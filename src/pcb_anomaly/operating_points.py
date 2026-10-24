"""Describe threshold tradeoffs and repeated misses from the controlled study."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from itertools import product

import numpy as np
from PIL import Image

from .controlled import BACKBONES, PREPROCESSING, BUDGETS, configuration
from .crops import read_rows, sha256
from .evaluation import calibrate_threshold
from .multiseed import SEEDS
from .visa import CATEGORIES, safe_path

TARGETS=(1,5,10)
FOCUS=('rn18_crop_5017','wrn50_crop_501','wrn50_crop_5017')


def summarize(values):
    values=np.asarray(values,dtype=float)
    return dict(mean=float(values.mean()),sd=float(values.std(ddof=1)),
                min=float(values.min()),max=float(values.max()))


def analyze(results, scores, manifest, geometry):
    """Return calibration-budget results and image-level stability diagnostics."""
    by_key={(r['method'],r['category'],r['reference_seed']):r for r in results}
    score_key=defaultdict(list)
    for row in scores:
        score_key[(row['method'],row['category'],row['reference_seed'])].append(row)
    if len(by_key)!=160 or any(len(v) not in (300,301) for v in score_key.values()):
        raise ValueError('Expected all 160 controlled runs and their aligned scores')
    test_rows={}
    output=[]
    for model,prep,budget in product(BACKBONES,PREPROCESSING,BUDGETS):
        method=configuration(model,prep,budget)
        for target in TARGETS:
            seed_summaries=[]; calibration_counts=[]
            for seed in SEEDS:
                tp=fn=fp=tn=cal_fp=cal_n=0
                for category in CATEGORIES:
                    rows=score_key[(method,category,seed)]
                    calibration=[r for r in rows if r['split']=='calibration']
                    tests=[r for r in rows if r['split']=='test']
                    if len(calibration)!=100 or len(tests) not in (200,201):
                        raise ValueError('Unexpected calibration/test partition')
                    threshold=calibrate_threshold([r['score'] for r in calibration],quantile=1-target/100)
                    cal_fp+=sum(r['score']>threshold for r in calibration); cal_n+=len(calibration)
                    for row in tests:
                        pred=int(row['score']>threshold)
                        if row['label']:
                            tp+=pred; fn+=1-pred
                        else:
                            fp+=pred; tn+=1-pred
                        test_rows[(method,target,seed,row['image'])]=dict(prediction=pred,threshold=threshold,score=row['score'])
                if tp+fn!=400 or fp+tn!=402 or cal_n!=400:
                    raise ValueError('Unexpected image counts')
                seed_summaries.append(dict(reference_seed=seed,sensitivity=tp/400,fpr=fp/402,
                                           calibration_fpr=cal_fp/cal_n,tp=tp,fp=fp,fn=fn,tn=tn,
                                           calibration_fp=cal_fp))
            output.append(dict(method=method,backbone=model,preprocessing=prep,bank_patches=budget,
                               bank_bytes=budget*1024*4,target_calibration_fpr=target,
                               achieved_calibration_fpr=summarize([r['calibration_fpr'] for r in seed_summaries]),
                               test_sensitivity=summarize([r['sensitivity'] for r in seed_summaries]),
                               test_fpr=summarize([r['fpr'] for r in seed_summaries]),
                               per_seed=seed_summaries))
    tests=[r for r in manifest if r['split']=='test']
    if len(tests)!=802: raise ValueError('Unexpected fixed test manifest')
    metadata={r['image']:r for r in tests}
    review={r['image']:r for r in geometry['details']}
    stability={}; detailed={}
    for method in FOCUS:
        for target in TARGETS:
            misses=[]; false_alarms=[]; per_image=[]
            for image,row in metadata.items():
                votes=[test_rows[(method,target,seed,image)]['prediction'] for seed in SEEDS]
                geometry_row=review.get(image,{})
                partial=geometry_row.get('crop_pixels',geometry_row.get('cropped_defect_pixels',0)) < \
                        geometry_row.get('resized_pixels',geometry_row.get('resized_defect_pixels',0))
                item=dict(image=image,category=row['object'],label=int(row['is_anomaly']),
                          anomaly_votes=sum(votes),votes=votes,defect_pixels=int(row.get('defect_pixels',0)),
                          partially_cropped=bool(partial))
                per_image.append(item)
                if item['label'] and item['anomaly_votes']==0: misses.append(item)
                if not item['label'] and item['anomaly_votes']==5: false_alarms.append(item)
            defects=[r for r in per_image if r['label']]
            by_category={}
            for category in CATEGORIES:
                group=[r for r in defects if r['category']==category]
                category_areas=np.asarray([r['defect_pixels'] for r in group],dtype=float)
                category_quartiles=np.quantile(category_areas,[.25,.75])
                category_area_groups=[('smallest_quartile',category_areas<=category_quartiles[0]),
                                      ('middle_half',(category_areas>category_quartiles[0])&(category_areas<=category_quartiles[1])),
                                      ('largest_quartile',category_areas>category_quartiles[1])]
                category_area_summary={}
                for name,mask in category_area_groups:
                    area_group=[r for r,keep in zip(group,mask) if keep]
                    category_area_summary[name]=dict(defects=len(area_group),persistently_missed=sum(r['anomaly_votes']==0 for r in area_group),
                                                     mean_reference_votes=float(np.mean([r['anomaly_votes'] for r in area_group])),
                                                     median_mask_pixels=float(np.median([r['defect_pixels'] for r in area_group])))
                by_category[category]=dict(defects=len(group),persistently_missed=sum(r['anomaly_votes']==0 for r in group),
                                           detected_in_all_seeds=sum(r['anomaly_votes']==5 for r in group),
                                           mean_reference_votes=float(np.mean([r['anomaly_votes'] for r in group])),
                                           partial_crop_count=sum(r['partially_cropped'] for r in group),
                                           partial_crop_misses=sum(r['partially_cropped'] and r['anomaly_votes']==0 for r in group),
                                           defect_area_quartiles=category_area_summary)
            area=np.asarray([r['defect_pixels'] for r in defects],dtype=float)
            quartiles=np.quantile(area,[.25,.75])
            area_groups=[('smallest_quartile',area<=quartiles[0]),
                         ('middle_half',(area>quartiles[0])&(area<=quartiles[1])),
                         ('largest_quartile',area>quartiles[1])]
            area_summary={}
            for name,mask in area_groups:
                group=[r for r,keep in zip(defects,mask) if keep]
                area_summary[name]=dict(defects=len(group),persistently_missed=sum(r['anomaly_votes']==0 for r in group),
                                        mean_reference_votes=float(np.mean([r['anomaly_votes'] for r in group])) if group else None,
                                        median_mask_pixels=float(np.median([r['defect_pixels'] for r in group])) if group else None)
            stability[f'{method}|{target}']=dict(method=method,target_calibration_fpr=target,
                persistently_missed=len(misses),persistently_detected=sum(r['anomaly_votes']==5 for r in defects),
                false_alarms_in_all_seeds=len(false_alarms),defects=400,normals=402,
                by_category=by_category,defect_area_quartiles=area_summary,
                crop_visibility={name:dict(defects=len(group),persistently_missed=sum(r['anomaly_votes']==0 for r in group),
                                           mean_reference_votes=float(np.mean([r['anomaly_votes'] for r in group])) if group else None)
                                 for name,group in [('partly_cropped',[r for r in defects if r['partially_cropped']]),
                                                    ('fully_visible',[r for r in defects if not r['partially_cropped']])]})
            detailed[f'{method}|{target}']=dict(defects=sorted(defects,key=lambda r:(r['category'],r['anomaly_votes'],r['defect_pixels'])),
                                               persistently_missed=sorted(misses,key=lambda r:(r['category'],r['defect_pixels'])),
                                               persistently_detected_false_alarms=sorted(false_alarms,key=lambda r:(r['category'],r['image'])))
    miss_overlap={}
    for target in TARGETS:
        left=set(r['image'] for r in detailed[f'rn18_crop_5017|{target}']['persistently_missed'])
        for method in ('wrn50_crop_501','wrn50_crop_5017'):
            right=set(r['image'] for r in detailed[f'{method}|{target}']['persistently_missed'])
            miss_overlap[f"{method}_vs_rn18_crop_5017|{target}"]=dict(
                shared=len(left&right),rn18_only=len(left-right),comparison_only=len(right-left),
                jaccard=len(left&right)/len(left|right) if left|right else None)
    return dict(targets=output,stability=stability,details=detailed,miss_overlap=miss_overlap,
                protocol=dict(threshold='Per category and reference seed; empirical higher quantile of 100 normal calibration scores',
                              target_values=TARGETS,alarm_rule='Anomaly if score > calibration threshold',
                              test_set='Same previously examined 802 images; descriptive operating-point analysis, not an independent test',
                              repetition='Five reference selections reuse the same test images; SD measures reference-selection variability only',
                              quantile_discreteness='With 100 calibration normals and strict >, nominal 1/5/10% targets are discrete and do not guarantee future test FPR',
                              miss_review='Persistent means missed or alarmed in all five reference selections at that configuration/threshold; the five decisions are not an ensemble'))


def make_plots(output, result, root, manifest):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=Path(output)
    # Threshold tradeoff for the crop configuration most relevant to model choice.
    fig,ax=plt.subplots(figsize=(7.2,5.2))
    colors={'rn18_crop_5017':'#0072B2','wrn50_crop_501':'#009E73','wrn50_crop_5017':'#D55E00'}
    labels={'rn18_crop_5017':'ResNet18 · large bank','wrn50_crop_501':'WideResNet50 · small bank','wrn50_crop_5017':'WideResNet50 · large bank'}
    for method in FOCUS:
        rows=sorted([r for r in result['targets'] if r['method']==method],key=lambda r:r['target_calibration_fpr'])
        ax.errorbar([100*r['test_fpr']['mean'] for r in rows],[100*r['test_sensitivity']['mean'] for r in rows],
                    xerr=[100*r['test_fpr']['sd'] for r in rows],yerr=[100*r['test_sensitivity']['sd'] for r in rows],
                    marker='o',capsize=3,color=colors[method],label=labels[method])
        for row in rows:
            ax.annotate(f"cal {row['target_calibration_fpr']}%",(100*row['test_fpr']['mean'],100*row['test_sensitivity']['mean']),
                        xytext=(4,4),textcoords='offset points',fontsize=7,color=colors[method])
    ax.set_xlabel('Observed test false-positive rate (%)'); ax.set_ylabel('Detected defects (%)')
    ax.set_title('VisA PCB · operating points set on normal calibration images\nError bars show SD across five reference selections')
    ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(output/'operating-points.png',dpi=180); fig.savefig(output/'operating-points.pdf'); plt.close(fig)
    # Side-by-side failure gallery for both large-bank crop models at a 5% calibration target.
    manifest_by_image={r['image']:r for r in manifest}
    models=('rn18_crop_5017','wrn50_crop_5017')
    selected={}
    for method in models:
        selected[method]={}
        for category in CATEGORIES:
            key=f'{method}|5'; group=[r for r in result['details'][key]['persistently_missed'] if r['category']==category]
            if not group:
                group=[r for r in result['details'][key]['defects'] if r['category']==category and r['anomaly_votes']<5]
            group=sorted(group,key=lambda r:(r['defect_pixels'],r['image']))
            indexes=np.unique(np.linspace(0,len(group)-1,min(3,len(group)),dtype=int)) if group else []
            selected[method][category]=[group[i] for i in indexes]
    fig,axes=plt.subplots(len(CATEGORIES),6,figsize=(18,3.4*len(CATEGORIES)))
    for i,category in enumerate(CATEGORIES):
        for j in range(6):
            method=models[j//3]; item_index=j%3
            ax=axes[i,j]; ax.axis('off')
            group=selected[method][category]
            if j in (0,3): ax.set_title(('ResNet18' if method.startswith('rn18') else 'WideResNet50')+'\nlarge bank',fontsize=9)
            if item_index>=len(group): continue
            item=group[item_index]; row=manifest_by_image[item['image']]
            with Image.open(safe_path(root,row['image'])) as im: im=im.convert('RGB')
            with Image.open(safe_path(root,row['mask'])) as m: mask=np.asarray(m)>0
            ax.imshow(im)
            if mask.any() and not mask.all(): ax.contour(mask,levels=[.5],colors=['red'],linewidths=.7)
            ax.set_title(f"{row['image'].rsplit('/',1)[-1]} · {item['anomaly_votes']}/5 votes\nmask {item['defect_pixels']} px",fontsize=8)
            if j==0: ax.set_ylabel(category)
    fig.suptitle('Large crop banks · 5% calibration target\nPersistent misses or lowest-vote defects; red = annotation',fontsize=11)
    fig.tight_layout(); fig.savefig(output/'persistent-misses.png',dpi=180); fig.savefig(output/'persistent-misses.pdf'); plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment',type=Path,default=Path('data/visa-controlled-v1'))
    p.add_argument('--audit',type=Path,default=Path('data/visa-audit-v1'))
    p.add_argument('--root',type=Path,default=Path('data/visa-pcb-v2'))
    p.add_argument('--output',type=Path,default=Path('data/visa-operating-points-v1'))
    a=p.parse_args()
    exp,audit,root,output=map(Path,(a.experiment,a.audit,a.root,a.output))
    output.mkdir(parents=True,exist_ok=False)
    experiment=json.loads((exp/'comparison.json').read_text())
    scores=[]
    for model,prep,budget,category,seed in product(BACKBONES,PREPROCESSING,BUDGETS,CATEGORIES,SEEDS):
        path=exp/f'{model}_{prep}'/category/f'seed{seed}-{budget}.json'
        blob=json.loads(path.read_text())
        if blob['result']['method']!=configuration(model,prep,budget): raise ValueError('Method mismatch')
        scores.extend(dict(row,method=blob['result']['method'],category=category,reference_seed=seed) for row in blob['scores'])
    geometry=json.loads((exp/'preprocessing-review.json').read_text())
    result=analyze(experiment['per_category'],scores,read_rows(audit/'manifest.jsonl'),geometry)
    result['provenance']=dict(controlled_plan_sha256=sha256(exp/'plan.json'),
                             controlled_comparison_sha256=sha256(exp/'comparison.json'),
                             controlled_run_sha256=sha256(exp/'run.json'),
                             manifest_sha256=sha256(audit/'manifest.jsonl'),
                             preprocessing_geometry_sha256=sha256(exp/'preprocessing-review.json'),
                             operating_point_code_sha256=sha256(Path(__file__)),
                             score_files_sha256={f'{m}_{p}/{c}/seed{s}-{b}.json':
                                 sha256(exp/f'{m}_{p}'/c/f'seed{s}-{b}.json')
                                 for m,p,b,c,s in product(BACKBONES,PREPROCESSING,BUDGETS,CATEGORIES,SEEDS)})
    (output/'operating-points.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    make_plots(output,result,root,read_rows(audit/'manifest.jsonl'))
    print(json.dumps({'configurations':len(result['targets']),'operating_points':len(result['targets']),'score_rows':len(scores),
                      'focus_stability':{k:{x:v for x,v in value.items() if x in ('persistently_missed','persistently_detected','false_alarms_in_all_seeds')}
                                         for k,value in result['stability'].items() if k.endswith('|5')},
                      'output':str(output)},indent=2))


if __name__=='__main__': main()
