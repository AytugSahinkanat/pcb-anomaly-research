"""Pixel-level VisA localization evaluation for controlled PatchCore models."""
import argparse
import gc
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .crops import read_rows, sha256
from .multiseed import SEEDS
from .visa import CATEGORIES, safe_path


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def binary_ranking_metrics(labels, scores):
    y = np.asarray(labels, dtype=np.uint8).ravel()
    s = np.asarray(scores, dtype=np.float32).ravel()
    order = np.argsort(s, kind='mergesort')
    sorted_s, sorted_y = s[order], y[order]
    npos = int(y.sum()); nneg = len(y) - npos
    if not npos or not nneg:
        raise ValueError('Pixel metrics require positive and negative pixels')
    ends = np.r_[np.flatnonzero(np.diff(sorted_s)), len(s)-1]
    tp = np.cumsum(sorted_y, dtype=np.int64)[ends]
    fp = (ends + 1) - tp
    tpr = np.r_[0., tp / npos, 1.]
    fpr = np.r_[0., fp / nneg, 1.]
    # Ascending-score accumulation measures the area for predicting the low
    # scores as positive, so reverse it for the anomaly-score convention.
    auroc = float(1.0 - np.trapz(tpr, fpr))
    # Non-interpolated average precision; ties enter at the same threshold.
    descending = np.argsort(-s, kind='mergesort')
    desc_s, desc_y = s[descending], y[descending]
    desc_ends = np.r_[np.flatnonzero(np.diff(desc_s)), len(s)-1]
    desc_tp = np.cumsum(desc_y, dtype=np.int64)[desc_ends]
    precision = desc_tp / (desc_ends + 1)
    ap = float(np.sum(np.diff(np.r_[0, desc_tp]) * precision) / npos)
    return auroc, ap


def pro_auc(masks, maps, steps=200, max_fpr=0.30):
    """Area under per-component overlap versus normal-pixel FPR, truncated at 0.30."""
    from scipy import ndimage
    mask_arr = np.asarray(masks, dtype=bool)
    score_arr = np.asarray(maps, dtype=np.float32)
    normal_scores = np.sort(score_arr[~mask_arr])
    if not len(normal_scores):
        raise ValueError('PRO requires normal pixels')
    components = []
    for mask, score in zip(mask_arr, score_arr):
        labels, count = ndimage.label(mask)
        for component_id in range(1, count + 1):
            components.append(np.sort(score[labels == component_id]))
    if not components:
        raise ValueError('PRO requires at least one defect region')
    thresholds = np.linspace(float(score_arr.min()), float(score_arr.max()), steps, dtype=np.float32)
    fpr = (len(normal_scores) - np.searchsorted(normal_scores, thresholds, side='right')) / len(normal_scores)
    pro = np.mean([(len(component) - np.searchsorted(component, thresholds, side='right')) / len(component)
                   for component in components], axis=0)
    order = np.argsort(fpr, kind='stable')
    fpr, pro = fpr[order], pro[order]
    unique_fpr, first = np.unique(fpr, return_index=True)
    unique_pro = np.maximum.reduceat(pro, first)
    grid = np.r_[unique_fpr[unique_fpr < max_fpr], max_fpr]
    if len(grid) < 2:
        return 0.0
    vals = np.interp(grid, unique_fpr, unique_pro)
    return float(np.trapz(vals, grid) / max_fpr)


def transform_mask(path, preprocessing, resize_image, center_crop, nearest):
    with Image.open(path) as image:
        mask = image.convert('L')
    if preprocessing == 'crop':
        # torchvision's resize computes the output size from the short side;
        # nearest-neighbour interpolation preserves binary mask labels.
        mask = resize_image(mask, 256, interpolation=nearest)
        mask = center_crop(mask, 224)
    else:
        # Square preprocessing center-pads the image; padding is a normal pixel.
        side = max(mask.size)
        canvas = Image.new('L', (side, side), 0)
        canvas.paste(mask, ((side-mask.width)//2, (side-mask.height)//2))
        mask = canvas.resize((224, 224), Image.Resampling.NEAREST)
    return np.asarray(mask, dtype=np.uint8) > 0


def run(output, experiment, previous, audit, root, cache, vendor):
    import torch
    from torchvision import models, transforms
    from torchvision.transforms import InterpolationMode

    output, experiment, previous, audit, root, cache, vendor = map(Path, (output, experiment, previous, audit, root, cache, vendor))
    output.mkdir(parents=True, exist_ok=True)
    (output/'run.json').write_text(json.dumps({'status':'running'}), encoding='utf-8')
    sys.path.insert(0, str((vendor/'src').resolve()))
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
    plan = json.loads((experiment/'plan.json').read_text(encoding='utf-8'))
    rows = read_rows(audit/'manifest.jsonl')
    rowmap = {r['image']:r for r in rows}
    from torchvision.transforms import functional as TF
    norm = transforms.Normalize([.485,.456,.406],[.229,.224,.225])
    records=[]
    started=time.perf_counter()
    for backbone in ('rn18','wrn50'):
        if backbone=='rn18': model=models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        else: model=models.wide_resnet50_2(weights=models.Wide_ResNet50_2_Weights.IMAGENET1K_V1)
        model.eval().requires_grad_(False)
        sampler=RecordingSampler(.1,torch.device('cpu'))
        pc=patchcore.patchcore.PatchCore(torch.device('cpu'))
        pc.load(model,['layer2','layer3'],torch.device('cpu'),(3,224,224),1024,1024,
                patchsize=3,anomaly_score_num_nn=1,featuresampler=sampler,
                nn_method=patchcore.common.FaissNN(False,4))
        for category in CATEGORIES:
            output_cat=output/backbone/category
            output_cat.mkdir(parents=True,exist_ok=True)
            if all((output_cat/f'seed{seed}.json').exists() for seed in SEEDS):
                records.extend(json.loads((output_cat/f'seed{seed}.json').read_text(encoding='utf-8')) for seed in SEEDS)
                print(f'{backbone}/{category}: all five saved seeds found; skipping',flush=True)
                continue
            queries=sorted([r for r in rows if r['object']==category and r['split'] in ('calibration','test')],key=lambda r:r['image'])
            tests=[r for r in queries if r['split']=='test']
            union=[] if backbone=='wrn50' else sorted({n for s in SEEDS for n in plan['selection'][str(s)][category]})
            names=union+[r['image'] for r in queries]
            index={n:i for i,n in enumerate(names)}
            feature_path=output_cat/'temporary-features.npy'
            feats=np.lib.format.open_memmap(feature_path,mode='w+',dtype='float32',shape=(len(names),784,1024))
            preprocessing='crop'
            transform=transforms.Compose([transforms.Resize(256),transforms.CenterCrop(224),transforms.ToTensor(),norm])
            for start in range(0,len(names),4):
                batch=[]
                for name in names[start:start+4]:
                    source=safe_path(root,name)
                    if sha256(source)!=rowmap[name]['image_sha256']: raise ValueError(f'Source changed: {name}')
                    with Image.open(source) as image: batch.append(transform(image.convert('RGB')))
                with torch.inference_mode(): embedded=np.asarray(pc._embed(torch.stack(batch)),dtype=np.float32)
                feats[start:start+len(batch)]=embedded.reshape(len(batch),784,1024)
                if start % 80 == 0: print(f'{backbone}/{category}: embedded {start+len(batch)}/{len(names)}',flush=True)
            feats.flush()
            query_features=feats[len(union):].reshape(-1,1024)
            feature_map=feats
            del feats
            gc.collect()
            # Build and evaluate the five reference banks; WRN banks are the exact retained banks.
            for seed in SEEDS:
                saved_result=output_cat/f'seed{seed}.json'
                if saved_result.exists():
                    records.append(json.loads(saved_result.read_text(encoding='utf-8')))
                    continue
                if backbone=='wrn50':
                    bank=np.load(previous/f'wrn/{category}/seed{seed}-bank.npy')
                else:
                    selected=plan['selection'][str(seed)][category]
                    selected_map=np.load(feature_path,mmap_mode='r')
                    reference_features=np.asarray(selected_map[[index[n] for n in selected]]).reshape(-1,1024)
                    selected_map._mmap.close(); del selected_map
                    selected_indices=np.load(experiment/f'rn18_crop/{category}/seed{seed}-indices.npy')
                    if selected_indices.shape!=(5017,) or selected_indices.min()<0 or selected_indices.max()>=len(reference_features):
                        raise ValueError('Stored ResNet coreset indices do not match selected references')
                    bank=reference_features[selected_indices]
                    del reference_features
                if bank.shape!=(5017,1024): raise ValueError('Unexpected memory bank shape')
                pc.anomaly_scorer.fit([bank])
                masks=[]; score_maps=[]
                for row in tests:
                    qi=queries.index(row)
                    q=np.asarray(query_features[qi*784:(qi+1)*784],dtype=np.float32)
                    patch=pc.anomaly_scorer.predict([q])[0].reshape(1,28,28)
                    score_maps.append(pc.anomaly_segmentor.convert_to_segmentation(patch)[0].astype(np.float32))
                    if row['mask']:
                        masks.append(transform_mask(safe_path(root,row['mask']),preprocessing,TF.resize,TF.center_crop,InterpolationMode.NEAREST))
                    else:
                        masks.append(np.zeros((224,224),dtype=bool))
                mask_arr=np.asarray(masks,dtype=bool); map_arr=np.asarray(score_maps,dtype=np.float32)
                pixel_auroc,pixel_ap=binary_ranking_metrics(mask_arr.ravel(),map_arr.ravel())
                result={'backbone':backbone,'preprocessing':'official Resize(256)+CenterCrop(224)','category':category,'reference_seed':int(seed),
                        'pixel_auroc':pixel_auroc,'pixel_average_precision':pixel_ap,'aupro_fpr_0_30':pro_auc(mask_arr,map_arr),
                        'test_images':len(tests),'anomaly_images':sum(bool(r['mask']) for r in tests),'positive_pixels':int(mask_arr.sum()),
                        'pixel_count':int(mask_arr.size),'mask_policy':'nearest-neighbour resize; same geometric transform as RGB',
                        'map_policy':'upstream PatchCore 28x28 patch distances, bilinear 224x224, Gaussian sigma=4'}
                atomic_json(saved_result,result)
                records.append(result)
                print(f"{backbone}/{category}/seed{seed}: AUROC={pixel_auroc:.4f} AP={pixel_ap:.4f} PRO={result['aupro_fpr_0_30']:.4f}",flush=True)
                del masks,score_maps,mask_arr,map_arr,bank
            del query_features
            feature_map._mmap.close(); del feature_map
            gc.collect()
            feature_path.unlink()
        del pc,model,sampler
        gc.collect()
    # Macro-average categories, retaining the seed-level replicates.
    summary=[]
    for backbone in ('rn18','wrn50'):
        for category in CATEGORIES:
            part=[r for r in records if r['backbone']==backbone and r['category']==category]
            summary.append({'backbone':backbone,'category':category,**{key:{'mean':float(np.mean([r[key] for r in part])),'sd':float(np.std([r[key] for r in part],ddof=1))} for key in ('pixel_auroc','pixel_average_precision','aupro_fpr_0_30')}})
    aggregate={}
    for backbone in ('rn18','wrn50'):
        part=[r for r in records if r['backbone']==backbone]
        aggregate[backbone]={key:{'macro_category_mean':float(np.mean([r[key] for r in part])),
                                  'sd_across_seed_macro_category_means':float(np.std([
                                      np.mean([r[key] for r in part if r['reference_seed']==seed]) for seed in SEEDS
                                  ],ddof=1))} for key in ('pixel_auroc','pixel_average_precision','aupro_fpr_0_30')}
    provenance={'device':'CPU','torch_threads':torch.get_num_threads(),'runner_sha256':sha256(Path(__file__)),
               'audit_manifest_sha256':sha256(audit/'manifest.jsonl'),'weights_sha256':plan.get('weights_sha256',{}),
               'versions':{name:importlib.metadata.version(name) for name in ('torch','torchvision','faiss-cpu','numpy','Pillow','scipy')}}
    atomic_json(output/'summary.json',{'category_seed_results':records,'category_summary':summary,'aggregate':aggregate,'provenance':provenance,
              'protocol':{'models':'Controlled PatchCore ResNet18 and WideResNet50-2, pretrained ImageNet1K V1','bank_bytes':5017*1024*4,
                          'seeds':list(SEEDS),'test_images_total':sum(1 for r in rows if r['split']=='test'),
                          'threshold_selection':'none; ranking metrics','aupro':'200 thresholds, FPR truncated at 0.30, normalized area'},
              'elapsed_seconds':time.perf_counter()-started})
    atomic_json(output/'run.json',{'status':'complete','elapsed_seconds':time.perf_counter()-started})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name,default in dict(output='data/visa-localization-v1',experiment='data/visa-controlled-v1',previous='data/visa-five-seeds-v1',
                             audit='data/visa-audit-v1',root='data/visa-pcb-v2',cache='data/torch-cache',vendor='data/vendor/patchcore-inspection').items():
        p.add_argument('--'+name,type=Path,default=Path(default))
    a=p.parse_args()
    run(a.output,a.experiment,a.previous,a.audit,a.root,a.cache,a.vendor)


if __name__=='__main__': main()
