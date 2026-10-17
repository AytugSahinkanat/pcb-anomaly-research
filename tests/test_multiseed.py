import unittest

from pcb_anomaly.multiseed import SEEDS
from pcb_anomaly.multiseed_report import aggregate, METHODS, prediction_stability
from pcb_anomaly.visa import CATEGORIES
from pcb_anomaly.visa_benchmark import choose_samples


class MultiseedTests(unittest.TestCase):
    def test_persistent_errors_do_not_count_five_times(self):
        rows=[dict(method=METHODS[0],image='a',category='pcb1',split='test',label=1,
                   reference_seed=seed,prediction=0) for seed in SEEDS]
        result=prediction_stability(rows)['summary'][METHODS[0]]
        self.assertEqual(result['persistently_missed_defects'],1)
        self.assertEqual(result['unstable_defects'],0)
        rows[-1]['prediction']=1
        self.assertEqual(prediction_stability(rows)['summary'][METHODS[0]]['unstable_defects'],1)
        with self.assertRaises(ValueError): prediction_stability(rows[:-1])

    def test_reference_seeds_change_selection_not_queries(self):
        rows=[]
        for c in CATEGORIES:
            for i in range(100):
                rows.append(dict(object=c,image=f'{c}/{i}',split='reference' if i<90 else 'calibration',label='normal'))
            rows.append(dict(object=c,image=f'{c}/bad',split='test',label='anomaly'))
        selections=[choose_samples(rows,seed=s) for s in SEEDS]
        for c in CATEGORIES:
            query_ids=[[r['image'] for r in g[c] if r['split']!='reference'] for g in selections]
            self.assertTrue(all(q==query_ids[0] for q in query_ids))
            refs=[frozenset(r['image'] for r in g[c] if r['split']=='reference') for g in selections]
            self.assertEqual(len(set(refs)),5)

    def test_summary_uses_seeds_not_pooled_repeated_test_images(self):
        rows=[]
        for m in METHODS:
            for s in SEEDS:
                for c in CATEGORIES:
                    rows.append(dict(method=m,reference_seed=s,category=c,tp=50,fn=50,
                                     fp=5,tn=95+(c in ('pcb3','pcb4')),auroc=.8,average_precision=.7))
        result=aggregate(rows)
        self.assertEqual(len(result['per_seed']),15)
        self.assertEqual(result['summary'][METHODS[0]]['tp']['mean'],200)
        self.assertEqual(result['summary'][METHODS[0]]['tp']['sd'],0)
        with self.assertRaises(ValueError): aggregate(rows[:-1])
        with self.assertRaises(ValueError): aggregate(rows+[rows[0]])
