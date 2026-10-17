import unittest
from itertools import product

from pcb_anomaly.controlled import BACKBONES, PREPROCESSING, BUDGETS, configuration
from pcb_anomaly.controlled_report import aggregate
from pcb_anomaly.multiseed import SEEDS
from pcb_anomaly.visa import CATEGORIES


class ControlledTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for model,prep,budget,seed,category in product(BACKBONES,PREPROCESSING,BUDGETS,SEEDS,CATEGORIES):
            # Shared reference-selection difficulty should cancel in paired contrasts.
            auc=.7+.01*(seed-42)+.05*(model=='wrn50')+.02*(prep=='crop')+.01*(budget==5017)
            rows.append(dict(method=configuration(model,prep,budget),reference_seed=seed,category=category,
                             auroc=auc,average_precision=auc,recall=.5,fpr=5/(100+(category in ('pcb3','pcb4'))),
                             tp=50,fn=50,fp=5,tn=95+(category in ('pcb3','pcb4'))))
        return rows

    def test_paired_contrasts_cancel_shared_seed_variation(self):
        result=aggregate(self.rows())
        self.assertEqual(len(result['per_seed']),40)
        for contrast in result['contrasts']:
            expected={'backbone':.05,'preprocessing':.02,'memory':.01}[contrast['name']]
            self.assertAlmostEqual(contrast['delta']['auroc']['mean'],expected)
            self.assertAlmostEqual(contrast['delta']['auroc']['sd'],0)
        for interaction in result['interactions']:
            self.assertAlmostEqual(interaction['delta']['auroc']['mean'],0)

    def test_rejects_missing_duplicate_and_bad_sample_counts(self):
        rows=self.rows()
        with self.assertRaises(ValueError): aggregate(rows[:-1])
        with self.assertRaises(ValueError): aggregate(rows+[rows[0]])
        rows[0]['tn']+=1
        with self.assertRaises(ValueError): aggregate(rows)

    def test_no_pooling_repeats_as_independent_samples(self):
        result=aggregate(self.rows())
        for r in result['per_seed']:
            self.assertEqual(r['tp']+r['fn'],400)
            self.assertEqual(r['fp']+r['tn'],402)
            self.assertAlmostEqual(r['fpr'],20/402)
