"""Generate local contact sheets for board and sampled-box visual review."""
import argparse
import io
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw, ImageFont
from .crops import read_rows


def make_review(archive, audit, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    images = json.loads((Path(audit) / 'images.json').read_text(encoding='utf-8'))
    rows = [r for r in read_rows(Path(audit) / 'manifest.jsonl') if r['crop_eligible']]
    font = ImageFont.load_default(size=16)
    selected = []
    with zipfile.ZipFile(archive) as source:
        for page_start in range(0, len(images), 12):
            canvas = Image.new('RGB', (1600, 1200), '#eeeeee')
            draw = ImageDraw.Draw(canvas)
            for j, rec in enumerate(images[page_start:page_start + 12]):
                with Image.open(io.BytesIO(source.read(rec['image_path']))) as original:
                    image = original.convert('RGB')
                image.thumbnail((390, 340))
                x, y = j % 4 * 400, j // 4 * 400
                canvas.paste(image, (x + (400 - image.width) // 2, y + 35))
                draw.text((x + 5, y + 5), rec['image_id'], fill='black', font=font)
                draw.text((x + 5, y + 375), f"{rec['width']} x {rec['height']}", fill='black', font=font)
                candidates = [r for r in rows if r['image_id'] == rec['image_id']]
                candidates.sort(key=lambda r: (r['bbox'][2] - r['bbox'][0]) * (r['bbox'][3] - r['bbox'][1]))
                if candidates:
                    selected.extend(candidates[i] for i in sorted({0, len(candidates) // 2, len(candidates) - 1}))
            canvas.save(output / f'boards-{page_start // 12 + 1}.jpg')
        for page_start in range(0, len(selected), 24):
            canvas = Image.new('RGB', (1600, 1440), '#eeeeee')
            draw = ImageDraw.Draw(canvas)
            for j, row in enumerate(selected[page_start:page_start + 24]):
                with Image.open(io.BytesIO(source.read(row['image_path']))) as original:
                    image = original.convert('RGB')
                x0, y0, x1, y1 = row['bbox']
                width, height = x1 - x0, y1 - y0
                pad = max(10, int(max(width, height) * .2))
                left, top = max(0, x0 - pad), max(0, y0 - pad)
                patch = image.crop((left, top, min(image.width, x1 + pad), min(image.height, y1 + pad)))
                ImageDraw.Draw(patch).rectangle((x0 - left, y0 - top, x1 - left - 1, y1 - top - 1), outline='red', width=max(1, round(max(patch.size) / 150)))
                patch.thumbnail((380, 180))
                x, y = j % 4 * 400, j // 4 * 240
                canvas.paste(patch, (x + (400 - patch.width) // 2, y + 40))
                draw.text((x + 5, y + 2), row['sample_id'], fill='black', font=font)
                draw.text((x + 5, y + 22), f"{row['category']} {width}x{height}", fill='black', font=font)
            canvas.save(output / f'boxes-{page_start // 24 + 1}.jpg')
    (output / 'sampled-boxes.json').write_text(json.dumps([r['sample_id'] for r in selected], indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    make_review(args.archive, args.audit, args.output)
