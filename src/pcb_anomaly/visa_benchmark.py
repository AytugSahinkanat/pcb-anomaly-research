"""Fixed, matched-backbone few-reference VisA image anomaly benchmark."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
from PIL import Image

from .crops import read_rows, sha256, square_input
from .evaluation import binary_metrics, calibrate_threshold, knn_scores
from .visa import CATEGORIES, safe_path

PROTOCOL = {
    'seed': 42, 'references_per_category': 64, 'input_size': 224,
    'backbone': 'resnet18 IMAGENET1K_V1 frozen',
    'preprocessing': 'RGB; center pad RGB(124,116,104); bilinear 224; ImageNet normalize',
    'global': 'layer4 global average; L2 normalize; mean Euclidean 3NN',
    'patchcore': 'layer2/layer3 3x3 local average (zero padding); bilinear layer3 to layer2; concatenate 384D; no L2 normalization',
    'coreset_fraction': 0.01, 'coreset_projection_dim': 64,
    'coreset': 'Gaussian projection for greedy farthest-first selection only; seeded first point; unique indices; original 384D features used for scoring',
    'patch_score': 'exact Euclidean 1NN; image score = maximum of 28x28 patch distances; no reweighting',
    'threshold': 'per method/category 95th percentile of 100 normal calibration scores, higher; anomaly iff score > threshold',
    'evaluation': 'official test unchanged; image AUROC, noninterpolated AP, confusion counts; no test tuning',
    'scope': 'PatchCore-ResNet18 implementation variant; not official WideResNet50 reproduction; single seed, 64 references',
}


def ranking_metrics(labels, scores):
    y, s = np.asarray(labels), np.asarray(scores, dtype=float)
    if y.ndim != 1 or y.shape != s.shape or not np.isin(y, [0, 1]).all() or not np.isfinite(s).all() or len(np.unique(y)) != 2:
        raise ValueError('Require finite aligned scores and both binary classes')
    positive, negative = s[y == 1], s[y == 0]
    auc = np.mean((positive[:, None] > negative).astype(float) + .5 * (positive[:, None] == negative))
    order = np.argsort(-s, kind='stable')
    sorted_y, sorted_s = y[order], s[order]
    ends = np.r_[np.flatnonzero(np.diff(sorted_s)), len(s)-1]
    tp = np.cumsum(sorted_y)[ends]
    precision = tp / (ends+1)
    ap = np.sum(np.diff(np.r_[0, tp]) / len(positive) * precision)
    return {'auroc': float(auc), 'average_precision': float(ap)}


def choose_samples(rows, count=64, seed=42):
    result = {}
    if len({r['image'] for r in rows}) != len(rows):
        raise ValueError('Duplicate image IDs')
    for category in CATEGORIES:
        group = [r for r in rows if r['object'] == category]
        if any(r['label'] != 'normal' for r in group if r['split'] in ('reference', 'calibration')):
            raise ValueError('Anomaly in reference/calibration')
        ref = sorted((r for r in group if r['split'] == 'reference'),
                     key=lambda r: hashlib.sha256(f"{seed}:reference:{r['image']}".encode()).hexdigest())
        if len(ref) < count:
            raise ValueError('Insufficient references')
        selected = ref[:count] + sorted((r for r in group if r['split'] in ('calibration', 'test')), key=lambda r: r['image'])
        for split in ('calibration', 'test'):
            if not any(r['split'] == split for r in selected):
                raise ValueError('Missing evaluation split')
        result[category] = selected
    return result


def greedy_coreset(features, count, seed=42, projection_dim=64):
    x = np.asarray(features, dtype=np.float32)
    if x.ndim != 2 or not np.isfinite(x).all() or not 1 <= count <= len(x):
        raise ValueError('Invalid coreset inputs')
    rng = np.random.default_rng(seed)
    projection = rng.normal(size=(x.shape[1], projection_dim)).astype(np.float32) / np.sqrt(projection_dim)
    projected = x @ projection
    selected, minimum = [], np.full(len(x), np.inf, dtype=np.float32)
    current = int(rng.integers(len(x)))
    for _ in range(count):
        selected.append(current)
        distance = np.sum((projected - projected[current]) ** 2, axis=1)
        minimum = np.minimum(minimum, distance)
        minimum[selected] = -np.inf
        current = int(np.argmax(minimum))
    return np.asarray(selected, dtype=np.int64)


def nearest_distances(query, bank, chunk=2048):
    q, b = np.asarray(query, dtype=np.float32), np.asarray(bank, dtype=np.float32)
    if q.ndim != 2 or b.ndim != 2 or not len(b) or q.shape[1] != b.shape[1] or not np.isfinite(q).all() or not np.isfinite(b).all():
        raise ValueError('Invalid distance inputs')
    bn = (b*b).sum(1)
    result = []
    for start in range(0, len(q), chunk):
        block = q[start:start+chunk]
        d2 = (block*block).sum(1)[:, None] + bn[None, :] - 2 * block @ b.T
        result.append(np.sqrt(np.maximum(d2.min(1), 0)))
    return np.concatenate(result)


def run(root, audit, output, cache):
    import torch
    import torch.nn.functional as F
    import torchvision
    from torchvision.models import resnet18, ResNet18_Weights
    from torchvision.transforms.functional import to_tensor, normalize

    root, audit, output, cache = map(Path, (root, audit, output, cache))
    if json.loads((audit/'audit.json').read_text())['status'] != 'complete':
        raise ValueError('Require completed data audit')
    groups = choose_samples(read_rows(audit/'manifest.jsonl'))
    output.mkdir(parents=True, exist_ok=False)
    plan = dict(PROTOCOL, manifest_sha256=sha256(audit/'manifest.jsonl'),
                source_sha256=sha256(Path(__file__)),
                selection={c: [{'image': r['image'], 'split': r['split']} for r in rows] for c, rows in groups.items()})
    (output/'protocol.json').write_text(json.dumps(plan, indent=2))
    (output/'run.json').write_text(json.dumps({'status': 'running'}))
    torch.set_num_threads(4)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1).eval().requires_grad_(False)

    def extract(rows):
        tensors = []
        for row in rows:
            path = safe_path(root, row['image'])
            if sha256(path) != row['image_sha256']:
                raise ValueError('Source image changed')
            with Image.open(path) as image:
                tensor = to_tensor(square_input(image, 224))
            tensors.append(normalize(tensor, [.485, .456, .406], [.229, .224, .225]))
        with torch.inference_mode():
            x = model.maxpool(model.relu(model.bn1(model.conv1(torch.stack(tensors)))))
            x = model.layer1(x)
            l2 = model.layer2(x)
            l3 = model.layer3(l2)
            global_features = model.avgpool(model.layer4(l3)).flatten(1)
            global_features = F.normalize(global_features, dim=1)
            local2 = F.avg_pool2d(l2, 3, stride=1, padding=1)
            local3 = F.avg_pool2d(l3, 3, stride=1, padding=1)
            local3 = F.interpolate(local3, size=local2.shape[-2:], mode='bilinear', align_corners=False)
            patches = torch.cat([local2, local3], dim=1).permute(0, 2, 3, 1).reshape(len(rows), 784, 384)
        return global_features.numpy(), patches.numpy()

    results, records = [], []
    start_all = time.perf_counter()
    for category, rows in groups.items():
        start_category = time.perf_counter()
        directory = output/category
        directory.mkdir()
        refs = [r for r in rows if r['split'] == 'reference']
        queries = [r for r in rows if r['split'] != 'reference']
        globals_, patches_ = [], []
        for start in range(0, len(refs), 16):
            g, p = extract(refs[start:start+16]); globals_.append(g); patches_.append(p)
        global_bank, all_patches = np.concatenate(globals_), np.concatenate(patches_).reshape(-1, 384)
        extraction_seconds = time.perf_counter()-start_category
        start = time.perf_counter()
        coreset_ids = greedy_coreset(all_patches, max(1, int(len(all_patches)*.01)))
        bank = all_patches[coreset_ids]
        coreset_seconds = time.perf_counter()-start
        np.save(directory/'global_bank.npy', global_bank)
        np.save(directory/'patch_bank.npy', bank)
        np.save(directory/'coreset_indices.npy', coreset_ids)
        del all_patches, patches_
        global_scores, patch_scores, patch_maps, query_globals = [], [], [], []
        feature_seconds = global_seconds = patch_seconds = 0.
        for start in range(0, len(queries), 16):
            batch = queries[start:start+16]
            t = time.perf_counter(); g, p = extract(batch); feature_seconds += time.perf_counter()-t
            t = time.perf_counter()
            scores = knn_scores(global_bank, g, k=3, reference_ids=[r['image'] for r in refs], query_ids=[r['image'] for r in batch])
            global_seconds += time.perf_counter()-t
            t = time.perf_counter()
            maps = nearest_distances(p.reshape(-1, 384), bank).reshape(len(batch), 28, 28)
            patch_seconds += time.perf_counter()-t
            global_scores.extend(scores.tolist()); patch_scores.extend(maps.max(axis=(1, 2)).tolist())
            patch_maps.append(maps); query_globals.append(g)
            if start % 80 == 0:
                print(f'{category}: scored {start+len(batch)}/{len(queries)} calibration/test images', flush=True)
        np.save(directory/'patch_maps.npy', np.concatenate(patch_maps))
        np.save(directory/'query_global_features.npy', np.concatenate(query_globals))
        (directory/'queries.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in queries))
        ci = [i for i, r in enumerate(queries) if r['split'] == 'calibration']
        ti = [i for i, r in enumerate(queries) if r['split'] == 'test']
        labels = [int(queries[i]['is_anomaly']) for i in ti]
        for method, values in [('resnet18_global_knn', global_scores), ('patchcore_resnet18', patch_scores)]:
            scores = np.asarray(values)
            threshold = calibrate_threshold(scores[ci], quantile=.95)
            metrics = binary_metrics(labels, scores[ti], threshold=threshold, label_source='independent_annotation')
            metrics.update(ranking_metrics(labels, scores[ti]))
            result = dict(category=category, method=method, threshold=threshold, **metrics)
            results.append(result)
            for i, row in enumerate(queries):
                records.append({'category': category, 'method': method, 'image': row['image'], 'split': row['split'],
                                'label': int(row['is_anomaly']), 'score': float(scores[i]), 'threshold': threshold,
                                'prediction': int(scores[i] > threshold)})
        timing = dict(reference_extraction_seconds=extraction_seconds, coreset_seconds=coreset_seconds,
                      shared_query_extraction_seconds=feature_seconds, global_search_seconds=global_seconds,
                      patch_search_seconds=patch_seconds, query_images=len(queries),
                      patch_bank_shape=list(bank.shape), global_bank_shape=list(global_bank.shape),
                      patch_bank_bytes=bank.nbytes, global_bank_bytes=global_bank.nbytes,
                      elapsed_seconds=time.perf_counter()-start_category)
        (directory/'timing.json').write_text(json.dumps(timing, indent=2))
        print(f'{category}: complete in {timing["elapsed_seconds"]:.1f}s', flush=True)
    aggregate = {}
    for method in ('resnet18_global_knn', 'patchcore_resnet18'):
        subset = [r for r in results if r['method'] == method]
        counts = {key: sum(r[key] for r in subset) for key in ('tp', 'fp', 'tn', 'fn')}
        aggregate[method] = dict(macro_auroc=float(np.mean([r['auroc'] for r in subset])),
                                macro_ap=float(np.mean([r['average_precision'] for r in subset])),
                                sensitivity=counts['tp']/(counts['tp']+counts['fn']),
                                fpr=counts['fp']/(counts['fp']+counts['tn']), **counts)
    summary = {'per_category': results, 'aggregate': aggregate}
    (output/'results.json').write_text(json.dumps(summary, indent=2))
    (output/'scores.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    run_info = dict(status='complete', protocol_sha256=sha256(output/'protocol.json'),
                    weights_sha256=sha256(cache/'checkpoints/resnet18-f37072fd.pth'),
                    torch=torch.__version__, torchvision=torchvision.__version__, numpy=np.__version__,
                    python=platform.python_version(), threads=4, device='cpu',
                    elapsed_seconds=time.perf_counter()-start_all)
    (output/'run.json').write_text(json.dumps(run_info, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/visa-pcb-v2'))
    parser.add_argument('--audit', type=Path, default=Path('data/visa-audit-v1'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('data/torch-cache'))
    args = parser.parse_args()
    run(args.root, args.audit, args.output, args.cache)


if __name__ == '__main__':
    main()
