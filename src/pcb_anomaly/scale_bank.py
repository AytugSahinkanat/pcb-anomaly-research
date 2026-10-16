"""Resolution-augmented reference bank; views collapse to original sample IDs."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from PIL import Image
from .crops import read_rows, sha256, square_input
from .sensitivity import transform, aggregate


def collapsed_scores(views, query):
    views = np.asarray(views)
    if views.ndim != 3 or query.shape != (views.shape[2],) or not np.isfinite(views).all() or not np.isfinite(query).all():
        raise ValueError('Invalid bank/query')
    return np.clip(np.max(views @ query, axis=0), -1, 1)


def compare_scores(original, changed, indices):
    if not len(indices):
        return None
    a, b = original[indices], changed[indices]
    ra, rb = np.argsort(-a,kind='stable'),np.argsort(-b,kind='stable')
    k=min(5,len(indices))
    return dict(top1_retained=bool(ra[0]==rb[0]),top5_overlap=len(set(ra[:k])&set(rb[:k]))/k,k=k,
                original_top1=int(indices[ra[0]]),changed_top1=int(indices[rb[0]]),
                top1_cosine_delta=float(b[rb[0]]-a[ra[0]]))


def experiment(features_dir,sensitivity_dir,crop_dir,output,cache):
    import torch
    import torchvision
    from torchvision.models import resnet18,ResNet18_Weights
    from torchvision.transforms.functional import to_tensor,normalize
    features_dir,sensitivity_dir,crop_dir,output,cache=map(Path,(features_dir,sensitivity_dir,crop_dir,output,cache))
    if output.exists(): raise FileExistsError(output)
    base=json.loads((features_dir/'run.json').read_text())
    prior=json.loads((sensitivity_dir/'run.json').read_text())
    if base['status']!='complete' or prior['status']!='complete' or sha256(features_dir/'features.npy')!=base['features_sha256'] or prior['baseline_features_sha256']!=base['features_sha256'] or sha256(features_dir/'samples.jsonl')!=prior['samples_sha256']:
        raise ValueError('Baseline provenance mismatch')
    rows=read_rows(features_dir/'samples.jsonl')
    features=np.load(features_dir/'features.npy',allow_pickle=False)
    refs=[i for i,r in enumerate(rows) if r['split']=='reference']
    queries=[i for i,r in enumerate(rows) if r['split']=='calibration']
    if [r['sample_id'] for r in read_rows(sensitivity_dir/'queries.jsonl')]!=[rows[i]['sample_id'] for i in queries]:
        raise ValueError('Query order mismatch')
    conditions=('identity','down50','down25')
    qfeatures={v:np.load(sensitivity_dir/(v+'.npy'),allow_pickle=False) for v in conditions}
    np.testing.assert_allclose(qfeatures['identity'],features[queries],atol=1e-6,rtol=1e-5)
    torch.set_num_threads(4); torch.manual_seed(42); torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    weights=ResNet18_Weights.IMAGENET1K_V1
    if sha256(cache/'checkpoints'/weights.url.rsplit('/',1)[-1])!=base['weights_sha256']:
        raise ValueError('Weights mismatch')
    model=resnet18(weights=weights).eval(); model.fc=torch.nn.Identity(); model.requires_grad_(False)
    images=[]
    for i in refs:
        path=(crop_dir/rows[i]['crop_path']).resolve()
        if not path.is_relative_to(crop_dir.resolve()) or sha256(path)!=rows[i]['crop_sha256']:
            raise ValueError('Crop mismatch')
        with Image.open(path) as image: images.append(image.convert('RGB'))
    output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    bank=[features[refs]]
    for condition in conditions[1:]:
        chunks=[]
        with torch.inference_mode():
            for start in range(0,len(images),32):
                batch=[normalize(to_tensor(square_input(transform(im,condition))),[.485,.456,.406],[.229,.224,.225]) for im in images[start:start+32]]
                x=model(torch.stack(batch)); norms=x.norm(dim=1,keepdim=True)
                if not torch.isfinite(x).all() or (norms<=0).any(): raise ValueError('Invalid features')
                chunks.append((x/norms).numpy())
                if start%1024==0: print(condition,min(start+32,len(images)),'/',len(images),flush=True)
        value=np.concatenate(chunks); np.save(output/(condition+'.npy'),value,allow_pickle=False); bank.append(value)
    bank=np.stack(bank)
    records=[]; summary={}
    original_scores=[collapsed_scores(bank,q) for q in qfeatures['identity']]
    for condition in conditions:
        part=[]
        for j,qi in enumerate(queries):
            q=rows[qi]
            eligible=[k for k,i in enumerate(refs) if rows[i]['board_group']!=q['board_group']]
            same=[k for k in eligible if rows[refs[k]]['category']==q['category']]
            scores=collapsed_scores(bank,qfeatures[condition][j])
            unres=compare_scores(original_scores[j],scores,eligible)
            part.append(dict(variant=condition,sample_id=q['sample_id'],category=q['category'],board_group=q['board_group'],
                embedding_cosine=float(np.clip(qfeatures['identity'][j]@qfeatures[condition][j],-1,1)),
                same_category=compare_scores(original_scores[j],scores,same),unrestricted=unres,
                category_agreement=rows[refs[unres['changed_top1']]]['category']==q['category']))
        summary[condition]=dict(overall=aggregate(part),
            by_category={c:aggregate([r for r in part if r['category']==c]) for c in sorted({r['category'] for r in part})},
            by_board={b:aggregate([r for r in part if r['board_group']==b]) for b in sorted({r['board_group'] for r in part})})
        records.extend(part); print(condition,json.dumps(summary[condition]['overall']),flush=True)
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output/'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    (output/'reference.jsonl').write_text(''.join(json.dumps(dict(rows[i],bank_index=k))+'\n' for k,i in enumerate(refs)),encoding='utf-8')
    run=dict(status='complete',method='max cosine over original/50%/25% reference views per unique component; query unchanged',
        protocol='calibration to reference; cross-board; test excluded; k counts unique components',
        reference_count=len(refs),query_count=len(queries),weights_sha256=base['weights_sha256'],
        baseline_features_sha256=base['features_sha256'],samples_sha256=prior['samples_sha256'],
        cached_queries_sha256={v:sha256(sensitivity_dir/(v+'.npy')) for v in conditions},
        outputs_sha256={p.name:sha256(p) for p in output.glob('*.npy')},
        torch=torch.__version__,torchvision=torchvision.__version__,numpy=np.__version__,threads=4,batch_size=32,seed=42,
        elapsed_seconds=time.perf_counter()-started)
    (output/'run.json').write_text(json.dumps(run,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('features','sensitivity','crops','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('data/torch-cache'))
    a=p.parse_args(); experiment(a.features,a.sensitivity,a.crops,a.output,a.cache)
