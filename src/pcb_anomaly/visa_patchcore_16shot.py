"""Run official WideResNet50-2 PatchCore with the same 16 VisA references as AnomalyDINO."""
import argparse
import gc
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms
from torchvision.transforms import InterpolationMode

from .crops import read_rows, sha256
from .multiseed import SEEDS
from .visa import CATEGORIES, safe_path
from .visa_benchmark import ranking_metrics
from .visa_localization import atomic_json, binary_ranking_metrics, pro_auc, transform_mask


def run(output, experiment, audit, root, cache, vendor):
    output, experiment, audit, root, cache, vendor = map(Path, (output, experiment, audit, root, cache, vendor))
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output/'run.json', {'status': 'running', 'started_unix': time.time()})
    plan = json.loads((experiment/'plan.json').read_text(encoding='utf-8'))
    rows = read_rows(audit/'manifest.jsonl')
    rowmap = {r['image']:r for r in rows}
    sys.path.insert(0, str((vendor/'src').resolve()))
    import patchcore.patchcore
    import patchcore.sampler
    import patchcore.common

    torch.set_num_threads(4)
    torch.manual_seed(42)
    np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    model = models.wide_resnet50_2(weights=models.Wide_ResNet50_2_Weights.IMAGENET1K_V1).eval().requires_grad_(False)
    sampler = patchcore.sampler.ApproximateGreedyCoresetSampler(.1, torch.device('cpu'))
    pc = patchcore.patchcore.PatchCore(torch.device('cpu'))
    pc.load(model, ['layer2','layer3'], torch.device('cpu'), (3,224,224), 1024,1024,
            patchsize=3, anomaly_score_num_nn=1, featuresampler=sampler,
            nn_method=patchcore.common.FaissNN(False,4))
    transform = transforms.Compose([
        transforms.Resize(256, interpolation=InterpolationMode.BILINEAR),
        transforms.CenterCrop(224), transforms.ToTensor(),
        transforms.Normalize([.485,.456,.406],[.229,.224,.225]),
    ])
    results=[]
    started=time.perf_counter()
    for cat in CATEGORIES:
        outcat=output/cat
        outcat.mkdir(parents=True,exist_ok=True)
        if all((outcat/f'seed{s}.json').exists() for s in SEEDS):
            results.extend(json.loads((outcat/f'seed{s}.json').read_text(encoding='utf-8')) for s in SEEDS)
            print(f'{cat}: saved five results found; skipping',flush=True)
            continue
        tests=sorted([r for r in rows if r['object']==cat and r['split']=='test'],key=lambda r:r['image'])
        ref_union=sorted({n for s in SEEDS for n in plan['selection'][str(s)][cat][:16]})
        names=ref_union+[r['image'] for r in tests]
        idx={n:i for i,n in enumerate(names)}
        feature_path=outcat/'temporary-features.npy'
        feature_meta=outcat/'temporary-features.json'
        signature={'images':names,'manifest_sha256':sha256(audit/'manifest.jsonl'),
                   'weights_sha256':plan['weights_sha256']['wide_resnet50_2-95faca4d.pth'],
                   'transform':'Resize256+CenterCrop224+ImageNet normalize','shape':[len(names),784,1024]}
        use_cache=False
        if feature_path.exists() and feature_meta.exists():
            try: use_cache=json.loads(feature_meta.read_text(encoding='utf-8'))==signature
            except (OSError,json.JSONDecodeError): use_cache=False
        if use_cache:
            feats=np.lib.format.open_memmap(feature_path,mode='r+',dtype='float32',shape=(len(names),784,1024))
            for start in range(0,len(names),16):
                chunk=np.asarray(feats[start:start+16])
                if not np.isfinite(chunk).all() or np.any(np.linalg.norm(chunk,axis=2)==0):
                    use_cache=False; break
            if not use_cache: feats._mmap.close()
        if not use_cache:
            feats=np.lib.format.open_memmap(feature_path,mode='w+',dtype='float32',shape=(len(names),784,1024))
            from .crops import sha256 as file_hash
            for start in range(0,len(names),4):
                batch=[]
                for name in names[start:start+4]:
                    path=safe_path(root,name)
                    if file_hash(path)!=rowmap[name]['image_sha256']: raise ValueError(f'Source changed: {name}')
                    with Image.open(path) as im: batch.append(transform(im.convert('RGB')))
                with torch.inference_mode(): embedded=np.asarray(pc._embed(torch.stack(batch)),dtype=np.float32)
                feats[start:start+len(batch)]=embedded.reshape(len(batch),784,1024)
                if start%80==0: print(f'{cat}: embedded {min(start+4,len(names))}/{len(names)}',flush=True)
            feats.flush(); feature_meta.write_text(json.dumps(signature,indent=2),encoding='utf-8')
        else:
            print(f'{cat}: reusing verified feature cache ({len(names)} images)',flush=True)

        query_features=feats[len(ref_union):]
        for seed in SEEDS:
            result_path=outcat/f'seed{seed}.json'
            if result_path.exists():
                results.append(json.loads(result_path.read_text(encoding='utf-8')))
                continue
            references=plan['selection'][str(seed)][cat][:16]
            ref_features=np.asarray(feats[[idx[n] for n in references]],dtype=np.float32).reshape(-1,1024)
            np.random.seed(42)
            bank=np.ascontiguousarray(sampler.run(ref_features))
            del ref_features; gc.collect()
            if bank.shape[1:]!=(1024,): raise ValueError(f'Unexpected bank shape: {bank.shape}')
            pc.anomaly_scorer.fit([bank])
            scores=[]; maps=[]; masks=[]
            for test_index,row in enumerate(tests):
                q=np.asarray(query_features[idx[row['image']]-len(ref_union)],dtype=np.float32)
                patch=pc.anomaly_scorer.predict([q])[0].reshape(1,28,28)
                scores.append(float(np.max(patch)))
                maps.append(pc.anomaly_segmentor.convert_to_segmentation(patch)[0].astype(np.float32))
                if row['mask']:
                    masks.append(transform_mask(safe_path(root,row['mask']),'crop',transforms.functional.resize,
                                                transforms.functional.center_crop,InterpolationMode.NEAREST))
                else: masks.append(np.zeros((224,224),dtype=bool))
                if test_index%20==0: print(f'{cat}/seed{seed}: scored {test_index+1}/{len(tests)}',flush=True)
            labels=np.asarray([bool(r['mask']) for r in tests],dtype=np.uint8)
            image=ranking_metrics(labels,scores)
            mask_arr=np.asarray(masks,dtype=bool); map_arr=np.asarray(maps,dtype=np.float32)
            auroc,ap=binary_ranking_metrics(mask_arr.ravel(),map_arr.ravel())
            record={'method':'official PatchCore WideResNet50-2','backbone':'WideResNet50-2 ImageNet1K V1',
                    'preprocessing':'Resize(256)+CenterCrop(224)','category':cat,'reference_seed':int(seed),
                    'reference_images':len(references),'rotation_degrees':[0],
                    'reference_patch_count':int(len(bank)),'reference_bank_bytes':int(bank.nbytes),
                    'image_auroc':image['auroc'],'image_average_precision':image['average_precision'],
                    'pixel_auroc':auroc,'pixel_average_precision':ap,'aupro_fpr_0_30':pro_auc(mask_arr,map_arr),
                    'test_images':len(tests),'anomaly_images':int(labels.sum()),'positive_pixels':int(mask_arr.sum()),
                    'pixel_count':int(mask_arr.size),'coreset':'official 10% approximate greedy sampler, 128D projection, 10 starts; seed 42',
                    'score':'maximum Euclidean 1-NN patch distance','map':'upstream PatchCore 28x28 bilinear 224x224, Gaussian sigma=4'}
            atomic_json(result_path,record); results.append(record)
            print(f"{cat}/seed{seed}: image AUROC={image['auroc']:.4f}, pixel AUROC={auroc:.4f}, AP={ap:.4f}, PRO={record['aupro_fpr_0_30']:.4f}",flush=True)
            del bank, scores, maps, masks, mask_arr, map_arr; gc.collect()
        feats._mmap.close(); del feats, query_features; gc.collect()
        feature_path.unlink(missing_ok=True); feature_meta.unlink(missing_ok=True)

    aggregate={}
    for metric in ('image_auroc','image_average_precision','pixel_auroc','pixel_average_precision','aupro_fpr_0_30'):
        per_seed=[np.mean([r[metric] for r in results if r['reference_seed']==seed]) for seed in SEEDS]
        aggregate[metric]={'macro_category_mean':float(np.mean([r[metric] for r in results])),
                           'sd_across_seed_macro_category_means':float(np.std(per_seed,ddof=1))}
    summary={'category_seed_results':results,'aggregate':aggregate,'protocol':{
        'categories':list(CATEGORIES),'seeds':list(SEEDS),
        'test_images_total':sum(next(r['test_images'] for r in results if r['category']==category) for category in CATEGORIES),
        'references_per_seed_category':16,'preprocessing':'Resize256+CenterCrop224','bank':'10% upstream approximate greedy coreset',
        'comparison':'same first 16 normal reference images per seed as AnomalyDINO; bank size and method pipeline differ'},
        'provenance':{'device':'CPU','runner_sha256':sha256(Path(__file__)),
                      'audit_manifest_sha256':sha256(audit/'manifest.jsonl'),
                      'weights_sha256':plan['weights_sha256'],
                      'versions':{n:importlib.metadata.version(n) for n in ('torch','torchvision','faiss-cpu','numpy','scipy')},
                      'elapsed_seconds':time.perf_counter()-started}}
    atomic_json(output/'summary.json',summary)
    atomic_json(output/'run.json',{'status':'complete','elapsed_seconds':time.perf_counter()-started})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n,d in dict(output='data/visa-patchcore-16shot-v1',experiment='data/visa-controlled-v1',
                    audit='data/visa-audit-v1',root='data/visa-pcb-v2',cache='data/torch-cache',
                    vendor='data/vendor/patchcore-inspection').items(): p.add_argument('--'+n,type=Path,default=Path(d))
    a=p.parse_args(); run(a.output,a.experiment,a.audit,a.root,a.cache,a.vendor)


if __name__=='__main__': main()
