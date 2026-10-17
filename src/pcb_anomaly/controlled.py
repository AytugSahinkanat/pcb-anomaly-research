"""Controlled 2 x 2 x 2 PatchCore study on the existing five VisA selections."""
import argparse
import contextlib
import gc
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import numpy as np

from .crops import read_rows, sha256, square_input
from .evaluation import binary_metrics, calibrate_threshold
from .multiseed import SEEDS, validate_plan
from .visa import CATEGORIES, safe_path
from .visa_benchmark import ranking_metrics

BACKBONES = ('rn18', 'wrn50')
PREPROCESSING = ('square', 'crop')
BUDGETS = (501, 5017)


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def configuration(backbone, preprocessing, budget):
    return f'{backbone}_{preprocessing}_{budget}'


def make_plan(output, previous, audit, vendor, cache):
    old = validate_plan(previous, audit, vendor)
    plan = dict(old, design='Full factorial: 2 backbones x 2 preprocessing x 2 bank budgets x 5 selections x 4 categories',
                backbones=BACKBONES, preprocessing=PREPROCESSING, budgets=BUDGETS,
                previous_plan_sha256=sha256(Path(previous)/'plan.json'),
                shared=dict(implementation='Pinned upstream PatchCore', layers=['layer2','layer3'],
                            pretrain_dimension=1024, target_dimension=1024, dtype='float32', patchsize=3,
                            projection_dimension=128, sampler_seed=42, neighbors=1,
                            score='maximum squared L2 nearest patch distance',
                            preprocessing_definitions={'square':'mean RGB center padding then bilinear resize224',
                                                      'crop':'bilinear shorter-side resize256 then center crop224'},
                            normalization='ImageNet mean/std', bank_bytes=[n*1024*4 for n in BUDGETS]),
                budget_scope='Stored feature bank only; backbone parameters, FAISS copy, activation and transient memory are excluded',
                selection_policy='Official 10% greedy coreset; its first 501 entries form nested small bank; verify prefix equivalence',
                reuse_policy='Previously completed WRN crop 5017 predictions and banks reused with provenance and score parity checks',
                attribution='Paired factorial contrasts; no claim of additive causal decomposition of historical gap; prior test inspected',
                retention='Retain selected indices, bank hashes and scores; new banks reproducible from weights/source/manifest, not retained')
    plan.pop('rn18'); plan.pop('wrn50')
    plan['weights_sha256'] = {p.name:sha256(p) for p in (Path(cache)/'checkpoints').glob('*.pth')}
    plan['runner_sha256'] = sha256(Path(__file__))
    Path(output).mkdir(parents=True, exist_ok=False)
    atomic_json(Path(output)/'plan.json', plan)


def run(output, previous, audit, root, cache, vendor):
    import torch
    from torchvision import transforms, models
    from PIL import Image
    output, previous, audit, root, cache, vendor = map(Path, (output,previous,audit,root,cache,vendor))
    plan = validate_plan(output,audit,vendor)
    if sha256(Path(__file__)) != plan['runner_sha256']:
        raise ValueError('Runner changed after preregistration')
    for name, digest in plan['weights_sha256'].items():
        if sha256(cache/'checkpoints'/name) != digest: raise ValueError('Weights changed')
    if sha256(previous/'plan.json') != plan['previous_plan_sha256']: raise ValueError('Previous plan changed')
    sys.path.insert(0,str((vendor/'src').resolve()))
    import patchcore.patchcore
    import patchcore.sampler
    import patchcore.common

    class RecordingSampler(patchcore.sampler.ApproximateGreedyCoresetSampler):
        def _compute_greedy_coreset_indices(self, features):
            indices = super()._compute_greedy_coreset_indices(features)
            self.selected_indices = indices
            return indices

    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    # Verify nested selection against two independent official sampler calls.
    toy = np.random.default_rng(19).normal(size=(100,256)).astype('float32')
    sampled = []
    for fraction in (.1,.3):
        torch.manual_seed(42); np.random.seed(42)
        test_sampler = RecordingSampler(fraction,torch.device('cpu'))
        with (output/'prefix-check.log').open('a') as log, contextlib.redirect_stderr(log):
            test_sampler.run(toy)
        sampled.append(test_sampler.selected_indices)
    if not np.array_equal(sampled[0],sampled[1][:10]): raise ValueError('Non-nested coreset')
    atomic_json(output/'prefix-check.json',dict(passed=True,small=sampled[0].tolist(),large=sampled[1].tolist()))
    allrows=read_rows(audit/'manifest.jsonl'); rowmap={r['image']:r for r in allrows}
    old_results=json.loads((previous/'wrn/results.json').read_text())
    old_scores=read_rows(previous/'wrn/scores.jsonl')
    if json.loads((previous/'wrn/run.json').read_text())['status']!='complete': raise ValueError('Prior WRN incomplete')
    started=time.perf_counter()
    atomic_json(output/'run.json',dict(status='running',plan_sha256=sha256(output/'plan.json')))
    for backbone in BACKBONES:
        torch.manual_seed(42); np.random.seed(42)
        if backbone=='rn18': model=models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        else: model=models.wide_resnet50_2(weights=models.Wide_ResNet50_2_Weights.IMAGENET1K_V1)
        model.eval().requires_grad_(False)
        sampler=RecordingSampler(.1,torch.device('cpu'))
        pc=patchcore.patchcore.PatchCore(torch.device('cpu'))
        pc.load(model,['layer2','layer3'],torch.device('cpu'),(3,224,224),1024,1024,
                patchsize=3,anomaly_score_num_nn=1,featuresampler=sampler,
                nn_method=patchcore.common.FaissNN(False,4))
        for prep in PREPROCESSING:
            resize=[square_input] if prep=='square' else [transforms.Resize(256),transforms.CenterCrop(224)]
            transform=transforms.Compose(resize+[transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
            reuse=backbone=='wrn50' and prep=='crop'
            for category in CATEGORIES:
                folder=output/f'{backbone}_{prep}'/category; folder.mkdir(parents=True,exist_ok=True)
                expected=[folder/f'seed{s}-{b}.json' for s in SEEDS for b in BUDGETS]
                if all(p.exists() for p in expected):
                    print(f'{backbone} {prep} {category}: checkpoints complete',flush=True); continue
                queries=sorted([r for r in allrows if r['object']==category and r['split'] in ('calibration','test')],key=lambda r:r['image'])
                union=[] if reuse else sorted({n for s in SEEDS for n in plan['selection'][str(s)][category]})
                names=union+[r['image'] for r in queries]; index={n:i for i,n in enumerate(names)}
                feature_path=folder/'temporary-features.npy'
                features=np.lib.format.open_memmap(feature_path,mode='w+',dtype='float32',shape=(len(names),784,1024))
                t=time.perf_counter()
                for start in range(0,len(names),4):
                    batch=[]
                    for name in names[start:start+4]:
                        path=safe_path(root,name)
                        if sha256(path)!=rowmap[name]['image_sha256']: raise ValueError('Image changed')
                        with Image.open(path) as im: batch.append(transform(im.convert('RGB')))
                    with torch.inference_mode(): values=np.asarray(pc._embed(torch.stack(batch)),dtype='float32')
                    if not np.isfinite(values).all(): raise ValueError('Nonfinite embedding')
                    features[start:start+len(batch)]=values.reshape(len(batch),784,1024)
                    if start%80==0: print(f'{backbone} {prep} {category}: extracted {start+len(batch)}/{len(names)}',flush=True)
                features.flush(); extraction_seconds=time.perf_counter()-t
                query_features=features[len(union):].reshape(-1,1024)
                for seed in SEEDS:
                    if all((folder/f'seed{seed}-{b}.json').exists() for b in BUDGETS): continue
                    torch.manual_seed(42); np.random.seed(42); t=time.perf_counter()
                    if reuse:
                        bank=np.load(previous/f'wrn/{category}/seed{seed}-bank.npy')
                        indices=np.load(previous/f'wrn/{category}/seed{seed}-indices.npy')
                    else:
                        full_bank=np.asarray(features[[index[n] for n in plan['selection'][str(seed)][category]]]).reshape(-1,1024)
                        with (folder/f'seed{seed}-coreset.log').open('w') as log, contextlib.redirect_stderr(log):
                            bank=sampler.run(full_bank)
                        indices=sampler.selected_indices
                        del full_bank
                    coreset_seconds=time.perf_counter()-t
                    if bank.shape!=(5017,1024) or bank.dtype!=np.float32: raise ValueError('Bank shape/dtype mismatch')
                    if len(np.unique(indices))!=5017: raise ValueError('Duplicate bank indices')
                    np.save(folder/f'seed{seed}-indices.npy',indices)
                    for budget in BUDGETS:
                        target=folder/f'seed{seed}-{budget}.json'
                        if target.exists(): continue
                        chosen=bank[:budget]; pc.anomaly_scorer.fit([chosen]); t=time.perf_counter()
                        if reuse and budget==5017:
                            prior={r['image']:r for r in old_scores if r['category']==category and r['reference_seed']==seed}
                            scores=np.array([prior[r['image']]['score'] for r in queries])
                        else:
                            values=[]
                            for start in range(0,len(queries),8):
                                q=np.asarray(query_features[start*784:min(start+8,len(queries))*784])
                                distances=pc.anomaly_scorer.predict([q])[0]
                                values.extend(distances.reshape(-1,784).max(1).tolist())
                            scores=np.array(values)
                            del q
                        search_seconds=time.perf_counter()-t
                        # All reused seeds and every new configuration are independently checked through full prediction.
                        with Image.open(safe_path(root,queries[0]['image'])) as im: check_input=transform(im.convert('RGB')).unsqueeze(0)
                        direct,_=pc._predict(check_input)
                        error=abs(float(direct[0])-float(scores[0]))
                        if error>1e-4*(1+abs(float(scores[0]))): raise ValueError('Full prediction parity failed')
                        ci=[i for i,r in enumerate(queries) if r['split']=='calibration']; ti=[i for i,r in enumerate(queries) if r['split']=='test']
                        threshold=calibrate_threshold(scores[ci]); labels=[int(queries[i]['is_anomaly']) for i in ti]
                        metrics=binary_metrics(labels,scores[ti],threshold=threshold,label_source='independent_annotation')
                        metrics.update(ranking_metrics(labels,scores[ti]))
                        import hashlib
                        result=dict(backbone=backbone,preprocessing=prep,budget=budget,reference_seed=seed,category=category,
                                    method=configuration(backbone,prep,budget),threshold=threshold,**metrics)
                        score_rows=[dict(image=r['image'],split=r['split'],label=int(r['is_anomaly']),score=float(scores[i]),
                                         prediction=int(scores[i]>threshold)) for i,r in enumerate(queries)]
                        atomic_json(target,dict(result=result,scores=score_rows,bank_shape=list(chosen.shape),bank_bytes=chosen.nbytes,
                                                bank_sha256=hashlib.sha256(chosen.tobytes()).hexdigest(),
                                                source='prior study' if reuse and budget==5017 else 'new evaluation',
                                                parity_error=error,extraction_seconds=extraction_seconds,
                                                coreset_seconds=coreset_seconds,search_seconds=search_seconds))
                        print(f'{backbone} {prep} {category} seed{seed} bank{budget}: complete ({search_seconds:.1f}s search)',flush=True)
                del query_features
                features.flush(); features._mmap.close(); del features; gc.collect()
                target=feature_path.resolve()
                if not target.is_relative_to(output.resolve()): raise ValueError('Unexpected cleanup target')
                target.unlink()
        del pc,model,sampler; gc.collect()
    atomic_json(output/'run.json',dict(status='complete',plan_sha256=sha256(output/'plan.json'),
                                     invocation_seconds=time.perf_counter()-started,
                                     versions={n:importlib.metadata.version(n) for n in ('torch','torchvision','faiss-cpu','numpy','Pillow')}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('plan','run'))
    for name,default in dict(output='data/visa-controlled-v1',previous='data/visa-five-seeds-v1',audit='data/visa-audit-v1',
                             root='data/visa-pcb-v2',cache='data/torch-cache',vendor='data/vendor/patchcore-inspection').items():
        parser.add_argument('--'+name,type=Path,default=Path(default))
    a=parser.parse_args()
    if a.action=='plan': make_plan(a.output,a.previous,a.audit,a.vendor,a.cache)
    else: run(a.output,a.previous,a.audit,a.root,a.cache,a.vendor)


if __name__=='__main__': main()
