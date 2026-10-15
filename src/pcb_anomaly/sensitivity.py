"""Paired rotation/resolution sensitivity on calibration queries, fixed reference."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, __version__ as pillow_version
from .crops import read_rows, sha256, square_input

VARIANTS = ('identity', 'rot90', 'rot180', 'rot270', 'down50', 'down25')


def transform(image, variant):
    image = image.convert('RGB')
    if variant == 'identity':
        return image.copy()
    if variant in ('rot90', 'rot180', 'rot270'):
        return image.transpose(getattr(Image.Transpose, 'ROTATE_' + variant[3:]))
    if variant in ('down50', 'down25'):
        scale = .5 if variant == 'down50' else .25
        size = tuple(max(1, int(v * scale + .5)) for v in image.size)
        return image.resize(size, Image.Resampling.BOX)
    raise ValueError('Unknown variant')


def compare_neighbors(reference, original, changed, indices):
    """Stable cosine ranking. Overlap uses min(5, bank size), not Jaccard."""
    if not len(indices):
        return None
    bank = reference[indices]
    a, b = np.clip(bank @ original, -1, 1), np.clip(bank @ changed, -1, 1)
    ra, rb = np.argsort(-a, kind='stable'), np.argsort(-b, kind='stable')
    k = min(5, len(indices))
    return dict(top1_retained=bool(ra[0] == rb[0]),
                top5_overlap=len(set(ra[:k]) & set(rb[:k])) / k, k=k,
                original_top1=int(indices[ra[0]]), changed_top1=int(indices[rb[0]]),
                top1_cosine_delta=float(b[rb[0]] - a[ra[0]]),
                original_margin=float(a[ra[0]] - a[ra[1]]) if len(ra)>1 else None)


def aggregate(records):
    result = dict(n=len(records), mean_embedding_cosine=float(np.mean([r['embedding_cosine'] for r in records])))
    for mode in ('same_category', 'unrestricted'):
        items = [r[mode] for r in records if r[mode] is not None]
        result[mode] = dict(n=len(items))
        if items:
            for key in ('top1_retained', 'top5_overlap', 'top1_cosine_delta'):
                result[mode][key] = float(np.mean([r[key] for r in items]))
            result[mode]['n_k5'] = sum(r['k'] == 5 for r in items)
    result['category_agreement'] = float(np.mean([r['category_agreement'] for r in records]))
    return result


def run_experiment(feature_dir, crop_dir, output, cache, batch_size=32, threads=4):
    import torch
    import torchvision
    from torchvision.models import resnet18, ResNet18_Weights
    from torchvision.transforms.functional import to_tensor, normalize

    feature_dir, crop_dir, output, cache = map(Path, (feature_dir, crop_dir, output, cache))
    if batch_size < 1 or threads < 1:
        raise ValueError('Positive batch size/threads required')
    if output.exists():
        raise FileExistsError(output)
    provenance = json.loads((feature_dir / 'run.json').read_text())
    if provenance['status'] != 'complete' or sha256(feature_dir / 'features.npy') != provenance['features_sha256']:
        raise ValueError('Invalid baseline feature artifact')
    rows = read_rows(feature_dir / 'samples.jsonl')
    features = np.load(feature_dir / 'features.npy', allow_pickle=False)
    if [r['feature_index'] for r in rows] != list(range(len(rows))) or len(features) != len(rows):
        raise ValueError('Feature alignment mismatch')
    if len({r['sample_id'] for r in rows}) != len(rows) or not np.isfinite(features).all() or not np.allclose(np.linalg.norm(features, axis=1), 1, atol=1e-5):
        raise ValueError('Invalid IDs or embeddings')
    queries = [i for i, r in enumerate(rows) if r['split'] == 'calibration']
    refs = [i for i, r in enumerate(rows) if r['split'] == 'reference']
    if not queries or not refs:
        raise ValueError('Nonempty calibration and reference sets required')
    images = []
    for i in queries:
        path = (crop_dir / rows[i]['crop_path']).resolve()
        if not path.is_relative_to(crop_dir.resolve()) or sha256(path) != rows[i]['crop_sha256']:
            raise ValueError('Crop checksum/path mismatch')
        with Image.open(path) as image:
            images.append(image.convert('RGB'))
    torch.set_num_threads(threads)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    weights = ResNet18_Weights.IMAGENET1K_V1
    checkpoint = cache / 'checkpoints' / weights.url.rsplit('/', 1)[-1]
    if not checkpoint.exists() or sha256(checkpoint) != provenance['weights_sha256']:
        raise ValueError('Need the verified, cached baseline weights')
    model = resnet18(weights=weights).eval()
    model.fc = torch.nn.Identity()
    model.requires_grad_(False)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'queries.jsonl').write_text(''.join(json.dumps(dict(rows[i], experiment_index=j))+'\n' for j,i in enumerate(queries)), encoding='utf-8')
    all_records, summaries = [], {}
    started = time.perf_counter()
    for variant in VARIANTS:
        embeddings = []
        with torch.inference_mode():
            for start in range(0, len(images), batch_size):
                tensors = [normalize(to_tensor(square_input(transform(image, variant))), [.485,.456,.406], [.229,.224,.225]) for image in images[start:start+batch_size]]
                values = model(torch.stack(tensors))
                norms = values.norm(dim=1, keepdim=True)
                if not torch.isfinite(values).all() or (norms <= 0).any():
                    raise ValueError('Invalid transformed embeddings')
                embeddings.append((values / norms).numpy())
        changed = np.concatenate(embeddings)
        if variant == 'identity':
            np.testing.assert_allclose(changed, features[queries], atol=1e-6, rtol=1e-5)
            identity_max_error = float(np.max(abs(changed-features[queries])))
        np.save(output / (variant+'.npy'), changed, allow_pickle=False)
        records = []
        for j, qi in enumerate(queries):
            q = rows[qi]
            eligible = [i for i in refs if rows[i]['board_group'] != q['board_group']]
            same = [i for i in eligible if rows[i]['category'] == q['category']]
            unrestricted = compare_neighbors(features, features[qi], changed[j], eligible)
            if unrestricted is None:
                raise ValueError('No cross-board references')
            record = dict(variant=variant, sample_id=q['sample_id'], category=q['category'],
                          board_group=q['board_group'], small=min(images[j].size)<16,
                          embedding_cosine=float(np.clip(features[qi] @ changed[j], -1, 1)),
                          same_category=compare_neighbors(features, features[qi], changed[j], same),
                          unrestricted=unrestricted,
                          category_agreement=rows[unrestricted['changed_top1']]['category']==q['category'])
            records.append(record)
        summaries[variant] = dict(overall=aggregate(records),
            by_category={c:aggregate([r for r in records if r['category']==c]) for c in sorted({r['category'] for r in records})},
            by_board={b:aggregate([r for r in records if r['board_group']==b]) for b in sorted({r['board_group'] for r in records})},
            by_size={str(s):aggregate([r for r in records if r['small']==s]) for s in (True,False) if any(r['small']==s for r in records)})
        all_records.extend(records)
        print(variant, json.dumps(summaries[variant]['overall']), flush=True)
    (output / 'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in all_records), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')
    report = dict(status='complete', protocol='paired calibration queries; fixed original reference; cross-board filtering; test excluded',
                  variants=list(VARIANTS), resolution='native crop -> BOX downsample (nearest integer, minimum 1px) -> square pad -> bilinear 224',
                  rotation='lossless counterclockwise transpose before square padding; no flip, no interpolation',
                  baseline_features_sha256=provenance['features_sha256'], samples_sha256=sha256(feature_dir/'samples.jsonl'),
                  weights_sha256=provenance['weights_sha256'], identity_max_error=identity_max_error,
                  torch=torch.__version__, torchvision=torchvision.__version__, numpy=np.__version__, pillow=pillow_version,
                  batch_size=batch_size, threads=threads, seed=42, elapsed_seconds=time.perf_counter()-started)
    (output / 'run.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--features', type=Path, required=True)
    p.add_argument('--crops', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cache', type=Path, default=Path('data/torch-cache'))
    args = p.parse_args()
    run_experiment(args.features, args.crops, args.output, args.cache)
