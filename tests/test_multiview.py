import unittest
import numpy as np
from PIL import Image
from pcb_anomaly.multiview import pool_views, ROTATIONS
from pcb_anomaly.sensitivity import transform


class MultiViewTests(unittest.TestCase):
    def test_mean_then_normalize(self):
        views = np.array([[[1,0]], [[1,0]], [[0,1]], [[0,1]]],dtype=np.float32)
        np.testing.assert_allclose(pool_views(views),[[2**-.5,2**-.5]],atol=1e-7)
        self.assertEqual(pool_views(views).shape,(1,2))

    def test_cyclic_permutation_exactly_preserves_pool(self):
        rng = np.random.default_rng(42)
        views = rng.normal(size=(4,7,512)).astype(np.float32)
        views /= np.linalg.norm(views,axis=2,keepdims=True)
        for offset in range(4):
            np.testing.assert_array_equal(pool_views(views),pool_views(np.roll(views,offset,axis=0)))

    def test_rotated_image_has_same_view_orbit_with_odd_dimensions(self):
        image = Image.fromarray(np.arange(5*8*3,dtype=np.uint8).reshape(5,8,3))
        expected = [transform(image,r).tobytes() for r in ROTATIONS]
        for offset,r in enumerate(ROTATIONS):
            actual = [transform(transform(image,r),s).tobytes() for s in ROTATIONS]
            self.assertEqual(actual,expected[offset:]+expected[:offset])

    def test_invalid_views_are_rejected(self):
        with self.assertRaises(ValueError):
            pool_views(np.ones((3,1,2)))
        with self.assertRaises(ValueError):
            pool_views(np.ones((4,1,2)))
        with self.assertRaises(ValueError):
            pool_views(np.array([[[1,0]],[[-1,0]],[[1,0]],[[-1,0]]]))
