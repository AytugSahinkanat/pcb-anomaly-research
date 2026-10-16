import unittest
import numpy as np
from pcb_anomaly.scale_bank import collapsed_scores, compare_scores


class ScaleBankTests(unittest.TestCase):
    def test_views_collapse_before_topk(self):
        bank=np.array([[[1.,0.],[0.,1.]],[[.8,.6],[1.,0.]]])
        scores=collapsed_scores(bank,np.array([1.,0.]))
        np.testing.assert_array_equal(scores,[1,1])
        result=compare_scores(scores,scores,[0,1])
        self.assertEqual(result['k'],2)
        self.assertEqual(result['top5_overlap'],1)
        self.assertEqual(result['original_top1'],0)

    def test_class_filter_missing_bank_and_rank_change(self):
        before=np.array([.9,.8,.1]); after=np.array([.2,.8,.9])
        result=compare_scores(before,after,[0,2])
        self.assertFalse(result['top1_retained'])
        self.assertEqual(result['changed_top1'],2)
        self.assertIsNone(compare_scores(before,after,[]))

    def test_invalid_features(self):
        with self.assertRaises(ValueError):
            collapsed_scores(np.zeros((2,2)),np.zeros(2))
        with self.assertRaises(ValueError):
            collapsed_scores(np.full((3,2,2),np.nan),np.zeros(2))
