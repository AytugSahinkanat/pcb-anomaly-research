"""Calibration-only visual retrieval diagnostics; never infer defect labels."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .crops import read_rows, sha256, square_input


def rank_neighbors(features, rows):
    features = np.asarray(features, dtype=np.float32)
    if features.ndim != 2 or len(features) != len(rows) or not np.isfinite(features).all():
        raise ValueError('Invalid feature/sample alignment')
    if len({r['sample_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate sample IDs')
    if not np.allclose(np.linalg.norm(features, axis=1), 1, atol=1e-5):
        raise ValueError('Expected L2-normalized features')
    refs = [i for i, r in enumerate(rows) if r['split'] == 'reference']
    queries = [i for i, r in enumerate(rows) if r['split'] == 'calibration']
    results = []
    for qi in queries:
        q = rows[qi]
        eligible = [i for i in refs if rows[i]['board_group'] != q['board_group']]
        if not eligible:
            continue
        similarity = np.clip(features[eligible] @ features[qi], -1, 1)
        order = np.argsort(-similarity, kind='stable')
        ranked = [(eligible[j], float(similarity[j])) for j in order]
        same = [(i, s) for i, s in ranked if rows[i]['category'] == q['category']]
        results.append(dict(query_index=qi, category=q['category'],
                            unrestricted_top1=ranked[0][0], unrestricted_cosine=ranked[0][1],
                            same_category_count=len(same), nearest=same[:3],
                            farthest=same[-1] if same else None))
    return results


def create_report(feature_dir, crop_dir, output):
    feature_dir, crop_dir, output = map(Path, (feature_dir, crop_dir, output))
    rows = read_rows(feature_dir / 'samples.jsonl')
    if [r['feature_index'] for r in rows] != list(range(len(rows))):
        raise ValueError('Feature indices do not match row order')
    run = json.loads((feature_dir / 'run.json').read_text())
    if run['status'] != 'complete' or sha256(feature_dir / 'features.npy') != run['features_sha256']:
        raise ValueError('Incomplete or modified feature artifact')
    features = np.load(feature_dir / 'features.npy', allow_pickle=False)
    results = rank_neighbors(features, rows)
    output.mkdir(parents=True, exist_ok=False)
    font = ImageFont.load_default(size=15)
    categories = sorted({r['category'] for r in rows})
    summary, pages = [], []
    for number, category in enumerate(categories):
        counts = Counter(r['split'] for r in rows if r['category'] == category)
        matches = [r for r in results if r['category'] == category]
        supported = [r for r in matches if r['nearest']]
        agreement = sum(rows[r['unrestricted_top1']]['category'] == category for r in matches)
        item = dict(category=category, counts=dict(counts), supported_queries=len(supported),
                    unrestricted_top1_agreement=agreement / len(matches) if matches else None)
        if supported:
            ordered = sorted(supported, key=lambda r: r['nearest'][0][1])
            chosen = [ordered[i] for i in sorted({0, len(ordered)//2, len(ordered)-1})]
            item['median_top1_cosine'] = float(np.median([r['nearest'][0][1] for r in supported]))
            item['selected_query_ids'] = [rows[r['query_index']]['sample_id'] for r in chosen]
            canvas = Image.new('RGB', (1500, 310 * len(chosen)), '#eeeeee')
            draw = ImageDraw.Draw(canvas)
            for line, result in enumerate(chosen):
                tiles = [('Query (calibration)', result['query_index'], None)]
                tiles += [(f'Same class #{j+1}', i, score) for j, (i, score) in enumerate(result['nearest'][:2])]
                tiles += [('Same class farthest', *result['farthest']),
                          ('Any class nearest', result['unrestricted_top1'], result['unrestricted_cosine'])]
                for col, (label, index, score) in enumerate(tiles):
                    row = rows[index]
                    path = (crop_dir / row['crop_path']).resolve()
                    if not path.is_relative_to(crop_dir.resolve()) or sha256(path) != row['crop_sha256']:
                        raise ValueError('Crop path/checksum mismatch')
                    with Image.open(path) as image:
                        tile = square_input(image, 200)
                    x, y = col * 300, line * 310
                    canvas.paste(tile, (x+50, y+25))
                    lines = [label, row['sample_id'], row['category'],
                             f"{row['width']}x{row['height']}" + (f' cos={score:.3f}' if score is not None else '')]
                    draw.text((x+5, y+3), lines[0], font=font, fill='black')
                    for k, text in enumerate(lines[1:]):
                        draw.text((x+5, y+230+k*22), text, font=font, fill='black')
            filename = f'{number:02d}.jpg'
            canvas.save(output / filename, quality=92)
            item['sheet'] = filename
            pages.append(f'<h2>{html.escape(category)}</h2><p>Queries: low / median / high nearest similarity (where available).</p><img src="{filename}" loading="lazy" style="max-width:100%">')
        summary.append(item)
    report = dict(protocol='calibration queries -> reference bank; different board_group; test excluded',
                  features_sha256=run['features_sha256'], queries=len(results),
                  supported_queries=sum(bool(r['nearest']) for r in results),
                  unrestricted_top1_agreement=sum(rows[r['unrestricted_top1']]['category'] == r['category'] for r in results)/len(results) if results else None,
                  categories=summary)
    (output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (output / 'neighbors.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in results), encoding='utf-8')
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Component neighbors</title><body style="font-family:system-ui;margin:30px"><h1>Component neighbors</h1><p>Calibration to reference, different boards. Test excluded. Cosine similarity is not defect probability. Category agreement is exploratory, not defect accuracy.</p>'+''.join(pages)+'</body>', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--crops', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create_report(args.features, args.crops, args.output), indent=2))
