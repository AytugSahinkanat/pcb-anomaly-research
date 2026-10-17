"""Inventory SolDef_AI without treating unlabeled images as defect-free."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .crops import sha256

URL = 'https://www.kaggle.com/api/v1/datasets/download/mauriziocalabrese/soldef-ai-pcb-dataset-for-defect-detection'


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
        'sha256': sha256(root / 'archive.zip')}, indent=2))


def audit(path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    labels, shapes, issues = Counter(), Counter(), []
    records, labeled_hashes = [], set()
    by_name, by_hash = defaultdict(list), defaultdict(list)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP member names')
        # Full reads validate CRC; compare file hashes across duplicated folders.
        for name in names:
            if name.lower().endswith(('.jpg', '.jpeg', '.png')):
                digest = hashlib.sha256(archive.read(name)).hexdigest()
                by_hash[digest].append(name)
                by_name[PurePosixPath(name).name].append((name, digest))
        for name in names:
            if not name.endswith('.json'):
                continue
            annotation = json.loads(archive.read(name))
            image_name = str(PurePosixPath(name).with_suffix('.jpg'))
            if image_name not in names:
                issues.append({'annotation': name, 'issue': 'missing_paired_image'})
                continue
            with Image.open(io.BytesIO(archive.read(image_name))) as source:
                width, height = source.size
                source.verify()
            if (annotation.get('imageWidth'), annotation.get('imageHeight')) != (width, height):
                issues.append({'annotation': name, 'issue': 'geometry_mismatch'})
            label_counts = Counter()
            for shape in annotation['shapes']:
                label_counts[shape['label']] += 1
                shapes[shape['shape_type']] += 1
                points = np.asarray(shape['points'], dtype=float)
                if (points.ndim != 2 or points.shape[1] != 2 or len(points) < 3
                        or not np.isfinite(points).all()):
                    issues.append({'annotation': name, 'issue': 'invalid_polygon'})
                elif ((points[:, 0] < 0).any() or (points[:, 0] > width).any()
                      or (points[:, 1] < 0).any() or (points[:, 1] > height).any()):
                    issues.append({'annotation': name, 'issue': 'polygon_outside_image'})
            labels.update(label_counts)
            matching = by_name[PurePosixPath(image_name).name]
            digest = next(digest for candidate, digest in matching if candidate == image_name)
            labeled_hashes.add(digest)
            records.append({'image': image_name, 'annotation': name, 'width': width, 'height': height,
                            'labels': dict(label_counts), 'sha256': digest,
                            'source_candidates': [n for n, h in matching if '/Dataset/' in n and h == digest],
                            'split': 'unassigned'})
        summary = {'status': 'audited_not_split', 'archive_sha256': sha256(path),
                   'image_files': sum(len(v) for v in by_hash.values()),
                   'unique_image_files_by_sha256': len(by_hash), 'annotation_files': len(records),
                   'unique_annotated_images_by_sha256': len(labeled_hashes),
                   'unique_images_without_annotation_by_sha256': len(set(by_hash) - labeled_hashes),
                   'shape_labels': dict(labels), 'shape_types': dict(shapes), 'issues': issues,
                   'annotated_images_without_unique_source': sum(len(r['source_candidates']) != 1 for r in records),
                   'policy': 'No binary labels or splits inferred. Unlabeled is not normal. Multi-view source grouping requires review.'}
        (output / 'audit.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        (output / 'annotations.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
        # First representative of each raw annotation label; no model-based selection.
        selected = [next(r for r in records if label in r['labels']) for label in sorted(labels)]
        canvas = Image.new('RGB', (900, 300 * ((len(selected)+1)//2)), 'white')
        draw = ImageDraw.Draw(canvas)
        for index, (label, record) in enumerate(zip(sorted(labels), selected)):
            image = Image.open(io.BytesIO(archive.read(record['image']))).convert('RGB')
            annotation = json.loads(archive.read(record['annotation']))
            overlay = ImageDraw.Draw(image)
            for shape in annotation['shapes']:
                if shape['label'] == label:
                    overlay.line([tuple(p) for p in shape['points']] + [tuple(shape['points'][0])],
                                 fill='red', width=5)
            tile = ImageOps.contain(image, (440, 265))
            x, y = (index % 2)*450, (index // 2)*300
            canvas.paste(tile, (x, y+30)); draw.text((x+8, y+8), label, fill='black')
        canvas.save(output / 'annotation-review.jpg', quality=92)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('acquire', 'audit'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'acquire':
        acquire(args.root)
    elif args.output is None:
        parser.error('audit requires --output')
    else:
        audit(args.root / 'archive.zip', args.output)


if __name__ == '__main__':
    main()
