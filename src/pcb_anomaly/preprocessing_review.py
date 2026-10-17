"""Diagnostic mask geometry and deterministic examples; never filters evaluation data."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .crops import read_rows, square_input
from .visa import CATEGORIES, safe_path


def review(root, audit, output):
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root,audit,output=map(Path,(root,audit,output))
    rows=sorted([r for r in read_rows(audit/'manifest.jsonl') if r['split']=='test' and r['is_anomaly']],key=lambda r:r['image'])
    mask_resize=transforms.Resize(256,interpolation=InterpolationMode.NEAREST)
    crop=transforms.CenterCrop(224)
    image_transform=transforms.Compose([transforms.Resize(256),crop])
    details=[]; examples={}
    for row in rows:
        with Image.open(safe_path(root,row['mask'])) as im:
            mask=Image.fromarray((np.asarray(im)>0).astype('uint8')*255)
        side=max(mask.size); padded=Image.new('L',(side,side))
        padded.paste(mask,((side-mask.width)//2,(side-mask.height)//2))
        square=padded.resize((224,224),Image.Resampling.NEAREST)
        resized=mask_resize(mask); cropped=crop(resized)
        details.append(dict(image=row['image'],category=row['object'],
                            square_pixels=int(np.count_nonzero(square)),crop_pixels=int(np.count_nonzero(cropped)),
                            resized_pixels=int(np.count_nonzero(resized)),
                            approximate_linear_scale_ratio=(256/min(mask.size))/(224/max(mask.size))))
        if row['object'] not in examples:
            with Image.open(safe_path(root,row['image'])) as im: original=im.convert('RGB')
            examples[row['object']]=(row['image'],[original,square_input(original),image_transform(original)],[mask,square,cropped])
    summaries=[]
    for category in CATEGORIES:
        group=[r for r in details if r['category']==category]
        summaries.append(dict(category=category,images=len(group),
                              square_empty=sum(r['square_pixels']==0 for r in group),
                              crop_empty=sum(r['crop_pixels']==0 for r in group),
                              partially_cropped=sum(r['crop_pixels']<r['resized_pixels'] for r in group),
                              median_square_pixels=float(np.median([r['square_pixels'] for r in group])),
                              median_crop_pixels=float(np.median([r['crop_pixels'] for r in group])),
                              median_linear_scale_ratio=float(np.median([r['approximate_linear_scale_ratio'] for r in group]))))
    result=dict(summary=summaries,details=details,
                interpretation='Diagnostic nearest-neighbor binary mask rasterization; all test images retained; no model settings changed. Mask area is not a localization metric.')
    (output/'preprocessing-review.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    fig,axes=plt.subplots(4,3,figsize=(8,10))
    for i,category in enumerate(CATEGORIES):
        name,images,masks=examples[category]
        for j,(im,mask) in enumerate(zip(images,masks)):
            ax=axes[i,j]; ax.imshow(im)
            a=np.asarray(mask)>0
            if a.any() and not a.all(): ax.contour(a,levels=[.5],colors=['red'],linewidths=.7)
            ax.set_xticks([]); ax.set_yticks([])
            if i==0: ax.set_title(['Original','Square pad → 224','Resize256 → crop224'][j])
            if j==0: ax.set_ylabel(f'{category}\n{name.rsplit("/",1)[-1]}')
    fig.suptitle('Preprocessing examples: first anomalous test image per category\nRed contours: annotated defects; examples are not a performance comparison',fontsize=10)
    fig.tight_layout(); fig.savefig(output/'preprocessing.png',dpi=180); fig.savefig(output/'preprocessing.pdf'); plt.close(fig)
    print(json.dumps(summaries,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/visa-pcb-v2'))
    p.add_argument('--audit',type=Path,default=Path('data/visa-audit-v1'))
    p.add_argument('--output',type=Path,default=Path('data/visa-controlled-v1'))
    a=p.parse_args(); review(a.root,a.audit,a.output)


if __name__=='__main__': main()
