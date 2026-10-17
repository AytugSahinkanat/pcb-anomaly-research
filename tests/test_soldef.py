import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from pcb_anomaly.soldef import audit


class SoldefTests(unittest.TestCase):
    def test_duplicates_and_unlabeled_remain_distinct_concepts(self):
        def encoded(color):
            stream = io.BytesIO()
            Image.new('RGB', (12, 10), color).save(stream, format='JPEG')
            return stream.getvalue()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(root / 'source.zip', 'w') as archive:
                image = encoded('red')
                archive.writestr('SolDef_AI/Dataset/CS1/V1/a.jpg', image)
                archive.writestr('SolDef_AI/Labeled/a.jpg', image)
                archive.writestr('SolDef_AI/Dataset/CS1/V1/unlabeled.jpg', encoded('blue'))
                archive.writestr('SolDef_AI/Labeled/a.json', json.dumps({
                    'imageWidth': 12, 'imageHeight': 10,
                    'shapes': [{'label': 'good', 'shape_type': 'polygon',
                                'points': [[1, 1], [9, 1], [9, 8], [1, 8]]}]}))
            audit(root / 'source.zip', root / 'audit')
            result = json.loads((root / 'audit/audit.json').read_text())
            self.assertEqual(result['image_files'], 3)
            self.assertEqual(result['unique_image_files_by_sha256'], 2)
            self.assertEqual(result['unique_images_without_annotation_by_sha256'], 1)
            record = json.loads((root / 'audit/annotations.jsonl').read_text())
            self.assertEqual(record['split'], 'unassigned')
            self.assertEqual(record['labels'], {'good': 1})
            self.assertEqual(len(record['source_candidates']), 1)
