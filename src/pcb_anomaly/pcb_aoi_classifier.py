"""Frozen-feature ROI classification on the official PCB-AoI board split."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import platform
import time
import zipfile

import numpy as np
from PIL import Image, ImageDraw

from .crops import sha256
from .soldef_resnet import embed, hog_descriptor, metrics, polygon_crop

LABELS = ('Bad_podu', 'Bad_qiaojiao')


def _read_manifest(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line]


def _unique_train_images(records):
    """Collapse exact pixel duplicates, retaining the richer XML label set."""
    grouped = defaultdict(list)
    for row in records:
        if row['split'] == 'train':
            grouped[row['sha256']].append(row)
    selected = []
    duplicate_groups = []
    for digest, rows in sorted(grouped.items()):
        rows.sort(key=lambda r: (-r['object_count'], r['annotation']))
        selected.append(rows[0])
        if len(rows) > 1:
            duplicate_groups.append({
                'sha256': digest, 'selected_annotation': rows[0]['annotation'],
                'discarded_annotations': [r['annotation'] for r in rows[1:]],
                'object_counts': [r['object_count'] for r in rows]})
    return selected, duplicate_groups


def _make_samples(archive_path, audit_records):
    train, duplicate_groups = _unique_train_images(audit_records)
    test = [r for r in audit_records if r['split'] == 'test']
    if len(test) != len({r['sha256'] for r in test}):
        raise ValueError('Exact duplicate test images must be resolved before evaluation')
    if {r['sha256'] for r in train} & {r['sha256'] for r in test}:
        raise ValueError('Training/test exact image leakage')
    samples = []
    with zipfile.ZipFile(archive_path) as archive:
        for split, records in (('train', train), ('test', test)):
            for row in records:
                with Image.open(io.BytesIO(archive.read(row['image']))) as source:
                    image = source.convert('RGB')
                for index, obj in enumerate(row['objects']):
                    label = obj['class']
                    if label not in LABELS:
                        raise ValueError(f'Unexpected class: {label}')
                    # VOC coordinates are one-based and inclusive; convert to
                    # zero-based half-open crop boundaries used by Pillow.
                    x1, y1, x2, y2 = obj['xyxy']
                    polygon = np.array([[max(0, x1 - 1), max(0, y1 - 1),],
                                        [x2, max(0, y1 - 1)], [x2, y2],
                                        [max(0, x1 - 1), y2]], dtype=np.float64)
                    crop = polygon_crop(image, polygon, padding=0.20, size=224)
                    samples.append({'sample_id': f'{split}|{row["sha256"]}|{index:04d}',
                                    'split': split, 'image': row['image'],
                                    'board_id': Path(row['image']).stem,
                                    'object_index': index, 'label': label,
                                    'crop': crop})
                image.close()
    return samples, duplicate_groups


def _classify(train_features, train_labels, query_features):
    prototypes = []
    for label in LABELS:
        selected = train_features[np.asarray(train_labels) == label]
        if not len(selected):
            raise ValueError(f'No training samples for class {label}')
        center = selected.mean(axis=0)
        center /= max(float(np.linalg.norm(center)), 1e-12)
        prototypes.append(center)
    similarities = query_features @ np.stack(prototypes).T
    return np.asarray(LABELS)[similarities.argmax(axis=1)]


def _cluster_bootstrap(truth, predictions, image_ids, replicates=2000, seed=42):
    by_image = defaultdict(list)
    for i, image in enumerate(image_ids):
        by_image[image].append(i)
    groups = sorted(by_image)
    rng = np.random.default_rng(seed)
    output = defaultdict(list)
    for _ in range(replicates):
        selected_groups = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([by_image[g] for g in selected_groups])
        result = metrics(truth[indices], predictions[indices], LABELS)
        for key in ('balanced_accuracy', 'macro_f1', 'accuracy'):
            output[key].append(result[key])
    return {key: {'lower_95': float(np.quantile(values, 0.025)),
                  'upper_95': float(np.quantile(values, 0.975)),
                  'replicates': replicates, 'resampling_unit': 'held-out image/board'}
            for key, values in output.items()}


def _paired_cluster_differences(truth, left, right, image_ids, replicates=2000, seed=42):
    by_image = defaultdict(list)
    for i, image in enumerate(image_ids):
        by_image[image].append(i)
    groups = sorted(by_image)
    rng = np.random.default_rng(seed)
    differences = defaultdict(list)
    for _ in range(replicates):
        selected_groups = rng.choice(groups, size=len(groups), replace=True)
        indices = np.concatenate([by_image[g] for g in selected_groups])
        left_metrics = metrics(truth[indices], left[indices], LABELS)
        right_metrics = metrics(truth[indices], right[indices], LABELS)
        for key in ('balanced_accuracy', 'macro_f1', 'accuracy'):
            differences[key].append(left_metrics[key] - right_metrics[key])
    return {key: {'mean_difference': float(np.mean(values)),
                  'lower_95': float(np.quantile(values, 0.025)),
                  'upper_95': float(np.quantile(values, 0.975)),
                  'replicates': replicates, 'resampling_unit': 'paired held-out image/board'}
            for key, values in differences.items()}


def _error_gallery(samples, predictions, path, max_each=5):
    errors_by_method = {}
    sample_by_id = {r['sample_id']: r for r in samples}
    for method in ('resnet18', 'hog'):
        errors = [r for r in predictions
                  if r['method'] == method and r['true'] != r['predicted']]
        errors.sort(key=lambda r: (r['image'], r['sample_id']))
        errors_by_method[method] = errors[:max_each]
    tile, header, columns = 224, 38, 2
    row_count = max(1, max(len(v) for v in errors_by_method.values()))
    canvas = Image.new('RGB', (tile * columns, header + (tile + header) * row_count), 'white')
    draw = ImageDraw.Draw(canvas)
    for col, method in enumerate(('resnet18', 'hog')):
        draw.text((col * tile + 6, 7), f'{method}: errors', fill='black')
        for row_index, prediction in enumerate(errors_by_method[method]):
            sample = sample_by_id[prediction['sample_id']]
            crop = sample['crop'].resize((tile, tile))
            x, y = col * tile, header + (tile + header) * row_index
            canvas.paste(crop, (x, y + header))
            short_name = Path(sample['image']).stem[-18:]
            short_label = {'Bad_podu': 'paste-shortage',
                           'Bad_qiaojiao': 'bridge'}
            draw.text((x + 4, y + 3),
                      f'{short_label[prediction["true"]]} -> '
                      f'{short_label[prediction["predicted"]]}', fill='black')
            draw.text((x + 4, y + 19), short_name, fill='#555555')
    canvas.save(path)


def run(archive_path, audit_manifest, output, cache, threads=4):
    archive_path, audit_manifest, output = map(Path, (archive_path, audit_manifest, output))
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    audit_records = _read_manifest(audit_manifest)
    if any(r['split'] not in {'train', 'test', 'train_augmentation'} for r in audit_records):
        raise ValueError('Unexpected split in audit manifest')
    samples, duplicate_groups = _make_samples(archive_path, audit_records)
    train = [r for r in samples if r['split'] == 'train']
    test = [r for r in samples if r['split'] == 'test']
    train_counts = Counter(r['label'] for r in train)
    test_counts = Counter(r['label'] for r in test)
    if set(train_counts) != set(LABELS) or set(test_counts) != set(LABELS):
        raise ValueError('Both labels must occur in the official train and test splits')

    output.mkdir(parents=True)
    plan = {
        'status': 'protocol_frozen_before_scoring',
        'dataset': 'KubeEdge-Ianvs PCB-AoI Public Dataset, Kaggle version 5',
        'archive_sha256': sha256(archive_path),
        'audit_manifest_sha256': sha256(audit_manifest),
        'task': 'classify the defect type inside ground-truth bounding boxes',
        'official_split': 'raw train_data for references/prototypes; test_data once for held-out board evaluation',
        'excluded_data': 'train_data_augmentation is not counted as independent training samples',
        'exact_duplicate_policy': 'within raw training pixels, keep the annotation XML with the greatest object count; ties use lexicographic path; never merge train/test',
        'crop': 'VOC box to zero-based half-open coordinates; add 20% context; aspect-preserving 224x224 letterbox RGB(124,116,104)',
        'methods': ['frozen torchvision ResNet18 ImageNet-1K V1 512D cosine nearest class centroid',
                    'unsigned 9-bin HOG, 16px cells, 2x2-cell L2-Hys blocks, cosine nearest class centroid',
                    'training-majority class baseline'],
        'selection': 'no test-driven tuning; fixed protocol inherited from the earlier SolDef ROI comparison',
        'metrics': ['balanced accuracy', 'macro F1', 'accuracy', 'per-class recall'],
        'uncertainty': '2,000 image/board-cluster bootstrap replicates, seed 42, percentile 95% interval',
        'forbidden_interpretations': ['not object detection mAP', 'not pixel localization',
                                      'no false-alarm rate because test split has no normal images',
                                      'not a PatchCore or one-class anomaly benchmark'],
        'train_roi_counts': dict(train_counts), 'test_roi_counts': dict(test_counts),
        'train_unique_images': len({r['image'] for r in train}),
        'test_images': len({r['image'] for r in test}),
        'duplicate_train_images_collapsed': duplicate_groups,
        'created_utc_date': '2026-10-29'}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')

    started = time.perf_counter()
    features, model_info = embed(samples, cache, threads=threads)
    hog_features = np.stack([hog_descriptor(row['crop']) for row in samples])
    train_idx = np.array([i for i, r in enumerate(samples) if r['split'] == 'train'])
    test_idx = np.array([i for i, r in enumerate(samples) if r['split'] == 'test'])
    truth = np.asarray([samples[i]['label'] for i in test_idx])
    image_ids = np.asarray([samples[i]['board_id'] for i in test_idx])
    methods = {
        'resnet18': _classify(features[train_idx],
                              [samples[i]['label'] for i in train_idx], features[test_idx]),
        'hog': _classify(hog_features[train_idx],
                         [samples[i]['label'] for i in train_idx], hog_features[test_idx])}
    majority_label = train_counts.most_common(1)[0][0]
    methods['majority'] = np.full(len(test_idx), majority_label)

    results, prediction_rows = {}, []
    for method, predicted in methods.items():
        result = metrics(truth, predicted, LABELS)
        result['cluster_bootstrap_95'] = _cluster_bootstrap(
            truth, predicted, image_ids) if method != 'majority' else None
        results[method] = result
        for idx, true, guess in zip(test_idx, truth, predicted):
            prediction_rows.append({'method': method, 'sample_id': samples[idx]['sample_id'],
                                    'image': samples[idx]['image'], 'true': str(true),
                                    'predicted': str(guess)})

    summary = {
        'status': 'complete', 'plan': plan,
        'model': model_info,
        'counts': {'train_raw_images_before_dedup': sum(r['split'] == 'train' for r in audit_records),
                   'train_unique_images': len({r['image'] for r in train}),
                   'train_roi': len(train), 'test_images': len({r['image'] for r in test}),
                   'test_roi': len(test), 'train_class_counts': dict(train_counts),
                   'test_class_counts': dict(test_counts)},
        'results': results,
        'paired_resnet18_minus_hog': _paired_cluster_differences(
            truth, methods['resnet18'], methods['hog'], image_ids),
        'runtime_seconds': time.perf_counter() - started,
        'interpretation': 'External board-held-out defect-type ROI classification on PCB-AoI only; not an anomaly detector evaluation.'}
    (output / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output / 'predictions.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in prediction_rows), encoding='utf-8')
    _error_gallery(samples, prediction_rows, output / 'errors.jpg')
    print(json.dumps({'status': summary['status'], 'output': str(output),
                      'counts': summary['counts'],
                      'results': {k: {m: v for m, v in val.items()
                                      if m in {'balanced_accuracy', 'macro_f1', 'accuracy',
                                               'recall_by_class', 'cluster_bootstrap_95'}}
                                  for k, val in results.items()}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('data/downloads/PCB-AoI.zip'))
    parser.add_argument('--audit-manifest', type=Path,
                        default=Path('data/pcb-aoi-audit-v2/manifest.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('data/pcb-aoi-classifier-v1'))
    parser.add_argument('--cache', type=Path, default=Path('data/torch-cache'))
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    run(args.archive, args.audit_manifest, args.output, args.cache, args.threads)


if __name__ == '__main__':
    main()
