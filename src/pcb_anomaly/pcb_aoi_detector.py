"""Train and evaluate a fixed Faster R-CNN baseline on PCB-AoI."""
import argparse
from collections import Counter, defaultdict
import io
import json
import math
from pathlib import Path
import random
import time
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .crops import sha256
from .pcb_aoi_classifier import _read_manifest, _unique_train_images

LABELS = ('Bad_podu', 'Bad_qiaojiao')
LABEL_TO_ID = {'Bad_podu': 1, 'Bad_qiaojiao': 2}


class BoardDataset:
    def __init__(self, archive_path, records):
        self.archive_path = Path(archive_path)
        self.records = list(records)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        import torch
        from torchvision.transforms.functional import to_tensor

        row = self.records[index]
        with zipfile.ZipFile(self.archive_path) as archive:
            image_bytes = archive.read(row['image'])
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        boxes, labels = [], []
        for obj in row['objects']:
            x1, y1, x2, y2 = obj['xyxy']
            # Pascal VOC one-based inclusive coordinates to zero-based
            # half-open coordinates used by torchvision detection models.
            boxes.append([max(0.0, x1 - 1.0), max(0.0, y1 - 1.0), x2, y2])
            labels.append(LABEL_TO_ID[obj['class']])
        target = {'boxes': torch.tensor(boxes, dtype=torch.float32),
                  'labels': torch.tensor(labels, dtype=torch.int64),
                  'image_id': torch.tensor([index], dtype=torch.int64)}
        tensor = to_tensor(image)
        image.close()
        return tensor, target


def _split_train(records, validation_fraction=0.20, seed=42):
    rng = np.random.default_rng(seed)
    shuffled = list(records)
    rng.shuffle(shuffled)
    n_val = max(1, round(len(shuffled) * validation_fraction))
    val = shuffled[:n_val]
    train = shuffled[n_val:]
    # Ensure both classes occur in both partitions using training metadata only.
    for label in LABELS:
        if not any(any(o['class'] == label for o in r['objects']) for r in val):
            index = next((i for i, r in enumerate(train)
                          if any(o['class'] == label for o in r['objects'])), None)
            if index is None:
                raise ValueError(f'No training board contains {label}')
            val.append(train.pop(index))
        if not any(any(o['class'] == label for o in r['objects']) for r in train):
            raise ValueError(f'No fitting board contains {label}')
    if {r['sha256'] for r in train} & {r['sha256'] for r in val}:
        raise ValueError('Exact image duplicate across fit/validation')
    return train, val


def _collate(batch):
    return tuple(zip(*batch))


def _iou(box, boxes):
    if len(boxes) == 0:
        return np.zeros(0, dtype=np.float64)
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    a = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    b = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0, boxes[:, 3] - boxes[:, 1])
    return inter / np.maximum(a + b - inter, 1e-12)


def _average_precision(records, predictions, class_id, iou_threshold):
    gt_by_image = {}
    n_gt = 0
    for row in records:
        boxes = np.asarray([o['box'] for o in row['_gt'] if o['label'] == class_id],
                           dtype=np.float64).reshape(-1, 4)
        gt_by_image[row['image']] = boxes
        n_gt += len(boxes)
    if n_gt == 0:
        return None
    detections = []
    for prediction in predictions:
        for box, score, label in zip(prediction['boxes'], prediction['scores'], prediction['labels']):
            if label == class_id:
                detections.append((float(score), prediction['image'], np.asarray(box, dtype=np.float64)))
    detections.sort(key=lambda row: (-row[0], row[1]))
    matched = defaultdict(set)
    true_positive, false_positive = [], []
    for _, image, box in detections:
        candidates = gt_by_image[image]
        overlaps = _iou(box, candidates)
        order = np.argsort(-overlaps)
        chosen = next((int(i) for i in order if overlaps[i] >= iou_threshold
                       and int(i) not in matched[image]), None)
        if chosen is None:
            true_positive.append(0.0)
            false_positive.append(1.0)
        else:
            matched[image].add(chosen)
            true_positive.append(1.0)
            false_positive.append(0.0)
    tp = np.cumsum(true_positive)
    fp = np.cumsum(false_positive)
    recall = tp / n_gt
    precision = tp / np.maximum(tp + fp, 1e-12)
    points = np.linspace(0, 1, 101)
    return float(np.mean([np.max(precision[recall >= p]) if np.any(recall >= p) else 0.0
                          for p in points]))


def detection_metrics(records, predictions):
    thresholds = np.arange(0.50, 0.951, 0.05)
    by_class = {}
    for class_id, label in enumerate(LABELS, 1):
        aps = [_average_precision(records, predictions, class_id, float(threshold))
               for threshold in thresholds]
        by_class[label] = {'ap50': aps[0], 'ap50_95': float(np.mean(aps))}
    return {'map50': float(np.mean([v['ap50'] for v in by_class.values()])),
            'map50_95': float(np.mean([v['ap50_95'] for v in by_class.values()])),
            'by_class': by_class, 'iou_thresholds': [round(float(x), 2) for x in thresholds],
            'ap_interpolation': '101-point interpolated precision-recall AP'}


def _evaluate(model, dataset, records, device, torch):
    from torch.utils.data import DataLoader
    model.eval()
    loader = DataLoader(dataset, batch_size=2, shuffle=False, num_workers=0,
                        collate_fn=_collate)
    predictions = []
    with torch.inference_mode():
        for images, _ in loader:
            outputs = model([image.to(device) for image in images])
            for output, row in zip(outputs, records[len(predictions):len(predictions) + len(outputs)]):
                predictions.append({'image': row['image'],
                                    'boxes': output['boxes'].cpu().numpy().tolist(),
                                    'scores': output['scores'].cpu().numpy().tolist(),
                                    'labels': output['labels'].cpu().numpy().tolist()})
    prepared = []
    for row in records:
        prepared.append({**row, '_gt': [{'box': [max(0.0, o['xyxy'][0] - 1.0),
                                                   max(0.0, o['xyxy'][1] - 1.0),
                                                   o['xyxy'][2], o['xyxy'][3]],
                                        'label': LABEL_TO_ID[o['class']]}
                                       for o in row['objects']]})
    return detection_metrics(prepared, predictions), predictions


def _write_review(archive_path, records, predictions, destination):
    image_by_name = {r['image']: r for r in records}
    first = sorted(image_by_name)[:8]
    tile, header, cols = 360, 34, 2
    rows_count = math.ceil(len(first) / cols)
    canvas = Image.new('RGB', (tile * cols, rows_count * (tile + header)), 'white')
    draw = ImageDraw.Draw(canvas)
    pred_by_name = {r.get('image', r.get('image_name')): r for r in predictions}
    with zipfile.ZipFile(archive_path) as archive:
        for i, name in enumerate(first):
            row, pred = image_by_name[name], pred_by_name[name]
            im = Image.open(io.BytesIO(archive.read(name))).convert('RGB')
            overlay = ImageDraw.Draw(im)
            for obj in row['objects']:
                x1, y1, x2, y2 = obj['xyxy']
                overlay.rectangle((x1, y1, x2, y2), outline='red', width=2)
            for box, score, label in zip(pred['boxes'], pred['scores'], pred['labels']):
                if score < 0.5 or label not in (1, 2):
                    continue
                x1, y1, x2, y2 = box
                overlay.rectangle((x1, y1, x2, y2), outline='lime', width=2)
            im.thumbnail((tile, tile))
            x, y = (i % cols) * tile, (i // cols) * (tile + header)
            canvas.paste(im, (x, y + header))
            draw.text((x + 4, y + 8), Path(name).name, fill='black')
            im.close()
    canvas.save(destination, quality=92)


def run(archive_path, audit_manifest, output, cache, epochs=10, threads=4):
    import torch
    import torchvision
    from torch.utils.data import DataLoader
    from torchvision.models.detection import (
        FasterRCNN_MobileNet_V3_Large_320_FPN_Weights,
        fasterrcnn_mobilenet_v3_large_320_fpn,
    )
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

    archive_path, audit_manifest, output, cache = map(Path,
                                                       (archive_path, audit_manifest, output, cache))
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    if epochs < 1 or threads < 1:
        raise ValueError('epochs and threads must be positive')
    audit_rows = _read_manifest(audit_manifest)
    train_all, duplicate_groups = _unique_train_images(audit_rows)
    fit_records, validation_records = _split_train(train_all)
    test_records = [r for r in audit_rows if r['split'] == 'test']
    if len(test_records) != 60:
        raise ValueError(f'Expected 60 official test boards, got {len(test_records)}')
    if ({r['sha256'] for r in train_all} & {r['sha256'] for r in test_records}):
        raise ValueError('Train/test image hash overlap')

    torch.manual_seed(42)
    random.seed(42)
    np.random.seed(42)
    torch.set_num_threads(threads)
    device = torch.device('cpu')
    output.mkdir(parents=True)
    weights = FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT
    plan = {'status': 'protocol_frozen_before_training',
            'dataset': 'PCB-AoI public dataset, Kaggle v5',
            'archive_sha256': sha256(archive_path),
            'audit_manifest_sha256': sha256(audit_manifest),
            'official_test': '60 source boards; used once after fixed validation-based epoch selection',
            'train_deduplication': 'exact train image hashes collapsed; keep XML with most boxes; ties by lexical annotation path',
            'fit_validation': '171 unique raw training images split 80/20 by image/board using numpy RNG seed 42; ensure both classes occur in each',
            'train_augmentation': 'excluded; only raw train_data used',
            'architecture': 'torchvision Faster R-CNN MobileNetV3-Large FPN 320, COCO V1 initialization, 3 classes including background',
            'training': {'epochs': epochs, 'batch_size': 2, 'optimizer': 'SGD',
                         'learning_rate': 0.0025, 'momentum': 0.9, 'weight_decay': 0.0005,
                         'step_lr': {'step_size': 5, 'gamma': 0.1}, 'seed': 42,
                         'data_augmentation': 'none'},
            'selection': 'checkpoint with highest validation mAP50:95; ties choose earliest epoch',
            'inference': {'score_threshold_for_AP': 0.001, 'nms_threshold': 0.5,
                          'max_detections_per_image': 100},
            'metrics': 'per-class AP50 and AP50:95; macro mAP; 101-point interpolated AP',
            'normal_data': 'none in official test; false-alarm rate cannot be estimated',
            'model_weights': {'name': str(weights), 'url': weights.url},
            'torch': torch.__version__, 'torchvision': torchvision.__version__,
            'python': __import__('platform').python_version(), 'device': 'cpu', 'threads': threads,
            'train_images': len(fit_records), 'validation_images': len(validation_records),
            'test_images': len(test_records), 'duplicate_train_groups': duplicate_groups}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')

    cache.mkdir(parents=True, exist_ok=True)
    torch.hub.set_dir(str(cache.resolve()))
    model = fasterrcnn_mobilenet_v3_large_320_fpn(weights=weights)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, len(LABELS) + 1)
    model.roi_heads.score_thresh = 0.001
    model.to(device)
    optimizer = torch.optim.SGD([p for p in model.parameters() if p.requires_grad],
                                lr=0.0025, momentum=0.9, weight_decay=0.0005)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)
    fit_dataset = BoardDataset(archive_path, fit_records)
    val_dataset = BoardDataset(archive_path, validation_records)
    test_dataset = BoardDataset(archive_path, test_records)
    loader = DataLoader(fit_dataset, batch_size=2, shuffle=True, num_workers=0,
                        collate_fn=_collate)
    best_ap, best_epoch, best_state, history = -1.0, None, None, []
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        loss_total, batches = 0.0, 0
        for images, targets in loader:
            images = [image.to(device) for image in images]
            targets = [{k: v.to(device) for k, v in t.items()} for t in targets]
            losses = model(images, targets)
            loss = sum(losses.values())
            if not torch.isfinite(loss):
                raise ValueError(f'Nonfinite detector loss at epoch {epoch}')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            loss_total += float(loss.detach())
            batches += 1
        scheduler.step()
        val_result, _ = _evaluate(model, val_dataset, validation_records, device, torch)
        row = {'epoch': epoch, 'mean_train_loss': loss_total / max(batches, 1),
               'validation_map50': val_result['map50'],
               'validation_map50_95': val_result['map50_95'],
               'learning_rate': optimizer.param_groups[0]['lr']}
        history.append(row)
        if val_result['map50_95'] > best_ap:
            best_ap, best_epoch = val_result['map50_95'], epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        (output / 'training.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
        print(json.dumps({'epoch': epoch, **row}), flush=True)

    if best_state is None:
        raise RuntimeError('No validation checkpoint was selected')
    model.load_state_dict(best_state)
    torch.save(best_state, output / 'selected_model.pth')
    test_result, test_predictions = _evaluate(model, test_dataset, test_records, device, torch)
    for pred in test_predictions:
        pred['image_name'] = pred.pop('image')
    summary = {'status': 'complete', 'plan': plan, 'selected_epoch': best_epoch,
               'selected_validation_map50_95': best_ap, 'validation_history': history,
               'test': test_result,
               'counts': {'fit_boards': len(fit_records), 'validation_boards': len(validation_records),
                          'test_boards': len(test_records),
                          'test_instances': sum(len(r['objects']) for r in test_records),
                          'test_class_counts': dict(Counter(o['class'] for r in test_records
                                                             for o in r['objects']))},
               'runtime_seconds': time.perf_counter() - started,
               'interpretation': 'Supervised box detection on held-out defective PCB-AoI boards; no normal-board false-alarm estimate.'}
    (output / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output / 'test_predictions.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in test_predictions), encoding='utf-8')
    _write_review(archive_path, test_records, test_predictions, output / 'test-review.jpg')
    print(json.dumps({'status': 'complete', 'output': str(output), 'selected_epoch': best_epoch,
                      'validation_map50_95': best_ap, 'test': test_result,
                      'runtime_seconds': summary['runtime_seconds']}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=Path('data/downloads/PCB-AoI.zip'))
    parser.add_argument('--audit-manifest', type=Path,
                        default=Path('data/pcb-aoi-audit-v2/manifest.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('data/pcb-aoi-detector-v1'))
    parser.add_argument('--cache', type=Path, default=Path('data/torch-cache'))
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    run(args.archive, args.audit_manifest, args.output, args.cache, args.epochs, args.threads)


if __name__ == '__main__':
    main()
