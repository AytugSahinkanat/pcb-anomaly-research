import unittest
import numpy as np
from pcb_anomaly.evaluation import (
    Split, validate_splits, knn_scores, calibrate_threshold,
    binary_metrics, l2_normalize,
)


class EvaluationTests(unittest.TestCase):
    def test_board_leakage_despite_different_crops(self):
        with self.assertRaisesRegex(ValueError, "Board leakage"):
            validate_splits(Split(("crop1",), ("boardA",)),
                            Split(("crop2",), ("boardB",)),
                            Split(("crop3",), ("boardA",)))

    def test_valid_splits_and_empty_test(self):
        a, b, c = [Split((f"s{i}",), (f"b{i}",)) for i in range(3)]
        validate_splits(a, b, c)
        with self.assertRaises(ValueError):
            validate_splits(a, b, Split((), ()))

    def test_self_exclusion_keeps_other_identical_features(self):
        scores = knn_scores([[0], [0], [3]], [[0]], k=2,
                            reference_ids=["a", "b", "c"], query_ids=["a"])
        np.testing.assert_allclose(scores, [1.5])

    def test_knn_matches_hand_computation(self):
        scores = knn_scores([[0], [2], [5]], [[1], [4]], k=2,
                            reference_ids=["a", "b", "c"],
                            query_ids=["x", "y"], batch_size=1)
        np.testing.assert_allclose(scores, [1, 1.5])

    def test_small_bank_and_alignment(self):
        with self.assertRaises(ValueError):
            knn_scores([[1]], [[1]], k=1, reference_ids=["a"], query_ids=["a"])
        with self.assertRaises(ValueError):
            knn_scores([[1]], [[2]], k=1, reference_ids=[], query_ids=["b"])

    def test_invalid_features(self):
        for x in ([[0, 0]], [[float("nan"), 1]]):
            with self.assertRaises(ValueError):
                l2_normalize(x)
        np.testing.assert_allclose(l2_normalize([[3, 4]]), [[0.6, 0.8]])

    def test_calibration_and_independent_metrics(self):
        threshold = calibrate_threshold([1, 2, 3, 4], quantile=0.75)
        self.assertEqual(threshold, 4)
        metrics = binary_metrics([0, 0, 1, 1], [1, 5, 3, 6], threshold=threshold,
                                 label_source="independent_annotation")
        self.assertEqual((metrics['tp'], metrics['fp'], metrics['fn'], metrics['tn']),
                         (1, 1, 1, 1))
        self.assertEqual(metrics['f1'], 0.5)
        with self.assertRaises(ValueError):
            binary_metrics([0, 1], [1, 5], threshold=4, label_source="score_threshold")


if __name__ == "__main__":
    unittest.main()
