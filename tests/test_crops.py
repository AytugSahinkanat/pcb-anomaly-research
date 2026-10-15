import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from pcb_anomaly.crops import extract_crops, read_rows, sha256, square_input


class CropTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = Image.new('RGB', (8, 6))
        for x in range(8):
            for y in range(6):
                image.putpixel((x, y), (x * 20, y * 30, 0))
        self.image = image
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        self.archive = self.root / 'source.zip'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('board.png', buffer.getvalue())
        self.rows = [dict(sample_id=f'board:{i}', image_path='board.png', bbox=[1, 2, 5, 6],
                          category='resistor', refdes='R1', board_group='board', split='reference',
                          label=None, label_source='unlabeled', crop_eligible=True) for i in range(2)]
        self.manifest = self.root / 'manifest.jsonl'

    def write_manifest(self):
        self.manifest.write_text(''.join(json.dumps(r) + '\n' for r in self.rows), encoding='utf-8')

    def test_coordinates_repeated_refdes_and_alignment(self):
        self.write_manifest()
        out = self.root / 'crops'
        report = extract_crops(self.archive, self.manifest, out)
        rows = read_rows(out / 'manifest.jsonl')
        self.assertEqual([r['sample_id'] for r in rows], ['board:0', 'board:1'])
        self.assertNotEqual(rows[0]['crop_path'], rows[1]['crop_path'])
        with Image.open(out / rows[0]['crop_path']) as crop:
            self.assertEqual(crop.size, (4, 4))
            self.assertEqual(crop.tobytes(), self.image.crop((1, 2, 5, 6)).tobytes())
        self.assertIsNone(rows[0]['label'])
        self.assertEqual(rows[0]['crop_sha256'], sha256(out / rows[0]['crop_path']))
        self.assertEqual(report['exact_pixel_duplicate_groups'], [['board:0', 'board:1']])
        with self.assertRaises(FileExistsError):
            extract_crops(self.archive, self.manifest, out)

    def test_duplicate_ids_rejected(self):
        self.rows[1]['sample_id'] = self.rows[0]['sample_id']
        self.write_manifest()
        with self.assertRaises(ValueError):
            extract_crops(self.archive, self.manifest, self.root / 'crops')

    def test_out_of_bounds_is_not_silently_padded(self):
        self.rows[0]['bbox'] = [-1, 0, 5, 6]
        self.write_manifest()
        with self.assertRaises(ValueError):
            extract_crops(self.archive, self.manifest, self.root / 'crops')
        self.assertFalse((self.root / 'crops/run.json').exists())

    def test_square_preserves_entire_long_component(self):
        image = Image.new('RGB', (12, 2), 'red')
        image.putpixel((0, 0), (0, 255, 0))
        image.putpixel((11, 1), (0, 0, 255))
        result = square_input(image, 12)
        self.assertEqual(result.getpixel((0, 5)), (0, 255, 0))
        self.assertEqual(result.getpixel((11, 6)), (0, 0, 255))
        self.assertEqual(result.getpixel((0, 0)), (124, 116, 104))
