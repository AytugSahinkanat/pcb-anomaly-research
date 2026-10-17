import unittest
import numpy as np

from pcb_anomaly.visa_benchmark import ranking_metrics, greedy_coreset, nearest_distances, choose_samples
from pcb_anomaly.benchmark_review import paired_bootstrap


class BenchmarkTests(unittest.TestCase):
    def test_paired_bootstrap_identical_methods_and_alignment(self):
        rows = []
        for category in ('pcb1', 'pcb2', 'pcb3', 'pcb4'):
            for method in ('resnet18_global_knn', 'patchcore_resnet18'):
                for label in (0, 1):
                    rows.append(dict(category=category, method=method, split='test',
                                     image=f'{category}/{label}', label=label, score=float(label)))
        result = paired_bootstrap(rows, iterations=10)
        self.assertEqual(result['macro_auroc_difference_95_percentile_ci'], [0., 0.])
        self.assertEqual(result['macro_ap_difference_95_percentile_ci'], [0., 0.])
        rows[-1]['image'] = 'mismatched'
        with self.assertRaises(ValueError):
            paired_bootstrap(rows, iterations=10)

    def test_ranking_perfect_reverse_and_ties(self):
        self.assertEqual(ranking_metrics([0, 1], [0, 1]), {'auroc': 1., 'average_precision': 1.})
        self.assertEqual(ranking_metrics([0, 1], [1, 0]), {'auroc': 0., 'average_precision': .5})
        self.assertEqual(ranking_metrics([0, 1, 0, 1], [1, 1, 1, 1]), {'auroc': .5, 'average_precision': .5})
        self.assertAlmostEqual(ranking_metrics([1, 0, 1], [3, 2, 1])['average_precision'], 5/6)
        with self.assertRaises(ValueError):
            ranking_metrics([0, 0], [0, 1])

    def test_nearest_matches_brute_force_across_chunks(self):
        rng = np.random.default_rng(1)
        query, bank = rng.normal(size=(19, 7)), rng.normal(size=(13, 7))
        expected = np.linalg.norm(query[:, None]-bank[None, :], axis=-1).min(axis=1)
        np.testing.assert_allclose(nearest_distances(query, bank, 3), expected, rtol=1e-5)

    def test_coreset_is_unique_deterministic_and_covers_extremes(self):
        x = np.arange(20, dtype=np.float32).reshape(-1, 1)
        indices = greedy_coreset(x, 4)
        np.testing.assert_array_equal(indices, greedy_coreset(x, 4))
        self.assertEqual(len(set(indices)), 4)
        # A random initial point near an endpoint need not select that endpoint.
        self.assertLessEqual(np.abs(x-x[indices].T).min(axis=1).max(), 5)
        self.assertIn(19, indices)
        self.assertEqual(len(set(greedy_coreset(np.zeros((5, 2)), 5))), 5)

    def test_reference_selection_ignores_test_scores_and_order(self):
        rows = []
        for category in ('pcb1', 'pcb2', 'pcb3', 'pcb4'):
            for i, split in enumerate(['reference']*4 + ['calibration', 'test']):
                rows.append({'object': category, 'split': split, 'label': 'normal', 'image': f'{category}/{i}'})
        first = choose_samples(rows, count=2)
        second = choose_samples(list(reversed(rows)), count=2)
        self.assertEqual(first, second)
        self.assertTrue(all(sum(r['split'] == 'reference' for r in rs) == 2 for rs in first.values()))
        rows[0]['label'] = 'anomaly'
        with self.assertRaises(ValueError):
            choose_samples(rows, count=2)
