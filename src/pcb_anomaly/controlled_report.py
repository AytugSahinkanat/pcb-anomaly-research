"""Validate and summarize the matched PatchCore factorial experiment."""
import argparse
from itertools import product
import json
from pathlib import Path

import numpy as np

from .controlled import BACKBONES, PREPROCESSING, BUDGETS, atomic_json, configuration
from .crops import read_rows, sha256
from .multiseed import SEEDS
from .visa import CATEGORIES
from .evaluation import binary_metrics, calibrate_threshold
from .visa_benchmark import ranking_metrics

METRICS=('auroc','ap','sensitivity','fpr')


def stats(values):
    values=np.asarray(values,dtype=float)
    return dict(mean=float(values.mean()),sd=float(values.std(ddof=1)),min=float(values.min()),max=float(values.max()))


def aggregate(rows):
    methods=[configuration(*v) for v in product(BACKBONES,PREPROCESSING,BUDGETS)]
    keys=[(r['method'],r['reference_seed'],r['category']) for r in rows]
    expected=set(product(methods,SEEDS,CATEGORIES))
    if len(keys)!=len(set(keys)) or set(keys)!=expected: raise ValueError('Require 160 unique results')
    per_seed=[]
    for method,seed in product(methods,SEEDS):
        group=[r for r in rows if r['method']==method and r['reference_seed']==seed]
        counts={k:sum(r[k] for r in group) for k in ('tp','fp','tn','fn')}
        if counts['tp']+counts['fn']!=400 or counts['fp']+counts['tn']!=402: raise ValueError('Unexpected test counts')
        per_seed.append(dict(method=method,reference_seed=seed,
                             auroc=float(np.mean([r['auroc'] for r in group])),
                             ap=float(np.mean([r['average_precision'] for r in group])),
                             sensitivity=counts['tp']/400,fpr=counts['fp']/402,**counts))
    summary={m:{k:stats([r[k] for r in per_seed if r['method']==m]) for k in METRICS} for m in methods}
    indexed={(r['method'],r['reference_seed']):r for r in per_seed}
    def contrast(name, left, right):
        differences={k:[indexed[(right,s)][k]-indexed[(left,s)][k] for s in SEEDS] for k in METRICS}
        return dict(name=name,left=left,right=right,delta={k:stats(v) for k,v in differences.items()},paired_differences=differences)
    contrasts=[]
    for prep,b in product(PREPROCESSING,BUDGETS):
        contrasts.append(contrast('backbone',configuration('rn18',prep,b),configuration('wrn50',prep,b)))
    for model,b in product(BACKBONES,BUDGETS):
        contrasts.append(contrast('preprocessing',configuration(model,'square',b),configuration(model,'crop',b)))
    for model,prep in product(BACKBONES,PREPROCESSING):
        contrasts.append(contrast('memory',configuration(model,prep,501),configuration(model,prep,5017)))
    interactions=[]
    for prep in PREPROCESSING:
        values={k:[] for k in METRICS}
        for seed in SEEDS:
            for k in METRICS:
                gain=lambda b: indexed[(configuration('wrn50',prep,b),seed)][k]-indexed[(configuration('rn18',prep,b),seed)][k]
                values[k].append(gain(5017)-gain(501))
        interactions.append(dict(name='backbone x memory',preprocessing=prep,delta={k:stats(v) for k,v in values.items()}))
    for budget in BUDGETS:
        values={k:[] for k in METRICS}
        for seed in SEEDS:
            for k in METRICS:
                gain=lambda prep: indexed[(configuration('wrn50',prep,budget),seed)][k]-indexed[(configuration('rn18',prep,budget),seed)][k]
                values[k].append(gain('crop')-gain('square'))
        interactions.append(dict(name='backbone x preprocessing',budget=budget,delta={k:stats(v) for k,v in values.items()}))
    for model in BACKBONES:
        values={k:[] for k in METRICS}
        for seed in SEEDS:
            for k in METRICS:
                gain=lambda prep: indexed[(configuration(model,prep,5017),seed)][k]-indexed[(configuration(model,prep,501),seed)][k]
                values[k].append(gain('crop')-gain('square'))
        interactions.append(dict(name='memory x preprocessing',backbone=model,delta={k:stats(v) for k,v in values.items()}))
    category_summary={m:{c:{k:stats([r[k] for r in rows if r['method']==m and r['category']==c])
                           for k in ('auroc','average_precision','recall','fpr')}
                        for c in CATEGORIES} for m in methods}
    return dict(summary=summary,per_seed=per_seed,contrasts=contrasts,interactions=interactions,per_category=rows,
                category_summary=category_summary,
                interpretation='Mean and sample SD across five fixed reference selections, not CI; 802 reused test images; paired deltas right minus left.')


def report(output, audit, previous):
    output,audit,previous=map(Path,(output,audit,previous))
    run=json.loads((output/'run.json').read_text())
    if run['status']!='complete': raise ValueError('Study incomplete')
    prefix=json.loads((output/'prefix-check.json').read_text())
    if not prefix['passed'] or prefix['small']!=prefix['large'][:len(prefix['small'])]:
        raise ValueError('Coreset prefix check failed')
    plan=json.loads((output/'plan.json').read_text())
    if sha256(output/'plan.json')!=run['plan_sha256'] or sha256(audit/'manifest.jsonl')!=plan['manifest_sha256']:
        raise ValueError('Provenance mismatch')
    old_run=json.loads((previous/'wrn/run.json').read_text())
    if (old_run['status']!='complete' or old_run['plan_sha256']!=plan['previous_plan_sha256']
            or old_run['weights_sha256']!=plan['weights_sha256']['wide_resnet50_2-95faca4d.pth']):
        raise ValueError('Reused run provenance mismatch')
    manifest=read_rows(audit/'manifest.jsonl'); rows=[]; errors=[]; reused=0; predictions={}
    for model,prep,category,seed,budget in product(BACKBONES,PREPROCESSING,CATEGORIES,SEEDS,BUDGETS):
        blob=json.loads((output/f'{model}_{prep}/{category}/seed{seed}-{budget}.json').read_text())
        r=blob['result']; scores=blob['scores']
        if (r['method'],r['category'],r['reference_seed'])!=(configuration(model,prep,budget),category,seed): raise ValueError('Mislabeled result')
        expected={x['image']:(x['split'],int(x['is_anomaly'])) for x in manifest if x['object']==category and x['split'] in ('calibration','test')}
        actual={x['image']:(x['split'],x['label']) for x in scores}
        if len(actual)!=len(scores) or actual!=expected: raise ValueError('Query alignment mismatch')
        if set(plan['selection'][str(seed)][category])&set(actual): raise ValueError('Reference leakage')
        threshold=calibrate_threshold([x['score'] for x in scores if x['split']=='calibration'])
        if threshold!=r['threshold']: raise ValueError('Calibration mismatch')
        test=[x for x in scores if x['split']=='test']; labels=[x['label'] for x in test]; values=[x['score'] for x in test]
        metrics=binary_metrics(labels,values,threshold=threshold,label_source='independent_annotation')
        metrics.update(ranking_metrics(labels,values))
        for k,v in metrics.items():
            if isinstance(v,(float,int)) and not np.isclose(v,r[k],rtol=0,atol=1e-12): raise ValueError('Metric mismatch')
        if any(x['prediction']!=int(x['score']>threshold) for x in scores): raise ValueError('Decision mismatch')
        if blob['bank_bytes']!=budget*1024*4 or blob['bank_shape']!=[budget,1024]: raise ValueError('Unequal memory')
        errors.append(blob['parity_error']); reused+=blob['source']=='prior study'; rows.append(r)
        predictions[(model,prep,category,seed,budget)]={x['image']:x['score'] for x in scores}
    monotonic_checks=0
    for model,prep,category,seed in product(BACKBONES,PREPROCESSING,CATEGORIES,SEEDS):
        small=predictions[(model,prep,category,seed,501)]
        large=predictions[(model,prep,category,seed,5017)]
        for image,value in small.items():
            if large[image]>value+1e-4*(1+abs(value)): raise ValueError('Larger nested bank increased nearest-neighbor score')
            monotonic_checks+=1
    result=aggregate(rows)
    old=json.loads((previous/'comparison.json').read_text())
    # A bridge measures the implementation/dimension/sampling bundle, not one isolated algorithmic change.
    bridge=[]
    for seed in SEEDS:
        a=next(r for r in old['per_seed'] if r['method']=='patchcore_resnet18' and r['reference_seed']==seed)
        b=next(r for r in result['per_seed'] if r['method']=='rn18_square_501' and r['reference_seed']==seed)
        bridge.append({k:b[k]-a[k] for k in METRICS})
    result['historical_bridge']=dict(description='Upstream RN18 square501 minus previous custom RN18 square501; embedding/aggregation/sampler/distance bundle changes; bank bytes also change 384D to1024D',
                                      delta={k:stats([r[k] for r in bridge]) for k in METRICS})
    result['verification']=dict(evaluations=len(rows),new_evaluations=160-reused,reused_evaluations=reused,
                                max_full_predict_parity_error=max(errors),manifest_sha256=plan['manifest_sha256'],
                                plan_sha256=sha256(output/'plan.json'),same_test_images=802,calibration_images=400,
                                nested_bank_monotonicity_checks=monotonic_checks,prefix_equivalence=True)
    result['provenance']=dict(upstream=plan['upstream'],source_hashes=plan['source_hashes'],
                             weights_sha256=plan['weights_sha256'],runner_sha256=plan['runner_sha256'],
                             previous_plan_sha256=plan['previous_plan_sha256'],
                             previous_comparison_sha256=sha256(previous/'comparison.json'),
                             shared_configuration=plan['shared'],reference_seeds=list(SEEDS))
    result['model_sizes']=json.loads((output/'model-sizes.json').read_text()) if (output/'model-sizes.json').exists() else None
    result['preprocessing_geometry']=json.loads((output/'preprocessing-review.json').read_text())['summary'] if (output/'preprocessing-review.json').exists() else None
    result['execution_notes']=json.loads((output/'execution-notes.json').read_text()) if (output/'execution-notes.json').exists() else None
    atomic_json(output/'comparison.json',result)
    lines=['| Backbone | Preprocessing | Bank MiB | AUROC (%) | AP (%) | Recall (%) | FPR (%) |',
           '|---|---|---:|---:|---:|---:|---:|']
    for model,prep,budget in product(BACKBONES,PREPROCESSING,BUDGETS):
        values=result['summary'][configuration(model,prep,budget)]
        lines.append(f'| {model} | {prep} | {budget*1024*4/2**20:.3f} | '+' | '.join(f"{100*values[k]['mean']:.2f} ± {100*values[k]['sd']:.2f}" for k in METRICS)+' |')
    (output/'table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    for ax,k,title in zip(axes,('auroc','sensitivity','fpr'),('Macro image AUROC','Defect recall','Observed false-positive rate')):
        for model,color in zip(BACKBONES,('#0072B2','#D55E00')):
            for prep,style,offset in [('square','--',-.035),('crop','-',.035)]:
                vals=[result['summary'][configuration(model,prep,b)] [k] for b in BUDGETS]
                ax.errorbar(np.array([0,1])+offset,[100*v['mean'] for v in vals],yerr=[100*v['sd'] for v in vals],
                            color=color,linestyle=style,marker='o',capsize=4,label=f'{model} / {prep}')
        ax.set_xticks([0,1],['1.96 MiB\n501 patches','19.60 MiB\n5,017 patches']); ax.set_title(title); ax.set_ylabel('%'); ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('VisA PCB1–PCB4 · 64 normal references/category · fixed 802-image test set\nMatched PatchCore; five reference selections, mean ± sample SD',fontsize=11)
    fig.tight_layout(); fig.savefig(output/'comparison.png',dpi=180); fig.savefig(output/'comparison.pdf'); plt.close(fig)
    print(json.dumps(result['verification'],indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('data/visa-controlled-v1'))
    p.add_argument('--audit',type=Path,default=Path('data/visa-audit-v1'))
    p.add_argument('--previous',type=Path,default=Path('data/visa-five-seeds-v1'))
    a=p.parse_args(); report(a.output,a.audit,a.previous)


if __name__=='__main__': main()
