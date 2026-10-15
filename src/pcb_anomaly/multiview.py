"""Four-view mean pooling and paired comparison against single-view ResNet18."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from .crops import read_rows, sha256, square_input
from .sensitivity import VARIANTS, transform, compare_neighbors, aggregate

ROTATIONS = ('identity', 'rot90', 'rot180', 'rot270')


def pool_views(views):
    """Mean of four L2-normalized view embeddings, then L2 normalize.

    Accumulate float32 inputs in float64 so cyclic ordering does not change
    rounding of the sum. This keeps the output dimension unchanged.
    """
    views = np.asarray(views, dtype=np.float32)
    if views.ndim != 3 or views.shape[0] != 4 or not np.isfinite(views).all():
        raise ValueError('Expected four finite matrices')
    if not np.allclose(np.linalg.norm(views, axis=2), 1, atol=1e-5):
        raise ValueError('Normalize individual views first')
    mean = views.astype(np.float64).mean(axis=0)
    norms = np.linalg.norm(mean, axis=1, keepdims=True)
    if (norms <= 0).any():
        raise ValueError('Zero pooled norm')
    return (mean / norms).astype(np.float32)


def experiment(features_dir, sensitivity_dir, crop_dir, output, cache):
    import torch
    import torchvision
    from torchvision.models import resnet18, ResNet18_Weights
    from torchvision.transforms.functional import to_tensor, normalize

    features_dir, sensitivity_dir, crop_dir, output, cache = map(Path,
        (features_dir, sensitivity_dir, crop_dir, output, cache))
    if output.exists():
        raise FileExistsError(output)
    base_run = json.loads((features_dir/'run.json').read_text())
    single_run = json.loads((sensitivity_dir/'run.json').read_text())
    if base_run['status'] != 'complete' or single_run['status'] != 'complete':
        raise ValueError('Completed baseline runs required')
    if sha256(features_dir/'features.npy') != base_run['features_sha256'] or single_run['baseline_features_sha256'] != base_run['features_sha256']:
        raise ValueError('Baseline checksum mismatch')
    if sha256(features_dir/'samples.jsonl') != single_run['samples_sha256']:
        raise ValueError('Metadata checksum mismatch')
    rows = read_rows(features_dir/'samples.jsonl')
    features = np.load(features_dir/'features.npy', allow_pickle=False)
    refs = [i for i,r in enumerate(rows) if r['split']=='reference']
    queries = [i for i,r in enumerate(rows) if r['split']=='calibration']
    if not refs or not queries or [r['feature_index'] for r in rows] != list(range(len(rows))):
        raise ValueError('Invalid alignment or empty split')
    query_rows = read_rows(sensitivity_dir/'queries.jsonl')
    if [r['sample_id'] for r in query_rows] != [rows[i]['sample_id'] for i in queries]:
        raise ValueError('Query cache order mismatch')
    cached = {v:np.load(sensitivity_dir/(v+'.npy'), allow_pickle=False) for v in VARIANTS}
    for value in cached.values():
        if value.shape != (len(queries),512) or not np.isfinite(value).all() or not np.allclose(np.linalg.norm(value,axis=1),1,atol=1e-5):
            raise ValueError('Invalid cached query features')
    np.testing.assert_allclose(cached['identity'],features[queries],atol=1e-6,rtol=1e-5)
    torch.set_num_threads(4)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    weights = ResNet18_Weights.IMAGENET1K_V1
    checkpoint = cache/'checkpoints'/weights.url.rsplit('/',1)[-1]
    if sha256(checkpoint) != base_run['weights_sha256']:
        raise ValueError('Weights mismatch')
    model = resnet18(weights=weights).eval()
    model.fc = torch.nn.Identity()
    model.requires_grad_(False)
    output.mkdir(parents=True,exist_ok=False)
    started = time.perf_counter()

    def load_images(indices):
        images = []
        for i in indices:
            path = (crop_dir/rows[i]['crop_path']).resolve()
            if not path.is_relative_to(crop_dir.resolve()) or sha256(path) != rows[i]['crop_sha256']:
                raise ValueError('Crop checksum/path mismatch')
            with Image.open(path) as image:
                images.append(image.convert('RGB'))
        return images

    def encode(images, condition, rotation, label):
        result = []
        with torch.inference_mode():
            for start in range(0,len(images),32):
                batch = [normalize(to_tensor(square_input(transform(transform(im,condition),rotation))),
                                   [.485,.456,.406],[.229,.224,.225]) for im in images[start:start+32]]
                value = model(torch.stack(batch))
                norm = value.norm(dim=1,keepdim=True)
                if not torch.isfinite(value).all() or (norm<=0).any():
                    raise ValueError('Invalid extracted features')
                result.append((value/norm).numpy())
                if start%1024==0:
                    print(f'{label}: {min(start+32,len(images))}/{len(images)}',flush=True)
        return np.concatenate(result)

    reference_images = load_images(refs)
    reference_views = [features[refs]]
    for rotation in ROTATIONS[1:]:
        value = encode(reference_images,'identity',rotation,'reference '+rotation)
        np.save(output/('reference-'+rotation+'.npy'),value,allow_pickle=False)
        reference_views.append(value)
    reference_pool = pool_views(reference_views)
    np.save(output/'reference.npy',reference_pool,allow_pickle=False)
    del reference_images, reference_views
    query_images = load_images(queries)
    original_views = np.stack([cached[r] for r in ROTATIONS])
    query_pool = pool_views(original_views)
    changed = {'identity':query_pool}
    # A rotated input has exactly the same four native pixel views in a cyclic
    # order. Reuse measured views, and validate this via fresh inference below.
    for offset, rotation in enumerate(ROTATIONS[1:],1):
        changed[rotation] = pool_views(np.roll(original_views,-offset,axis=0))
    for condition in ('down50','down25'):
        views = [cached[condition]]
        for rotation in ROTATIONS[1:]:
            value = encode(query_images,condition,rotation,condition+' '+rotation)
            np.save(output/(condition+'-'+rotation+'.npy'),value,allow_pickle=False)
            views.append(value)
        changed[condition] = pool_views(views)
    # Independently re-extract all four views after rotating eight query images.
    check_indices = np.linspace(0,len(queries)-1,min(8,len(queries)),dtype=int)
    selected = [query_images[i] for i in check_indices]
    fresh = pool_views([encode(selected,'rot90',r,'rotation check '+r) for r in ROTATIONS])
    np.testing.assert_allclose(fresh,query_pool[check_indices],atol=1e-6,rtol=1e-5)
    fresh_error = float(np.max(abs(fresh-query_pool[check_indices])))
    bank = np.zeros_like(features)
    bank[refs] = reference_pool
    bank[queries] = query_pool
    records, summaries = [], {}
    for variant in VARIANTS:
        np.save(output/(variant+'.npy'),changed[variant],allow_pickle=False)
        part = []
        for j,qi in enumerate(queries):
            q = rows[qi]
            eligible = [i for i in refs if rows[i]['board_group'] != q['board_group']]
            same = [i for i in eligible if rows[i]['category']==q['category']]
            unrestricted = compare_neighbors(bank,query_pool[j],changed[variant][j],eligible)
            part.append(dict(variant=variant,sample_id=q['sample_id'],category=q['category'],
                board_group=q['board_group'],small=min(query_images[j].size)<16,
                embedding_cosine=float(np.clip(query_pool[j]@changed[variant][j],-1,1)),
                same_category=compare_neighbors(bank,query_pool[j],changed[variant][j],same),
                unrestricted=unrestricted,category_agreement=rows[unrestricted['changed_top1']]['category']==q['category']))
        summaries[variant] = dict(overall=aggregate(part),
            by_category={c:aggregate([r for r in part if r['category']==c]) for c in sorted({r['category'] for r in part})},
            by_board={b:aggregate([r for r in part if r['board_group']==b]) for b in sorted({r['board_group'] for r in part})},
            by_size={str(s):aggregate([r for r in part if r['small']==s]) for s in (True,False) if any(r['small']==s for r in part)})
        records.extend(part)
        print(variant,json.dumps(summaries[variant]['overall']),flush=True)
    baseline = json.loads((sensitivity_dir/'summary.json').read_text())
    comparison = {v:dict(single_view=baseline[v]['overall'],four_view=summaries[v]['overall']) for v in VARIANTS}
    for name,value in [('summary',summaries),('comparison',comparison)]:
        (output/(name+'.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (output/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    for name,indices in [('queries',queries),('reference',refs)]:
        (output/(name+'.jsonl')).write_text(''.join(json.dumps(dict(rows[i],pooled_index=j))+'\n' for j,i in enumerate(indices)),encoding='utf-8')
    run = dict(status='complete',method='mean of four individually L2-normalized views, float64 accumulation, final L2 normalization, 512D',
        protocol='calibration queries; fixed four-view reference bank; different board_group; test excluded',
        rotation_measurement='cyclic permutation of measured four views; independent fresh four-view extraction on 8 rotated queries',
        rotation_fresh_max_error=fresh_error,rotation_check_sample_ids=[rows[queries[i]]['sample_id'] for i in check_indices],
        baseline_features_sha256=base_run['features_sha256'],samples_sha256=single_run['samples_sha256'],
        baseline_summary_sha256=sha256(sensitivity_dir/'summary.json'),
        cached_query_sha256={v:sha256(sensitivity_dir/(v+'.npy')) for v in VARIANTS},
        output_features_sha256={p.name:sha256(p) for p in output.glob('*.npy')},weights_sha256=base_run['weights_sha256'],
        torch=torch.__version__,torchvision=torchvision.__version__,numpy=np.__version__,
        threads=4,batch_size=32,seed=42,elapsed_seconds=time.perf_counter()-started)
    (output/'run.json').write_text(json.dumps(run,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--features',type=Path,required=True)
    p.add_argument('--sensitivity',type=Path,required=True)
    p.add_argument('--crops',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('data/torch-cache'))
    args=p.parse_args()
    experiment(args.features,args.sensitivity,args.crops,args.output,args.cache)
