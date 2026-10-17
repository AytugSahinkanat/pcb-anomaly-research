"""Post-evaluation uncertainty and failure examples; never tunes a model."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .crops import read_rows, square_input
from .visa import CATEGORIES, safe_path
from .visa_benchmark import ranking_metrics


def paired_bootstrap(records, iterations=1000, seed=2026):
    rng = np.random.default_rng(seed)
    arrays = []
    for category in CATEGORIES:
        a = sorted((r for r in records if r['category'] == category and r['split'] == 'test' and r['method'] == 'resnet18_global_knn'), key=lambda r: r['image'])
        b = sorted((r for r in records if r['category'] == category and r['split'] == 'test' and r['method'] == 'patchcore_resnet18'), key=lambda r: r['image'])
        if [r['image'] for r in a] != [r['image'] for r in b] or [r['label'] for r in a] != [r['label'] for r in b]:
            raise ValueError('Paired score alignment mismatch')
        arrays.append((np.array([r['label'] for r in a]), np.array([r['score'] for r in a]), np.array([r['score'] for r in b])))
    values = []
    for _ in range(iterations):
        differences = []
        for y, a, b in arrays:
            indices = np.concatenate([rng.choice(np.flatnonzero(y == label), np.sum(y == label), replace=True) for label in (0, 1)])
            ma, mb = ranking_metrics(y[indices], a[indices]), ranking_metrics(y[indices], b[indices])
            differences.append([mb['auroc']-ma['auroc'], mb['average_precision']-ma['average_precision']])
        values.append(np.mean(differences, axis=0))
    lower, upper = np.quantile(values, [.025, .975], axis=0)
    return {'iterations': iterations, 'seed': seed, 'comparison': 'PatchCore minus global ResNet18',
            'macro_auroc_difference_95_percentile_ci': [float(lower[0]), float(upper[0])],
            'macro_ap_difference_95_percentile_ci': [float(lower[1]), float(upper[1])],
            'limitations': 'Paired class/category-stratified image bootstrap. Conditional on one trained bank/seed; physical-board dependence unknown; not seed variability.'}


def review(root, benchmark, audit):
    root, benchmark, audit = map(Path, (root, benchmark, audit))
    if json.loads((benchmark/'run.json').read_text())['status'] != 'complete':
        raise ValueError('Require completed benchmark')
    records = read_rows(benchmark/'scores.jsonl')
    uncertainty = paired_bootstrap(records)
    (benchmark/'uncertainty.json').write_text(json.dumps(uncertainty, indent=2))
    manifest = {r['image']: r for r in read_rows(audit/'manifest.jsonl')}
    selected = []
    for category in CATEGORIES:
        subset = [r for r in records if r['category'] == category and r['method'] == 'patchcore_resnet18' and r['split'] == 'test']
        for label, prediction, name, reverse in [(1, 0, 'missed defect', False), (0, 1, 'false alarm', True)]:
            candidates = [r for r in subset if r['label'] == label and r['prediction'] == prediction]
            if not candidates:
                continue
            record = sorted(candidates, key=lambda r: (r['score'], r['image']), reverse=reverse)[0]
            selected.append(dict(record, example_type=name))
    # Two panels per example: GT overlay on source and normalized patch heatmap.
    canvas = Image.new('RGB', (960, 290*((len(selected)+1)//2)), 'white')
    draw = ImageDraw.Draw(canvas)
    for n, r in enumerate(selected):
        meta = manifest[r['image']]
        with Image.open(safe_path(root, r['image'])) as image:
            base = square_input(image)
        gt = base.copy()
        if meta['mask']:
            with Image.open(safe_path(root, meta['mask'])) as source:
                binary = Image.fromarray((np.asarray(source)>0).astype('uint8')*255)
            side = max(binary.size)
            pad = Image.new('L', (side, side), 0)
            pad.paste(binary, ((side-binary.width)//2, (side-binary.height)//2))
            mask = np.asarray(pad.resize((224, 224), Image.Resampling.NEAREST)) > 0
            pixels = np.asarray(gt).copy()
            pixels[mask] = (.45*pixels[mask]+.55*np.array([255, 0, 0])).astype('uint8')
            gt = Image.fromarray(pixels)
        queries = read_rows(benchmark/r['category']/'queries.jsonl')
        index = next(i for i, row in enumerate(queries) if row['image'] == r['image'])
        patch = np.load(benchmark/r['category']/'patch_maps.npy', allow_pickle=False)[index]
        scaled = (patch-patch.min())/max(float(np.ptp(patch)), 1e-8)
        heat = np.asarray(Image.fromarray(scaled).resize((224, 224), Image.Resampling.BILINEAR))
        color = np.zeros((224, 224, 3), dtype='uint8')
        color[:, :, 0] = (heat*255).astype('uint8'); color[:, :, 2] = ((1-heat)*255).astype('uint8')
        overlay = Image.blend(base, Image.fromarray(color), .5)
        x, y = (n%2)*480, (n//2)*290
        draw.text((x+5, y+4), f"{r['category']} {r['example_type']} | {Path(r['image']).name}", fill='black')
        draw.text((x+5, y+20), f"GT (red) | patch heat (per-image scale); score {r['score']:.2f} / threshold {r['threshold']:.2f}", fill='black')
        canvas.paste(gt, (x+5, y+45)); canvas.paste(overlay, (x+240, y+45))
    if selected:
        canvas.save(benchmark/'failure-review.jpg', quality=93)
    (benchmark/'review-selection.json').write_text(json.dumps(selected, indent=2))
    print(json.dumps(uncertainty, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/visa-pcb-v2'))
    parser.add_argument('--audit', type=Path, default=Path('data/visa-audit-v1'))
    parser.add_argument('--benchmark', type=Path, required=True)
    args = parser.parse_args()
    review(args.root, args.benchmark, args.audit)
