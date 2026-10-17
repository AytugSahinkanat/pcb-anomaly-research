"""Predeclared five-reference-selection study with upstream PatchCore."""
import argparse
import contextlib
import gc
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import numpy as np

from .crops import read_rows, sha256
from .evaluation import binary_metrics, calibrate_threshold
from .visa import CATEGORIES, safe_path
from .visa_benchmark import choose_samples, ranking_metrics

SEEDS = (42, 43, 44, 45, 46)
COMMIT = 'fcaa92f124fb1ad74a7acf56726decd4b27cbcad'


def write_plan(output, audit, vendor):
    output, audit, vendor = map(Path, (output, audit, vendor))
    output.mkdir(parents=True, exist_ok=False)
    if json.loads((audit/'audit.json').read_text())['status'] != 'complete':
        raise ValueError('Incomplete data audit')
    source = json.loads((vendor/'provenance.json').read_text())
    if source['commit'] != COMMIT:
        raise ValueError('Unexpected upstream commit')
    rows = read_rows(audit/'manifest.jsonl')
    selections = {str(seed): {c: [r['image'] for r in rs if r['split']=='reference']
                              for c, rs in choose_samples(rows, seed=seed).items()} for seed in SEEDS}
    plan = {'reference_seeds': SEEDS, 'references_per_category':64, 'sampler_seed':42,
            'manifest_sha256':sha256(audit/'manifest.jsonl'), 'upstream':source,
            'source_hashes': {p.name:sha256(p) for p in (vendor/'src/patchcore').glob('*.py')},
            'selection': selections,
            'rn18': 'Unchanged v1 methods and square-pad 224 preprocessing; only reference selection changes; 1% coreset',
            'wrn50': {'implementation':'upstream PatchCore class, embed, ApproximateGreedyCoresetSampler and FaissNN',
                      'weights':'Wide_ResNet50_2_Weights.IMAGENET1K_V1', 'layers':['layer2','layer3'],
                      'pretrain_embed_dimension':1024, 'target_embed_dimension':1024,
                      'patchsize':3, 'coreset_fraction':.1, 'projection_dimension':128,
                      'starting_points':10, 'neighbors':1, 'score':'maximum squared L2 1NN patch distance',
                      'preprocessing':'official Resize(256) shorter side; CenterCrop(224); ImageNet normalize',
                      'source':'README quick-guide IM224_WR50_L2-3_P01_D1024-1024_PS-3_AN-1'},
            'calibration':'same fixed 100 normal/category; higher 95th percentile; score > threshold',
            'evaluation':'same official 802 test images in each run; 5 runs are not 4010 independent samples',
            'scope':'64-reference benchmark adaptation; backbone/preprocessing/coreset all differ; not a backbone-only ablation',
            'test_policy':'No settings chosen from these test scores; report every seed/category; this is an extension on an already inspected benchmark'}
    (output/'plan.json').write_text(json.dumps(plan, indent=2))
    return plan


def validate_plan(output, audit, vendor):
    output, audit, vendor = map(Path, (output, audit, vendor))
    plan = json.loads((output/'plan.json').read_text())
    if sha256(audit/'manifest.jsonl') != plan['manifest_sha256']:
        raise ValueError('Manifest changed')
    for name, digest in plan['source_hashes'].items():
        if sha256(vendor/'src/patchcore'/name) != digest:
            raise ValueError('Upstream code changed')
    return plan


def run_rn(output, audit, root, cache, vendor):
    from .visa_benchmark import run
    validate_plan(output, audit, vendor)
    output=Path(output)
    for seed in SEEDS:
        print(f'ResNet18 two methods: reference seed {seed} started', flush=True)
        with (output/f'rn-seed{seed}.log').open('w') as log, contextlib.redirect_stdout(log):
            run(root,audit,output/f'rn-seed{seed}',cache,reference_seed=seed)
        print(f'ResNet18 two methods: reference seed {seed} complete', flush=True)


def run_wrn(output, audit, root, cache, vendor, resume=False):
    import torch
    import torchvision
    from torchvision import transforms
    from torchvision.models import wide_resnet50_2, Wide_ResNet50_2_Weights
    from PIL import Image
    output, audit, root, cache, vendor = map(Path,(output,audit,root,cache,vendor))
    plan=validate_plan(output,audit,vendor)
    sys.path.insert(0,str((vendor/'src').resolve()))
    import patchcore.patchcore
    import patchcore.sampler
    import patchcore.common
    import faiss

    class RecordingSampler(patchcore.sampler.ApproximateGreedyCoresetSampler):
        def _compute_greedy_coreset_indices(self, features):
            indices=super()._compute_greedy_coreset_indices(features)
            self.selected_indices=indices
            return indices

    torch.set_num_threads(4); torch.manual_seed(42); np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    model=wide_resnet50_2(weights=Wide_ResNet50_2_Weights.IMAGENET1K_V1).eval().requires_grad_(False)
    sampler=RecordingSampler(.1,torch.device('cpu'))
    pc=patchcore.patchcore.PatchCore(torch.device('cpu'))
    pc.load(model,['layer2','layer3'],torch.device('cpu'),(3,224,224),1024,1024,
            patchsize=3,anomaly_score_num_nn=1,featuresampler=sampler,
            nn_method=patchcore.common.FaissNN(False,4))
    transform=transforms.Compose([transforms.Resize(256),transforms.CenterCrop(224),transforms.ToTensor(),
                                  transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    allrows=read_rows(audit/'manifest.jsonl'); rowmap={r['image']:r for r in allrows}
    dest=output/'wrn'; dest.mkdir(exist_ok=resume)
    def read_checkpoint(name, default):
        path=dest/name
        return json.loads(path.read_text()) if resume and path.exists() else default
    results=read_checkpoint('results.json',[])
    timings=read_checkpoint('timing.json',[])
    parity=read_checkpoint('upstream-parity.json',[])
    records=read_rows(dest/'scores.jsonl') if resume and (dest/'scores.jsonl').exists() else []
    prior_pairs=len(results)
    (dest/'run.json').write_text(json.dumps({'status':'running'}))
    started=time.perf_counter()
    for category in CATEGORIES:
        completed={r['reference_seed'] for r in results if r['category']==category}
        if completed==set(SEEDS):
            temporary=(dest/category/'temporary-features.npy').resolve()
            if temporary.exists():
                if not temporary.is_relative_to(dest.resolve()): raise ValueError('Unexpected cleanup target')
                temporary.unlink()
            print(f'WRN {category}: reused five completed checkpointed runs',flush=True)
            continue
        queries=sorted([r for r in allrows if r['object']==category and r['split'] in ('calibration','test')],key=lambda r:r['image'])
        union=sorted(set(n for seed in SEEDS for n in plan['selection'][str(seed)][category]))
        names=union+[r['image'] for r in queries]
        index={name:i for i,name in enumerate(names)}
        folder=dest/category; folder.mkdir(exist_ok=resume)
        feature_path=folder/'temporary-features.npy'
        features=np.lib.format.open_memmap(feature_path,mode='w+',dtype='float32',shape=(len(names),784,1024))
        t=time.perf_counter()
        for start in range(0,len(names),4):
            batch=[]
            for name in names[start:start+4]:
                path=safe_path(root,name)
                if sha256(path)!=rowmap[name]['image_sha256']:
                    raise ValueError('Image changed')
                with Image.open(path) as im: batch.append(transform(im.convert('RGB')))
            with torch.inference_mode(): values=np.asarray(pc._embed(torch.stack(batch)),dtype='float32')
            features[start:start+len(batch)]=values.reshape(len(batch),784,1024)
            if start%80==0: print(f'WRN {category}: extracted {start+len(batch)}/{len(names)} unique images',flush=True)
        features.flush(); extraction_seconds=time.perf_counter()-t
        query_features=features[len(union):].reshape(-1,1024)
        for seed in SEEDS:
            if seed in completed: continue
            torch.manual_seed(42); np.random.seed(42)
            references=plan['selection'][str(seed)][category]
            full_bank=np.asarray(features[[index[n] for n in references]]).reshape(-1,1024)
            t=time.perf_counter()
            print(f'WRN {category} seed {seed}: coreset started',flush=True)
            with (folder/f'seed{seed}-coreset.log').open('w') as log, contextlib.redirect_stderr(log):
                bank=sampler.run(full_bank)
            coreset_seconds=time.perf_counter()-t
            del full_bank
            np.save(folder/f'seed{seed}-bank.npy',bank)
            np.save(folder/f'seed{seed}-indices.npy',sampler.selected_indices)
            t=time.perf_counter(); pc.anomaly_scorer.fit([bank]); scores=[]
            for start in range(0,len(queries),8):
                q=np.asarray(query_features[start*784:min(start+8,len(queries))*784])
                distances=pc.anomaly_scorer.predict([q])[0]
                scores.extend(distances.reshape(-1,784).max(1).tolist())
            search_seconds=time.perf_counter()-t
            scores=np.asarray(scores)
            if seed==42:
                with Image.open(safe_path(root,queries[0]['image'])) as im:
                    check_input=transform(im.convert('RGB')).unsqueeze(0)
                direct_scores,_=pc._predict(check_input)
                error=abs(float(direct_scores[0])-float(scores[0]))
                if error>1e-4*(1+abs(float(scores[0]))):
                    raise ValueError('Cached scoring differs from upstream full prediction')
                parity.append(dict(category=category,image=queries[0]['image'],absolute_error=error,
                                   check='cached embedding + upstream scorer vs upstream full _predict'))
                (dest/'upstream-parity.json').write_text(json.dumps(parity,indent=2))
            ci=[i for i,r in enumerate(queries) if r['split']=='calibration']
            ti=[i for i,r in enumerate(queries) if r['split']=='test']
            threshold=calibrate_threshold(scores[ci]); labels=[int(queries[i]['is_anomaly']) for i in ti]
            metrics=binary_metrics(labels,scores[ti],threshold=threshold,label_source='independent_annotation')
            metrics.update(ranking_metrics(labels,scores[ti]))
            results.append(dict(reference_seed=seed,category=category,method='patchcore_wrn50_official',threshold=threshold,**metrics))
            records.extend(dict(reference_seed=seed,category=category,method='patchcore_wrn50_official',image=r['image'],
                                split=r['split'],label=int(r['is_anomaly']),score=float(scores[i]),threshold=threshold,
                                prediction=int(scores[i]>threshold)) for i,r in enumerate(queries))
            timings.append(dict(category=category,reference_seed=seed,shared_extraction_seconds=extraction_seconds,
                                unique_images=len(names),query_images=len(queries),coreset_seconds=coreset_seconds,
                                search_seconds=search_seconds,bank_bytes=bank.nbytes,bank_shape=list(bank.shape),
                                unique_coreset_indices=int(len(np.unique(sampler.selected_indices)))))
            (dest/'results.json').write_text(json.dumps(results,indent=2))
            (dest/'scores.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            (dest/'timing.json').write_text(json.dumps(timings,indent=2))
            print(f'WRN {category} seed {seed}: complete (coreset {coreset_seconds:.1f}s, search {search_seconds:.1f}s)',flush=True)
        # Only remove this run's derived temporary feature file, never source data.
        del q,query_features
        features.flush(); features._mmap.close()
        del features; gc.collect()
        target=feature_path.resolve()
        if not target.is_relative_to(dest.resolve()): raise ValueError('Unexpected cleanup target')
        target.unlink()
    info=dict(status='complete',elapsed_seconds=time.perf_counter()-started,resumed=resume,
              prior_completed_pairs=prior_pairs,elapsed_scope='this invocation only',upstream_commit=COMMIT,
              plan_sha256=sha256(output/'plan.json'),weights_sha256=sha256(cache/'checkpoints/wide_resnet50_2-95faca4d.pth'),
              versions={n:importlib.metadata.version(n) for n in ('torch','torchvision','faiss-cpu','scipy','timm','numpy')})
    (dest/'run.json').write_text(json.dumps(info,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('plan','rn','wrn'))
    parser.add_argument('--output',type=Path,default=Path('data/visa-five-seeds-v1'))
    parser.add_argument('--root',type=Path,default=Path('data/visa-pcb-v2'))
    parser.add_argument('--audit',type=Path,default=Path('data/visa-audit-v1'))
    parser.add_argument('--cache',type=Path,default=Path('data/torch-cache'))
    parser.add_argument('--vendor',type=Path,default=Path('data/vendor/patchcore-inspection'))
    parser.add_argument('--resume',action='store_true',help='Resume WRN from per-seed result checkpoints')
    args=parser.parse_args()
    if args.action=='plan': write_plan(args.output,args.audit,args.vendor)
    elif args.action=='wrn': run_wrn(args.output,args.audit,args.root,args.cache,args.vendor,resume=args.resume)
    else: run_rn(args.output,args.audit,args.root,args.cache,args.vendor)


if __name__=='__main__': main()
