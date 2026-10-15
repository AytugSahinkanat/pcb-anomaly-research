import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from pcb_anomaly.data import parse_label, board_group, match_image, convert_bbox, audit, propose_splits


class DataTests(unittest.TestCase):
    def test_quoted_class_and_text(self):
        self.assertEqual(parse_label('"electrolytic capacitor" C1'), ('electrolytic capacitor', 'C1'))
        self.assertEqual(parse_label('"component text" "MAX E"'), ('component text', 'MAX E'))
        with self.assertRaises(ValueError):
            parse_label('"unfinished')

    def test_board_views_stay_together_without_substring_matching(self):
        self.assertEqual(board_group('ML450_Bottom2'), ('ML450', 'bottom'))
        self.assertNotEqual(board_group('Spartan6_Top')[0], board_group('Spartan6Redux_Top')[0])

    def test_uppercase_extension_and_filename_priority(self):
        names = ['dataset/A/A.JPG', 'dataset/A/A.png']
        self.assertEqual(match_image('dataset/A/A.xml', 'A.jpg', names)[0], names[0])
        with self.assertRaises(ValueError):
            match_image('dataset/A/A.xml', 'missing.jpg', names)

    def test_voc_conversion_and_invalid_bounds(self):
        self.assertEqual(convert_bbox([1, 1, 10, 5], 10, 5), (0, 0, 10, 5))
        self.assertEqual(convert_bbox([3, 2, 3, 2], 10, 5), (2, 1, 3, 2))
        for box in ([0, 1, 2, 2], [1, 1, 11, 3], [3, 2, 2, 3]):
            with self.assertRaises(ValueError):
                convert_bbox(box, 10, 5)

    def test_audit_preserves_duplicate_named_components(self):
        image = io.BytesIO()
        Image.new('RGB', (10, 5)).save(image, format='JPEG')
        obj = '<object><name>capacitor C1</name><bndbox><xmin>1</xmin><ymin>1</ymin><xmax>3</xmax><ymax>3</ymax></bndbox></object>'
        xml = '<annotation><filename>A.JPG</filename><size><width>10</width><height>5</height></size>' + obj*2 + '</annotation>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'data.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('A/A.JPG', image.getvalue())
                z.writestr('A/A.xml', xml)
            rows, images, summary = audit(path)
        self.assertEqual(summary['eligible_components'], 2)
        self.assertNotEqual(rows[0]['sample_id'], rows[1]['sample_id'])
        self.assertIsNone(rows[0]['label'])
        self.assertIn('repeated_raw_label', rows[1]['issues'])

    def test_splits_are_order_independent_and_nonempty(self):
        rows = [{'board_group': str(i), 'crop_eligible': True} for i in range(10)]
        a = propose_splits(rows)
        self.assertEqual(a, propose_splits(list(reversed(rows))))
        self.assertEqual(set(a['assignments'].values()), {'reference', 'calibration', 'test'})
        with self.assertRaises(ValueError):
            propose_splits(rows[:2])


if __name__ == '__main__':
    unittest.main()
