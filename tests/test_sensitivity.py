import unittest
import numpy as np
from PIL import Image
from pcb_anomaly.sensitivity import transform, compare_neighbors, aggregate


class SensitivityTests(unittest.TestCase):
    def test_rotation_preserves_pixels_and_full_extent(self):
        image = Image.new('RGB', (3, 2))
        image.putpixel((0, 0), (255, 0, 0))
        image.putpixel((2, 1), (0, 255, 0))
        rotated = transform(image, 'rot90')
        self.assertEqual(rotated.size, (2, 3))
        self.assertEqual(rotated.getpixel((0, 2)), (255, 0, 0))
        self.assertEqual(rotated.getpixel((1, 0)), (0, 255, 0))
        self.assertEqual(transform(transform(image, 'rot90'), 'rot270').tobytes(), image.tobytes())

    def test_native_resolution_rounding_and_minimum(self):
        image = Image.new('RGB', (7, 2), 'red')
        self.assertEqual(transform(image, 'down50').size, (4, 1))
        self.assertEqual(transform(image, 'down25').size, (2, 1))
        self.assertEqual(transform(image, 'identity').tobytes(), image.tobytes())
        with self.assertRaises(ValueError):
            transform(image, 'unsupported')

    def test_ranking_change_and_small_bank_denominator(self):
        bank = np.array([[1.,0.], [0.,1.], [-1.,0.]])
        metric = compare_neighbors(bank, bank[0], bank[1], [0,1])
        self.assertFalse(metric['top1_retained'])
        self.assertEqual(metric['top5_overlap'], 1)
        self.assertEqual(metric['k'], 2)
        self.assertEqual(metric['original_top1'], 0)
        self.assertEqual(metric['changed_top1'], 1)
        self.assertEqual(metric['top1_cosine_delta'], 0)
        self.assertIsNone(compare_neighbors(bank, bank[0], bank[1], []))

    def test_identity_and_ties_have_stable_order(self):
        bank = np.array([[1.,0.], [1.,0.]])
        metric = compare_neighbors(bank, bank[0], bank[0], [1,0])
        self.assertEqual(metric['original_top1'], 1)
        self.assertTrue(metric['top1_retained'])
        result = aggregate([dict(embedding_cosine=1., same_category=None,
                                 unrestricted=metric, category_agreement=True)])
        self.assertEqual(result['same_category']['n'], 0)
        self.assertEqual(result['unrestricted']['top5_overlap'], 1)
