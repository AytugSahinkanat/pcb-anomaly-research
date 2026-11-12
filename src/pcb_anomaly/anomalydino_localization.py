"""CPU evaluation of the pinned AnomalyDINO pipeline on VisA PCB categories.

The evaluation domain matches the PatchCore localization benchmark: Resize(256),
CenterCrop(224), then enlargement to 448 for DINOv2 ViT-S/14. Five saved
reference lists are reused (first 16 images); no test-set tuning is performed.
"""
import argparse
import gc
import importlib.metadata
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from sklearn.decomposition import PCA
from torchvision import transforms
from torchvision.transforms import InterpolationMode

from .crops import read_rows, sha256
from .multiseed import SEEDS
from .visa import CATEGORIES, safe_path
from .visa_benchmark import ranking_metrics
from .visa_localization import binary_ranking_metrics, pro_auc, transform_mask


ANGLES = (0, 45, 90, 135, 180, 225, 270, 315)
PATCHES = 32 * 32
DIM = 384


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    tmp.replace(path)


def prepare_rgb(path, transform):
    with Image.open(path) as im:
        image = transform(im.convert('RGB'))
    return np.asarray(image.resize((448, 448), Image.Resampling.BICUBIC))


def rotate(image, angle):
    center = tuple(np.array(image.shape[1::-1]) / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, image.shape[1::-1], flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_DEFAULT)


def features_for_images(model, images, batch_size=4):
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=(.485, .456, .406), std=(.229, .224, .225)),
    ])
    output = []
    with torch.inference_mode():
        for start in range(0, len(images), batch_size):
            batch = torch.stack([transform(Image.fromarray(im)) for im in images[start:start + batch_size]])
            h, w = batch.shape[-2:]
            batch = batch[:, :, :h - h % 14, :w - w % 14]
            tokens = model.get_intermediate_layers(batch)[0]
            output.extend(tokens.cpu().numpy().astype(np.float32))
    return output


def foreground_mask(features, shape, masking=True, threshold=10, kernel_size=3, border=.2):
    if not masking:
        return np.ones(len(features), dtype=bool)
    pc = PCA(n_components=1, svd_solver='randomized').fit_transform(features.astype(np.float32))
    mask = pc > threshold
    grid = mask.reshape(shape)
    center = grid[int(shape[0]*border):int(shape[0]*(1-border)),
                  int(shape[1]*border):int(shape[1]*(1-border))]
    if center.sum() <= center.size * .35:
        mask = -pc > threshold
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((kernel_size, kernel_size), np.uint8)).astype(bool)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE,
                            np.ones((kernel_size, kernel_size), np.uint8)).astype(bool)
    return mask.squeeze()


def valid_feature_cache(features):
    for start in range(0, features.shape[0], 16):
        chunk = np.asarray(features[start:start+16])
        if not np.isfinite(chunk).all() or np.any(np.linalg.norm(chunk, axis=2) == 0):
            return False
    return True


def run(output, experiment, audit, root, cache, category=None, only_seed=None):
    output, experiment, audit, root, cache = map(Path, (output, experiment, audit, root, cache))
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output/'run.json', {'status': 'running', 'started_unix': time.time()})
    plan = json.loads((experiment / 'plan.json').read_text(encoding='utf-8'))
    rows = read_rows(audit / 'manifest.jsonl')
    rowmap = {r['image']: r for r in rows}
    selected_categories = (category,) if category else CATEGORIES
    selected_seeds = (only_seed,) if only_seed is not None else SEEDS

    torch.set_num_threads(4)
    torch.manual_seed(42)
    np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    faiss = __import__('faiss')
    faiss.omp_set_num_threads(4)
    repo = cache / 'facebookresearch_dinov2_7764ea0f912e53c92e82eb78a2a1631e92725fc8'
    checkpoint = cache / 'checkpoints' / 'dinov2_vits14_pretrain.pth'
    if not (repo / 'hubconf.py').is_file() or not checkpoint.is_file():
        raise FileNotFoundError('Pinned local DINOv2 source or checkpoint is missing')
    model = torch.hub.load(str(repo.resolve()), 'dinov2_vits14', source='local', pretrained=False)
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    model.load_state_dict(state, strict=True)
    del state
    model.eval().cpu()
    image_transform = transforms.Compose([
        transforms.Resize(256, interpolation=InterpolationMode.BICUBIC, antialias=True),
        transforms.CenterCrop(224),
    ])
    records = []
    started = time.perf_counter()

    for cat in selected_categories:
        cat_dir = output / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        queries = sorted([r for r in rows if r['object'] == cat and r['split'] in ('calibration', 'test')],
                         key=lambda r: r['image'])
        tests = [r for r in queries if r['split'] == 'test']
        if all((output / cat / f'seed{seed}.json').exists() for seed in selected_seeds):
            records.extend(json.loads((output / cat / f'seed{seed}.json').read_text(encoding='utf-8'))
                           for seed in selected_seeds)
            print(f'{cat}: all selected seed results found; skipping feature extraction', flush=True)
            continue
        ref_union = sorted({name for seed in selected_seeds for name in plan['selection'][str(seed)][cat][:16]})
        ref_start = 0
        ref_index = {name: i for i, name in enumerate(ref_union)}
        query_index = {r['image']: len(ref_union) * len(ANGLES) + i for i, r in enumerate(queries)}
        feature_file = cat_dir / 'temporary-features.npy'
        feature_meta = cat_dir / 'temporary-features.json'
        expected_shape = (len(ref_union)*len(ANGLES)+len(queries), PATCHES, DIM)
        signature = {'shape': list(expected_shape), 'refs': ref_union,
                     'queries': [r['image'] for r in queries],
                     'manifest_sha256': sha256(audit/'manifest.jsonl'),
                     'checkpoint_sha256': sha256(checkpoint),
                     'preprocessing': 'Resize256-CenterCrop224-BICUBIC-448; rotate OpenCV bilinear BORDER_DEFAULT'}
        use_cache = False
        if feature_file.exists() and feature_meta.exists():
            try:
                use_cache = json.loads(feature_meta.read_text(encoding='utf-8')) == signature
            except (OSError, json.JSONDecodeError):
                use_cache = False
        elif feature_file.exists():
            # Recover an interrupted run that finished writing features before
            # its first score/metric calculation failed.
            probe = np.lib.format.open_memmap(feature_file, mode='r+', dtype='float32', shape=expected_shape)
            cache_valid = valid_feature_cache(probe)
            for name in ref_union + [r['image'] for r in queries]:
                cache_valid = cache_valid and sha256(safe_path(root, name)) == rowmap[name]['image_sha256']
            probe._mmap.close()
            use_cache = bool(cache_valid)
            if use_cache:
                feature_meta.write_text(json.dumps(signature, indent=2), encoding='utf-8')
        if use_cache:
            features = np.lib.format.open_memmap(feature_file, mode='r+', dtype='float32', shape=expected_shape)
            if not valid_feature_cache(features):
                use_cache = False
                features._mmap.close()
        if not use_cache:
            features = np.lib.format.open_memmap(feature_file, mode='w+', dtype='float32', shape=expected_shape)

        # Cache deterministic features once per unique reference/query to avoid
        # rerunning DINOv2 for each of the five reference selections.
        views, destinations = [], []
        for name in ref_union:
            source = safe_path(root, name)
            if sha256(source) != rowmap[name]['image_sha256']:
                raise ValueError(f'Source image changed: {name}')
            base = prepare_rgb(source, image_transform)
            for angle in ANGLES:
                views.append(rotate(base, angle))
                destinations.append(ref_index[name] * len(ANGLES) + ANGLES.index(angle))
        for row in queries:
            source = safe_path(root, row['image'])
            if sha256(source) != rowmap[row['image']]['image_sha256']:
                raise ValueError(f'Source image changed: {row["image"]}')
            views.append(prepare_rgb(source, image_transform))
            destinations.append(query_index[row['image']])

        if use_cache:
            print(f'{cat}: reusing verified feature cache ({features.shape[0]} views)', flush=True)
        else:
            for start in range(0, len(views), 4):
                batch_features = features_for_images(model, views[start:start+4])
                for j, feat in enumerate(batch_features):
                    if feat.shape != (PATCHES, DIM):
                        raise ValueError(f'Unexpected DINO feature shape {feat.shape}; expected {(PATCHES, DIM)}')
                    features[destinations[start+j]] = feat
                if start % 80 == 0:
                    print(f'{cat}: extracted {min(start+4, len(views))}/{len(views)} views', flush=True)
        del views, destinations
        features.flush()
        if not use_cache:
            feature_meta.write_text(json.dumps(signature, indent=2), encoding='utf-8')
        else:
            # A previous interrupted run may have completed extraction but not
            # written its cache signature. Validate all vectors and the source
            # hashes before blessing that cache for a resumable continuation.
            for name in ref_union + [r['image'] for r in queries]:
                if sha256(safe_path(root, name)) != rowmap[name]['image_sha256']:
                    raise ValueError(f'Source image changed: {name}')
            if not feature_meta.exists():
                if not valid_feature_cache(features):
                    raise ValueError('Unmarked DINO feature cache is incomplete or invalid')
                feature_meta.write_text(json.dumps(signature, indent=2), encoding='utf-8')

        for seed in selected_seeds:
            result_path = cat_dir / f'seed{seed}.json'
            if result_path.exists():
                records.append(json.loads(result_path.read_text(encoding='utf-8')))
                continue
            references = plan['selection'][str(seed)][cat][:16]
            bank_parts = []
            for name in references:
                idx = ref_index[name]
                augmented = np.asarray(features[idx*8:(idx+1)*8])
                for view in augmented:
                    mask = foreground_mask(view, (32, 32), masking=True)
                    bank_parts.append(view[mask])
            bank = np.concatenate(bank_parts).astype(np.float32)
            bank = np.ascontiguousarray(bank)
            faiss.normalize_L2(bank)
            index = faiss.IndexFlatL2(DIM)
            index.add(bank)
            scores, maps, masks = [], [], []
            for test_index, row in enumerate(tests):
                feat = np.asarray(features[query_index[row['image']]], dtype=np.float32).copy()
                active = foreground_mask(feat, (32, 32), masking=True)
                selected = np.ascontiguousarray(feat[active])
                faiss.normalize_L2(selected)
                dist = np.empty(len(selected), dtype=np.float32)
                for start in range(0, len(selected), 64):
                    block, _ = index.search(selected[start:start+64], 1)
                    dist[start:start+len(block)] = block[:, 0]
                dist = (dist / 2).astype(np.float32)  # normalized L2^2 / 2 = cosine distance
                patch_dist = np.zeros(PATCHES, dtype=np.float32)
                patch_dist[active] = dist
                scores.append(float(np.mean(np.sort(patch_dist)[-max(1, int(np.ceil(PATCHES*.01))):])))
                raw_map = patch_dist.reshape(32, 32)
                map448 = cv2.resize(raw_map, (448, 448), interpolation=cv2.INTER_LINEAR)
                # Return to the shared 224x224 evaluation field after the
                # upstream sigma=4 smoothing at the model's 448px resolution.
                from scipy.ndimage import gaussian_filter
                map448 = gaussian_filter(map448, sigma=4)
                maps.append(cv2.resize(map448, (224, 224), interpolation=cv2.INTER_AREA).astype(np.float32))
                if row['mask']:
                    masks.append(transform_mask(safe_path(root, row['mask']), 'crop',
                                                transforms.functional.resize,
                                                transforms.functional.center_crop,
                                                InterpolationMode.NEAREST))
                else:
                    masks.append(np.zeros((224, 224), dtype=bool))
                if test_index % 20 == 0:
                    print(f'{cat}/seed{seed}: scored {test_index+1}/{len(tests)} test images', flush=True)
            labels = np.asarray([bool(r['mask']) for r in tests], dtype=np.uint8)
            image_metrics = ranking_metrics(labels, scores)
            image_auroc, image_ap = image_metrics['auroc'], image_metrics['average_precision']
            mask_arr = np.asarray(masks, dtype=bool)
            map_arr = np.asarray(maps, dtype=np.float32)
            pixel_auroc, pixel_ap = binary_ranking_metrics(mask_arr.ravel(), map_arr.ravel())
            record = {
                'method': 'AnomalyDINO official pipeline adaptation', 'backbone': 'DINOv2 ViT-S/14',
                'preprocessing': 'Resize(256)+CenterCrop(224), enlarge to 448x448',
                'category': cat, 'reference_seed': int(seed), 'reference_images': len(references),
                'rotation_degrees': list(ANGLES), 'reference_patch_count': int(len(bank)),
                'reference_bank_bytes': int(bank.nbytes),
                'image_auroc': image_auroc, 'image_average_precision': image_ap,
                'pixel_auroc': pixel_auroc, 'pixel_average_precision': pixel_ap,
                'aupro_fpr_0_30': pro_auc(mask_arr, map_arr),
                'test_images': len(tests), 'anomaly_images': int(labels.sum()),
                'positive_pixels': int(mask_arr.sum()), 'pixel_count': int(mask_arr.size),
                'masking': 'upstream PCA foreground mask, threshold=10, 3x3 dilate+close',
                'score': 'mean of largest 1% patch cosine distances',
                'map': 'bilinear patch upsample to 448, Gaussian sigma=4, area downsample to common 224 field',
            }
            atomic_json(result_path, record)
            records.append(record)
            print(f"{cat}/seed{seed}: image AUROC={image_auroc:.4f}, pixel AUROC={pixel_auroc:.4f}, AP={pixel_ap:.4f}, PRO={record['aupro_fpr_0_30']:.4f}", flush=True)
            del index, bank, bank_parts, scores, maps, masks, mask_arr, map_arr
            gc.collect()
        features._mmap.close()
        del features
        feature_file.unlink(missing_ok=True)
        gc.collect()

    versions = {n: importlib.metadata.version(n) for n in ('torch', 'torchvision', 'faiss-cpu', 'numpy', 'scipy', 'scikit-learn')}
    summary = {'category_seed_results': records, 'provenance': {
        'device': 'CPU', 'torch_threads': torch.get_num_threads(), 'weights_sha256': plan.get('weights_sha256', {}),
        'audit_manifest_sha256': sha256(audit/'manifest.jsonl'), 'runner_sha256': sha256(Path(__file__)),
        'dinov2_checkpoint_sha256': sha256(checkpoint),
        'versions': versions, 'elapsed_seconds': time.perf_counter()-started,
    }, 'protocol': {'seeds': list(selected_seeds), 'categories': list(selected_categories),
                    'references_per_category': 16, 'test_selection': 'official VisA test; ranking metrics only',
                    'mask_threshold_selection': 'none; no test tuning'}}
    atomic_json(output/'summary.json', summary)
    atomic_json(output/'run.json', {'status': 'complete', 'elapsed_seconds': time.perf_counter()-started})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('data/visa-anomalydino-v1'))
    p.add_argument('--experiment', type=Path, default=Path('data/visa-controlled-v1'))
    p.add_argument('--audit', type=Path, default=Path('data/visa-audit-v1'))
    p.add_argument('--root', type=Path, default=Path('data/visa-pcb-v2'))
    p.add_argument('--cache', type=Path, default=Path('data/torch-cache'))
    p.add_argument('--category', choices=CATEGORIES)
    p.add_argument('--seed', type=int, choices=SEEDS)
    args = p.parse_args()
    run(args.output, args.experiment, args.audit, args.root, args.cache, args.category, args.seed)


if __name__ == '__main__':
    main()
