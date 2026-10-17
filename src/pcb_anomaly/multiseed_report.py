"""Aggregate repeated runs without treating repeats as new test samples."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from .multiseed import SEEDS
from .visa import CATEGORIES

METHODS=('resnet18_global_knn','patchcore_resnet18','patchcore_wrn50_official')


def prediction_stability(score_rows):
    grouped=defaultdict(list)
    for row in score_rows:
        if row['split']=='test': grouped[(row['method'],row['image'])].append(row)
    details=[]
    for (method,image),rows in sorted(grouped.items()):
        if len(rows)!=5 or {r['reference_seed'] for r in rows}!=set(SEEDS) or len({r['label'] for r in rows})!=1:
            raise ValueError('Require five aligned decisions per test image')
        details.append(dict(method=method,image=image,label=rows[0]['label'],category=rows[0]['category'],
                            anomaly_votes=sum(r['prediction'] for r in rows)))
    summary={}
    for method in METHODS:
        rows=[r for r in details if r['method']==method]
        summary[method]=dict(persistently_missed_defects=sum(r['label']==1 and r['anomaly_votes']==0 for r in rows),
                            persistently_detected_defects=sum(r['label']==1 and r['anomaly_votes']==5 for r in rows),
                            persistently_false_alarmed_normals=sum(r['label']==0 and r['anomaly_votes']==5 for r in rows),
                            unstable_defects=sum(r['label']==1 and 0<r['anomaly_votes']<5 for r in rows),
                            unstable_normals=sum(r['label']==0 and 0<r['anomaly_votes']<5 for r in rows))
    return {'summary':summary,'details':details,'scope':'Descriptive five-reference stability; not an evaluated ensemble model.'}


def aggregate(rows):
    expected={(m,s,c) for m in METHODS for s in SEEDS for c in CATEGORIES}
    keys=[(r['method'],r['reference_seed'],r['category']) for r in rows]
    if len(set(keys))!=len(keys) or set(keys)!=expected:
        raise ValueError('Require exactly 60 unique method/seed/category results')
    per_seed=[]
    for method in METHODS:
        for seed in SEEDS:
            group=[r for r in rows if r['method']==method and r['reference_seed']==seed]
            counts={k:sum(r[k] for r in group) for k in ('tp','fp','tn','fn')}
            if counts['tp']+counts['fn']!=400 or counts['fp']+counts['tn']!=402:
                raise ValueError('Unexpected test counts')
            per_seed.append(dict(method=method,reference_seed=seed,
                                 auroc=float(np.mean([r['auroc'] for r in group])),
                                 ap=float(np.mean([r['average_precision'] for r in group])),
                                 sensitivity=counts['tp']/400,fpr=counts['fp']/402,**counts))
    summary={}
    for method in METHODS:
        group=[r for r in per_seed if r['method']==method]
        summary[method]={k:{'mean':float(np.mean([r[k] for r in group])),
                           'sd':float(np.std([r[k] for r in group],ddof=1)),
                           'min':float(min(r[k] for r in group)), 'max':float(max(r[k] for r in group))}
                         for k in ('auroc','ap','sensitivity','fpr','tp','fp')}
    return {'per_seed':per_seed,'summary':summary,'per_category':rows,
            'interpretation':'Sample standard deviation across five reference selections, not a confidence interval; same 802 test images reused; fixed coreset seed.'}


def report(output):
    from .crops import read_rows
    output=Path(output); rows=[]; score_rows=[]
    plan=json.loads((output/'plan.json').read_text())
    for seed in SEEDS:
        folder=output/f'rn-seed{seed}'
        if json.loads((folder/'run.json').read_text())['status']!='complete': raise ValueError('Incomplete RN run')
        rows.extend(dict(r,reference_seed=seed) for r in json.loads((folder/'results.json').read_text())['per_category'])
        score_rows.extend(dict(r,reference_seed=seed) for r in read_rows(folder/'scores.jsonl'))
        selection=json.loads((folder/'protocol.json').read_text())['selection']
        for category in CATEGORIES:
            actual=[r['image'] for r in selection[category] if r['split']=='reference']
            if actual!=plan['selection'][str(seed)][category]: raise ValueError('Reference plan mismatch')
    if json.loads((output/'wrn/run.json').read_text())['status']!='complete': raise ValueError('Incomplete WRN run')
    rows.extend(json.loads((output/'wrn/results.json').read_text()))
    score_rows.extend(read_rows(output/'wrn/scores.jsonl'))
    expected=None
    for method in METHODS:
        for seed in SEEDS:
            selected=[r for r in score_rows if r['method']==method and r['reference_seed']==seed and r['split']=='test']
            identity=sorted((r['image'],r['label']) for r in selected)
            if len(identity)!=802 or len({r[0] for r in identity})!=802: raise ValueError('Test identity count mismatch')
            if expected is None: expected=identity
            if identity!=expected: raise ValueError('Methods/seeds have different test images or labels')
    result=aggregate(rows)
    (output/'prediction-stability.json').write_text(json.dumps(prediction_stability(score_rows),indent=2))
    (output/'comparison.json').write_text(json.dumps(result,indent=2))
    names=dict(zip(METHODS,['ResNet18 + 3NN','PatchCore–ResNet18','Resmî PatchCore–WideResNet50']))
    lines=['| Yöntem | AUROC (%) | AP (%) | Duyarlılık (%) | FPR (%) |',
           '|---|---:|---:|---:|---:|']
    for method in METHODS:
        stats=result['summary'][method]
        values=[f"{stats[k]['mean']*100:.2f} ± {stats[k]['sd']*100:.2f}" for k in ('auroc','ap','sensitivity','fpr')]
        lines.append('| '+names[method]+' | '+' | '.join(values)+' |')
    (output/'summary-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=['| Kategori | Yöntem | AUROC (%) | Duyarlılık (%) | FPR (%) |', '|---|---|---:|---:|---:|']
    for category in CATEGORIES:
        for method in METHODS:
            group=[r for r in rows if r['category']==category and r['method']==method]
            values=[f"{np.mean([r[k] for r in group])*100:.2f} ± {np.std([r[k] for r in group],ddof=1)*100:.2f}" for k in ('auroc','recall','fpr')]
            lines.append('| '+category+' | '+names[method]+' | '+' | '.join(values)+' |')
    (output/'category-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels=['ResNet18 + 3NN','PatchCore–ResNet18','PatchCore–WideResNet50']
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for ax,key,title in zip(axes,['auroc','sensitivity','fpr'],['Macro image AUROC','Defect sensitivity','False-positive rate']):
        for i,method in enumerate(METHODS):
            values=np.array([r[key] for r in result['per_seed'] if r['method']==method])*100
            ax.scatter(np.full(5,i)+np.linspace(-.08,.08,5),values,s=22,color=f'C{i}',zorder=3)
            ax.errorbar(i,values.mean(),yerr=values.std(ddof=1),fmt='_',markersize=20,capsize=5,color='black')
        ax.set_xticks(range(3),labels,rotation=18,ha='right',fontsize=8)
        ax.set_title(title);ax.set_ylabel('%');ax.grid(axis='y',alpha=.25)
    fig.suptitle('VisA PCB: 64 references/category; five selections (dots); mean ± SD\nSame 802 test images; calibrated thresholds; preprocessing and memory budgets differ',fontsize=11)
    fig.savefig(output/'comparison.png',dpi=180)
    fig.savefig(output/'comparison.pdf')
    plt.close(fig)
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data/visa-five-seeds-v1'))
    report(parser.parse_args().output)
