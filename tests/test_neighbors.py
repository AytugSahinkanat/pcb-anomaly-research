import unittest
import numpy as np
from pcb_anomaly.neighbors import rank_neighbors


class NeighborTests(unittest.TestCase):
    def test_cross_board_reference_only_and_class_filter(self):
        rows = [dict(sample_id=str(i), category=c, board_group=b, split=s)
                for i, (c,b,s) in enumerate([
                    ('a','query','calibration'), ('a','query','reference'),
                    ('b','other','reference'), ('a','third','reference'),
                    ('a','testboard','test')])]
        features = np.array([[1,0], [1,0], [1,0], [.6,.8], [1,0]])
        result = rank_neighbors(features, rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['unrestricted_top1'], 2)
        self.assertEqual(result[0]['nearest'][0][0], 3)
        self.assertEqual(result[0]['same_category_count'], 1)

    def test_missing_category_is_not_fabricated(self):
        rows = [dict(sample_id='q', category='missing', board_group='q', split='calibration'),
                dict(sample_id='r', category='other', board_group='r', split='reference')]
        result = rank_neighbors(np.array([[1,0],[1,0]]), rows)[0]
        self.assertEqual(result['nearest'], [])
        self.assertIsNone(result['farthest'])
        with self.assertRaises(ValueError):
            rank_neighbors(np.array([[2,0],[1,0]]), rows)
