"""Lossless, manifest-aligned component crops. No labels are inferred."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def square_input(image, size=224):
    """Center-pad RGB with rounded ImageNet mean; resize without truncation."""
    image = image.convert('RGB')
    side = max(image.size)
    canvas = Image.new('RGB', (side, side), (124, 116, 104))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas.resize((size, size), Image.Resampling.BILINEAR)


def extract_crops(archive, manifest, output):
    rows = [r for r in read_rows(manifest) if r['crop_eligible']]
    if not rows or len({r['sample_id'] for r in rows}) != len(rows):
        raise ValueError('Require nonempty unique sample IDs')
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row['image_path']].append((index, row))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'images').mkdir()
    result = [None] * len(rows)
    flags = Counter()
    duplicates = defaultdict(list)
    with zipfile.ZipFile(archive) as source:
        for member, items in grouped.items():
            with Image.open(io.BytesIO(source.read(member))) as original:
                image = original.convert('RGB')
            for index, row in items:
                x0, y0, x1, y1 = row['bbox']
                if not all(type(v) is int for v in row['bbox']) or not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
                    raise ValueError(f"Invalid bbox: {row['sample_id']}")
                crop = image.crop((x0, y0, x1, y1))
                name = hashlib.sha256(row['sample_id'].encode()).hexdigest() + '.png'
                relative = 'images/' + name
                crop.save(output / relative)
                quality = []
                if min(crop.size) < 16:
                    quality.append('min_side_lt_16')
                if max(crop.size) / min(crop.size) > 5:
                    quality.append('aspect_ratio_gt_5')
                flags.update(quality)
                pixel_hash = hashlib.sha256(str(crop.size).encode() + crop.tobytes()).hexdigest()
                duplicates[pixel_hash].append(row['sample_id'])
                result[index] = dict(row, crop_path=relative, width=crop.width, height=crop.height,
                                     crop_sha256=sha256(output / relative), pixel_sha256=pixel_hash,
                                     quality_flags=quality)
    (output / 'manifest.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in result), encoding='utf-8')
    report = dict(status='complete', count=len(result), archive_sha256=sha256(archive),
                  source_manifest_sha256=sha256(manifest), crop_policy='RGB; exact half-open bbox; no padding or resizing',
                  quality_flags=dict(flags), split_counts=dict(Counter(r['split'] for r in result)),
                  exact_pixel_duplicate_groups=[ids for ids in duplicates.values() if len(ids) > 1])
    (output / 'run.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(extract_crops(args.archive, args.manifest, args.output), indent=2))


if __name__ == '__main__':
    main()
