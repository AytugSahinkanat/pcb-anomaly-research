"""Acquire and audit the official VisA PCB one-class benchmark."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .crops import sha256
from .download import download_ranges

URL = 'https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar'
REPO = 'https://raw.githubusercontent.com/amazon-science/spot-diff/main/'
CATEGORIES = ('pcb1', 'pcb2', 'pcb3', 'pcb4')


def safe_path(root, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
        raise ValueError(f'Unsafe source path: {relative}')
    target = (root / Path(*path.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes root: {relative}')
    return target


def acquire(root, archive_path=None):
    """Stream archive; retain only PCB files without storing a second copy."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    provenance = {'url': URL, 'status': 'incomplete', 'files': 0}
    (root / 'acquisition.json').write_text(json.dumps(provenance, indent=2))
    for name in ('split_csv/1cls.csv', 'LICENSE-DATASET', 'utils/id2class.py'):
        with urllib.request.urlopen(REPO + name, timeout=60) as response:
            (root / Path(name).name).write_bytes(response.read())
    if archive_path is not None:
        archive_path = Path(archive_path)
        provenance['download'] = download_ranges(URL, archive_path)
        provenance['archive_sha256'] = sha256(archive_path)
    source_context = archive_path.open('rb') if archive_path else urllib.request.urlopen(URL, timeout=120)
    with source_context as response:
        if archive_path is None:
            provenance['source_headers'] = dict(response.headers)
        with tarfile.open(fileobj=response, mode='r|' if archive_path is None else 'r:') as archive:
            for member in archive:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] not in CATEGORIES:
                    continue
                target = safe_path(root, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    if shutil.disk_usage(root).free < member.size + 1024**3:
                        raise OSError('Keep at least 1 GiB free disk space')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open('xb') as dest:
                        shutil.copyfileobj(source, dest, length=1024 * 1024)
                    provenance['files'] += 1
                    if provenance['files'] % 500 == 0:
                        print(f"Extracted {provenance['files']} PCB files", flush=True)
                else:
                    raise ValueError(f'Unsupported archive entry: {member.name}')
    if not provenance['files']:
        raise ValueError('No PCB entries found')
    provenance.update(status='complete', split_sha256=sha256(root / '1cls.csv'))
    (root / 'acquisition.json').write_text(json.dumps(provenance, indent=2))
    print(json.dumps(provenance), flush=True)


def partition(rows, calibration_count=100, seed=42):
    """Hash-ranked normal training holdout; official test remains untouched."""
    if calibration_count < 1:
        raise ValueError('Calibration count must be positive')
    seen = set()
    grouped = defaultdict(list)
    result = []
    for source in rows:
        if source['object'] not in CATEGORIES:
            continue
        row = dict(source)
        if row['image'] in seen:
            raise ValueError('Duplicate image in split CSV')
        seen.add(row['image'])
        if row['split'] not in ('train', 'test') or row['label'] not in ('normal', 'anomaly'):
            raise ValueError('Unexpected split or label')
        if row['split'] == 'train' and row['label'] != 'normal':
            raise ValueError('Anomaly in one-class training split')
        if bool(row['mask']) != (row['label'] == 'anomaly'):
            raise ValueError('Mask/label inconsistency')
        row['official_split'] = row['split']
        row['split'] = 'reference' if row['split'] == 'train' else 'test'
        result.append(row)
        if row['official_split'] == 'train':
            grouped[row['object']].append(row)
    if not result:
        raise ValueError('No PCB samples')
    for category, items in grouped.items():
        if len(items) <= calibration_count:
            raise ValueError(f'Insufficient normal training samples: {category}')
        items.sort(key=lambda r: hashlib.sha256(f"{seed}:{r['image']}".encode()).hexdigest())
        for row in items[:calibration_count]:
            row['split'] = 'calibration'
    return result


def audit(root, output, calibration_count=100, seed=42):
    root, output = Path(root), Path(output)
    if json.loads((root / 'acquisition.json').read_text())['status'] != 'complete':
        raise ValueError('Acquisition has not completed')
    with (root / '1cls.csv').open(newline='', encoding='utf-8') as stream:
        rows = partition(list(csv.DictReader(stream)), calibration_count, seed)
    output.mkdir(parents=True, exist_ok=False)
    counts = Counter()
    pixels = defaultdict(list)
    for row in rows:
        path = safe_path(root, row['image'])
        with Image.open(path) as source:
            image = source.convert('RGB')
        row['width'], row['height'] = image.size
        row['image_sha256'] = sha256(path)
        row['pixel_sha256'] = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        row['label_source'] = 'independent_annotation'
        row['is_anomaly'] = row['label'] == 'anomaly'
        row['mask_sha256'] = None
        row['defect_pixels'] = 0
        if row['mask']:
            mask_path = safe_path(root, row['mask'])
            with Image.open(mask_path) as source:
                mask = np.asarray(source)
            if mask.ndim != 2 or (mask.shape[1], mask.shape[0]) != image.size:
                raise ValueError(f"Mask geometry mismatch: {row['mask']}")
            row['defect_pixels'] = int(np.count_nonzero(mask))
            if not row['defect_pixels']:
                raise ValueError(f"Empty anomaly mask: {row['mask']}")
            row['mask_values'] = np.unique(mask).tolist()
            row['mask_sha256'] = sha256(mask_path)
        pixels[row['pixel_sha256']].append((row['image'], row['split']))
        counts[(row['object'], row['split'], row['label'])] += 1
    duplicates = [items for items in pixels.values() if len(items) > 1]
    cross_split = [items for items in duplicates if len({s for _, s in items}) > 1]
    summary = {'status': 'blocked_duplicate_leakage' if cross_split else 'complete',
               'samples': len(rows), 'seed': seed, 'calibration_per_category': calibration_count,
               'split_sha256': sha256(root / '1cls.csv'),
               'counts': [{'category': c, 'split': s, 'label': l, 'n': n}
                          for (c, s, l), n in sorted(counts.items())],
               'exact_pixel_duplicates': duplicates, 'cross_split_duplicates': cross_split,
               'physical_board_identity': 'unknown; official image split only',
               'mask_policy': 'raw masks preserved; anomaly = raw value > 0; normal = implicit zero'}
    (output / 'manifest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    (output / 'audit.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)
    if cross_split:
        raise ValueError('Exact pixel duplicates cross evaluation splits; audit required')
    preview(root, rows, output / 'mask-review.jpg')


def preview(root, rows, destination):
    """Fixed first examples for annotation QA, not model selection."""
    canvas = Image.new('RGB', (1280, 300 * len(CATEGORIES)), 'white')
    draw = ImageDraw.Draw(canvas)
    for index, category in enumerate(CATEGORIES):
        items = sorted((r for r in rows if r['object'] == category), key=lambda r: r['image'])
        normal = next((r for r in items if r['label'] == 'normal'), None)
        anomaly = next((r for r in items if r['label'] == 'anomaly'), None)
        if normal is None or anomaly is None:
            continue
        good = Image.open(safe_path(root, normal['image'])).convert('RGB')
        bad = Image.open(safe_path(root, anomaly['image'])).convert('RGB')
        with Image.open(safe_path(root, anomaly['mask'])) as mask:
            binary = Image.fromarray((np.asarray(mask) > 0).astype('uint8') * 255)
        overlay = Image.composite(Image.blend(bad, Image.new('RGB', bad.size, 'red'), .55), bad, binary)
        x0, y0, x1, y1 = binary.getbbox()
        margin = 30
        zoom = overlay.crop((max(0, x0-margin), max(0, y0-margin),
                             min(bad.width, x1+margin), min(bad.height, y1+margin)))
        views = [(good, 'normal'), (bad, 'anomaly'), (overlay, 'mask overlay'), (zoom, 'defect zoom')]
        for column, (image, title) in enumerate(views):
            tile = ImageOps.contain(image, (310, 260))
            canvas.paste(tile, (column*320 + (320-tile.width)//2, index*300+30))
            draw.text((column*320+8, index*300+8), f'{category} | {title}', fill='black')
    canvas.save(destination, quality=92)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('acquire', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--archive', type=Path, help='Download with parallel ranges and retain source tar')
    parser.add_argument('--calibration-count', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.action == 'acquire':
        acquire(args.root, args.archive)
    else:
        if args.output is None:
            parser.error('audit requires --output')
        audit(args.root, args.output, args.calibration_count, args.seed)


if __name__ == '__main__':
    main()
