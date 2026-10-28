"""Acquire and audit the public PCB-AoI solder-paste inspection dataset."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .crops import sha256

URL = 'https://www.kaggle.com/api/v1/datasets/download/kubeedgeianvs/pcb-aoi'
SPLITS = {'train_data': 'train', 'test_data': 'test',
          'train_data_augmentation': 'train_augmentation'}


def acquire(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    partial = root / 'archive.zip.partial'
    with urllib.request.urlopen(URL, timeout=120) as response, partial.open('xb') as dest:
        while block := response.read(1024 * 1024):
            dest.write(block)
    with zipfile.ZipFile(partial) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC check failed')
    partial.rename(root / 'archive.zip')
    (root / 'acquisition.json').write_text(json.dumps({
        'status': 'complete', 'url': URL, 'bytes': (root / 'archive.zip').stat().st_size,
        'sha256': sha256(root / 'archive.zip'),
        'dataset': 'kubeedgeianvs/pcb-aoi',
        'license_reported_by_kaggle_at_review': 'Apache 2.0'}, indent=2), encoding='utf-8')


def _safe_member(group, relative):
    rel = PurePosixPath(relative.replace('\\', '/'))
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError(f'Unsafe indexed path: {relative}')
    return f'{group}/{rel.as_posix().removeprefix("./")}'


def audit(archive_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    archive_path = Path(archive_path)
    issues, warnings, records = [], [], []
    class_instances = defaultdict(Counter)
    class_images = defaultdict(Counter)
    primary_hashes = defaultdict(list)
    group_counts = Counter()
    review_samples = {}

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        if len(names) != len(archive.namelist()):
            raise ValueError('Duplicate ZIP member names')
        unsafe = [n for n in names if PurePosixPath(n).is_absolute()
                  or '..' in PurePosixPath(n).parts or '\\' in n]
        if unsafe:
            raise ValueError(f'Unsafe ZIP paths: {unsafe[:3]}')

        for group, split in SPLITS.items():
            index_name = f'{group}/index.txt'
            if index_name not in names:
                issues.append({'split': split, 'issue': 'missing_index'})
                continue
            raw_lines = archive.read(index_name).decode('utf-8-sig').splitlines()
            rows = [line.strip().split() for line in raw_lines if line.strip()]
            if len(rows) != len(set(tuple(row) for row in rows)):
                issues.append({'split': split, 'issue': 'duplicate_index_rows'})
            for row_number, row in enumerate(rows, 1):
                if len(row) != 2:
                    issues.append({'split': split, 'line': row_number,
                                   'issue': 'invalid_index_row'})
                    continue
                try:
                    image_name = _safe_member(group, row[0])
                    xml_name = _safe_member(group, row[1])
                except ValueError as exc:
                    issues.append({'split': split, 'line': row_number,
                                   'issue': str(exc)})
                    continue
                if image_name not in names or xml_name not in names:
                    issues.append({'split': split, 'image': image_name,
                                   'annotation': xml_name, 'issue': 'missing_pair'})
                    continue
                try:
                    image_bytes = archive.read(image_name)
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        width, height = image.size
                        image.verify()
                    root = ET.fromstring(archive.read(xml_name))
                except Exception as exc:
                    issues.append({'split': split, 'image': image_name,
                                   'issue': f'read_error:{type(exc).__name__}'})
                    continue

                annotation_size = (root.findtext('size/width'), root.findtext('size/height'))
                try:
                    annotation_size = tuple(map(int, annotation_size))
                except (TypeError, ValueError):
                    annotation_size = None
                size_matches = annotation_size == (width, height)
                if not size_matches:
                    issues.append({'split': split, 'image': image_name,
                                   'issue': 'image_xml_size_mismatch',
                                   'image_size': [width, height],
                                   'xml_size': annotation_size})

                boxes, labels = [], Counter()
                for object_index, obj in enumerate(root.findall('object')):
                    label = (obj.findtext('name') or '').strip()
                    box = obj.find('bndbox')
                    try:
                        coords = [float(box.findtext(k)) for k in
                                  ('xmin', 'ymin', 'xmax', 'ymax')]
                        x1, y1, x2, y2 = coords
                        valid = (all(map(lambda x: x == x and abs(x) != float('inf'), coords))
                                 and 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height)
                    except (AttributeError, TypeError, ValueError):
                        coords, valid = [], False
                    if not label:
                        issues.append({'split': split, 'image': image_name,
                                       'object': object_index, 'issue': 'empty_class'})
                    if not valid:
                        issues.append({'split': split, 'image': image_name,
                                       'object': object_index, 'issue': 'invalid_bbox'})
                    else:
                        boxes.append({'class': label, 'xyxy': coords})
                        labels[label] += 1
                        class_instances[split][label] += 1
                    if label:
                        if split in {'train', 'test'} and label not in review_samples:
                            review_samples[(split, label)] = (image_bytes, list(boxes))

                for label in labels:
                    class_images[split][label] += 1

                digest = hashlib.sha256(image_bytes).hexdigest()
                if split in {'train', 'test'}:
                    primary_hashes[split].append((digest, image_name))
                records.append({'split': split, 'image': image_name,
                                'annotation': xml_name, 'width': width, 'height': height,
                                'sha256': digest, 'objects': boxes,
                                'object_count': len(root.findall('object')),
                                'size_matches': size_matches})
                group_counts[split] += 1

    train_hashes = defaultdict(list)
    test_hashes = defaultdict(list)
    for digest, name in primary_hashes['train']:
        train_hashes[digest].append(name)
    for digest, name in primary_hashes['test']:
        test_hashes[digest].append(name)
    train_test_duplicates = [(t, v) for digest, train_names in train_hashes.items()
                             for t in train_names for v in test_hashes.get(digest, [])]
    within_train_duplicates = sum(max(0, len(v) - 1) for v in train_hashes.values())
    if train_test_duplicates:
        issues.append({'issue': 'exact_train_test_image_duplicates',
                       'pairs': train_test_duplicates})
    if within_train_duplicates:
        warnings.append({'issue': 'exact_duplicates_within_train',
                         'extra_files': within_train_duplicates})

    summary = {
        'status': 'complete' if not issues else 'issues_found',
        'dataset': 'PCB-AoI Public Dataset',
        'archive_bytes': archive_path.stat().st_size,
        'archive_sha256': sha256(archive_path),
        'counts': dict(group_counts),
        'instances_by_split_and_class': {k: dict(v) for k, v in class_instances.items()},
        'annotated_images_by_split_and_class': {k: dict(v) for k, v in class_images.items()},
        'exact_train_test_duplicate_pairs': len(train_test_duplicates),
        'exact_duplicates_within_raw_train_extra_files': within_train_duplicates,
        'issues': issues, 'warnings': warnings,
        'interpretation': [
            'Use train_data as the raw training set; train_data_augmentation is derived from training images and is not extra independent data.',
            'The official test split contains defective images only; no normal images were found, so false-alarm rate and one-class PatchCore evaluation are unsupported.',
            'This is solder-paste inspection (SPI), not post-reflow solder-joint inspection.'
        ]}
    (output / 'audit.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output / 'manifest.jsonl').write_text(
        ''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')
    _write_review(archive_path, output / 'annotation-review.jpg', review_samples)
    print(json.dumps(summary, indent=2))


def _write_review(archive_path, destination, samples):
    items = [(split, label, samples[(split, label)])
             for split in ('train', 'test') for label in sorted(
                 {key[1] for key in samples if key[0] == split})]
    if not items:
        return
    tile_size, header, columns = (420, 420), 32, 2
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new('RGB', (tile_size[0] * columns,
                               (tile_size[1] + header) * rows), 'white')
    draw = ImageDraw.Draw(canvas)
    with zipfile.ZipFile(archive_path) as archive:
        for i, (split, label, (image_bytes, boxes)) in enumerate(items):
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            overlay = ImageDraw.Draw(image)
            for box in boxes:
                x1, y1, x2, y2 = box['xyxy']
                overlay.rectangle((x1, y1, x2, y2), outline='red', width=3)
                overlay.text((x1, y1), box['class'], fill='yellow',
                             stroke_width=1, stroke_fill='black')
            tile = ImageOps.contain(image, tile_size)
            x, y = (i % columns) * tile_size[0], (i // columns) * (tile_size[1] + header)
            canvas.paste(tile, (x, y + header))
            draw.text((x + 8, y + 8), f'{split}: {label}', fill='black')
    canvas.save(destination, quality=92)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('acquire', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'acquire':
        acquire(args.root)
    else:
        archive = args.archive or (args.root / 'archive.zip')
        if args.output is None:
            parser.error('audit requires --output')
        audit(archive, args.output)


if __name__ == '__main__':
    main()
