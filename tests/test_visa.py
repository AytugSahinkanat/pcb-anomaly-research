import csv
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from pcb_anomaly.visa import audit, partition, safe_path


def row(name, split='train', label='normal'):
    return {'object': 'pcb1', 'split': split, 'label': label,
            'image': f'pcb1/{name}.png',
            'mask': f'pcb1/{name}_mask.png' if label == 'anomaly' else ''}


class VisaTests(unittest.TestCase):
    def test_holdout_preserves_test_and_is_order_independent(self):
        rows = [row(str(i)) for i in range(5)] + [row('bad', 'test', 'anomaly')]
        first = partition(rows, 2)
        second = partition(list(reversed(rows)), 2)
        self.assertEqual({r['image']: r['split'] for r in first},
                         {r['image']: r['split'] for r in second})
        self.assertEqual(sum(r['split'] == 'calibration' for r in first), 2)
        self.assertEqual(first[-1]['split'], 'test')
        self.assertTrue(all(r['label'] == 'normal' for r in first if r['split'] != 'test'))
        self.assertEqual(rows[0]['split'], 'train')

    def test_rejects_leakage_and_invalid_labels(self):
        for rows in ([row('a'), row('a', 'test')],
                     [row('a', 'train', 'anomaly')],
                     [dict(row('a'), mask='unexpected.png')]):
            with self.assertRaises(ValueError):
                partition(rows, 1)

    def test_rejects_escaping_paths(self):
        for name in ('../escape', '/absolute', 'C:/escape', 'pcb1\\escape'):
            with self.assertRaises(ValueError):
                safe_path(Path('.'), name)

    def test_mask_audit_and_pixel_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'pcb1').mkdir()
            (root / 'acquisition.json').write_text(json.dumps({'status': 'complete'}))
            rows = [row('a'), row('b'), row('c', 'test', 'anomaly')]
            with (root / '1cls.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
            for i, r in enumerate(rows):
                Image.new('RGB', (6, 4), (i * 50, 0, 0)).save(root / r['image'])
            mask_path = root / rows[-1]['mask']
            Image.new('L', (6, 4), 0).save(mask_path)
            with self.assertRaisesRegex(ValueError, 'Empty anomaly mask'):
                audit(root, root / 'empty', 1)
            Image.new('L', (3, 2), 1).save(mask_path)
            with self.assertRaisesRegex(ValueError, 'geometry mismatch'):
                audit(root, root / 'mismatch', 1)
            Image.new('L', (6, 4), 2).save(mask_path)
            audit(root, root / 'valid', 1)
            manifest = [json.loads(s) for s in (root / 'valid/manifest.jsonl').read_text().splitlines()]
            self.assertEqual(manifest[-1]['defect_pixels'], 24)
            self.assertEqual(manifest[-1]['mask_values'], [2])
            Image.open(root / rows[0]['image']).save(root / rows[-1]['image'])
            with self.assertRaisesRegex(ValueError, 'duplicates cross'):
                audit(root, root / 'duplicate', 1)
