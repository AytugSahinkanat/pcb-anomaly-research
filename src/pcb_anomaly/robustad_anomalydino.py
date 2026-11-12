"""Evaluate the AnomalyDINO pipeline on the audited RobustAD PCB domain splits."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

import cv2
import faiss
import numpy as np
import torch
from PIL import Image
from sklearn.decomposition import PCA
from torchvision.transforms.functional import normalize, to_tensor
from scipy.ndimage import gaussian_filter

from .audit_robustad_pcb import DEFECTS, REVISION
from .crops import sha256
from .robustad_patchcore import (
    DOMAIN_LABELS,
    FEATURE_DIM,
    IMAGE_SIZE,
    PATCH_COUNT,
    REFERENCE_COUNT,
    SEEDS,
    SPLITS,
    load_records,
    preprocess_mask,
    select_references,
)
from .visa_benchmark import ranking_metrics
from .visa_localization import binary_ranking_metrics, pro_auc


ANGLES = (0, 45, 90, 135, 180, 225, 270, 315)
DINO_DIM = 384
DINO_SIZE = 448
DINO_PATCH_COUNT = 1024
DINO_REPO = "facebookresearch/dinov2"
DINO_REVISION = "7764ea0f912e53c92e82eb78a2a1631e92725fc8"
DINO_CHECKPOINT = "dinov2_vits14_pretrain.pth"


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def rotate(image: np.ndarray, angle: int) -> np.ndarray:
    center = tuple(np.array(image.shape[1::-1]) / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, image.shape[1::-1], flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_DEFAULT)


def preprocess_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("RGB").resize((DINO_SIZE, DINO_SIZE), Image.Resampling.BICUBIC)
        return np.asarray(image)


def foreground_mask(features: np.ndarray, threshold: float = 10.0, kernel_size: int = 3,
                    border: float = .2) -> np.ndarray:
    pc = PCA(n_components=1, svd_solver="randomized", random_state=42).fit_transform(features.astype(np.float32))
    mask = pc > threshold
    grid = mask.reshape(32, 32)
    center = grid[int(32 * border):int(32 * (1 - border)), int(32 * border):int(32 * (1 - border))]
    if center.sum() <= center.size * .35:
        mask = -pc > threshold
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((kernel_size, kernel_size), np.uint8)).astype(bool)
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE,
                            np.ones((kernel_size, kernel_size), np.uint8)).astype(bool)
    return mask.reshape(-1)


def prepare_foreground_masks(features: np.ndarray) -> np.ndarray:
    masks = np.empty((features.shape[0], DINO_PATCH_COUNT), dtype=bool)
    for index in range(features.shape[0]):
        masks[index] = foreground_mask(features[index])
        if index % 100 == 0 or index + 1 == features.shape[0]:
            print(f"Prepared PCA foreground masks {index + 1}/{features.shape[0]}", flush=True)
    return masks


def embed_batch(model, images: list[np.ndarray], torch_module) -> np.ndarray:
    tensors = torch_module.stack([
        normalize(to_tensor(Image.fromarray(image)), [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        for image in images
    ])
    if tensors.shape[-2:] != (DINO_SIZE, DINO_SIZE):
        raise ValueError(f"Expected {DINO_SIZE}x{DINO_SIZE} input, got {tensors.shape[-2:]}")
    with torch_module.inference_mode():
        tokens = model.get_intermediate_layers(tensors)[0]
    output = tokens.cpu().numpy().astype(np.float32)
    if output.shape != (len(images), DINO_PATCH_COUNT, DINO_DIM):
        raise ValueError(f"Unexpected DINOv2 tokens {output.shape}")
    return output


def scores_to_map(distances: np.ndarray) -> np.ndarray:
    raw = distances.reshape(32, 32)
    upsampled = cv2.resize(raw, (DINO_SIZE, DINO_SIZE), interpolation=cv2.INTER_LINEAR)
    smoothed = gaussian_filter(upsampled, sigma=4)
    common = cv2.resize(smoothed, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_AREA)
    return common.astype(np.float32)


def evaluate(output: Path, root: Path, cache: Path) -> dict:
    output, root, cache = map(Path, (output, root, cache))
    audit = json.loads(Path("reports/robustad-pcb-audit-v1.json").read_text(encoding="utf-8"))
    if audit.get("revision") != REVISION or audit.get("total_images_verified") != 1260:
        raise ValueError("Expected the audited, pinned RobustAD PCB revision")
    references, tests, duplicate_groups = load_records(root)
    selections = select_references(references)
    reference_union = sorted({name for per_seed in selections.values() for name in per_seed})
    reference_index = {name: index for index, name in enumerate(reference_union)}
    records = references + tests
    reference_lookup = {row["image"]: row for row in references}
    test_lookup = {row["image"]: row for row in tests}
    test_offset = len(reference_union) * len(ANGLES)
    test_index = {row["image"]: test_offset + index for index, row in enumerate(tests)}
    feature_shape = (test_offset + len(tests), DINO_PATCH_COUNT, DINO_DIM)

    cache_root = cache / f"dinov2_{DINO_REVISION}"
    checkpoint = cache / "checkpoints" / DINO_CHECKPOINT
    repo = cache / f"facebookresearch_dinov2_{DINO_REVISION}"
    if not (repo / "hubconf.py").is_file() or not checkpoint.is_file():
        raise FileNotFoundError("Pinned local DINOv2 source or ViT-S/14 checkpoint is missing")
    checkpoint_hash = sha256(checkpoint)
    runner_hash = sha256(Path(__file__))
    signature = {
        "dataset_revision": REVISION,
        "feature_contract": "dinov2-vit-s14-fullframe-448-bicubic-v1",
        "dino_revision": DINO_REVISION,
        "checkpoint_sha256": checkpoint_hash,
        "reference_selections": selections,
        "reference_union": reference_union,
        "test_images": [row["image"] for row in tests],
        "source_sha256": [{"image": row["image"], "sha256": sha256(row["image_path"])} for row in records],
        "preprocessing": "full-frame RGB bicubic resize to 448x448; ImageNet normalization",
        "feature_shape": list(feature_shape),
    }
    output.mkdir(parents=True, exist_ok=True)
    feature_file = output / "features.npy"
    signature_file = output / "features.signature.json"
    summary_file = output / "summary.json"
    atomic_json(output / "run.json", {"status": "running", "started_unix": time.time()})
    atomic_json(output / "reference-selections.json", {
        "dataset_revision": REVISION,
        "policy": "same five SHA-256-ranked 16-image selections as PatchCore",
        "selections": selections,
    })

    use_cache = False
    if feature_file.is_file() and signature_file.is_file():
        try:
            use_cache = json.loads(signature_file.read_text(encoding="utf-8")) == signature
        except (OSError, json.JSONDecodeError):
            use_cache = False
    if use_cache:
        features = np.load(feature_file, mmap_mode="r+")
        if features.shape != feature_shape:
            del features
            use_cache = False
    else:
        features = None

    torch.set_num_threads(4)
    torch.manual_seed(42)
    np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    faiss.omp_set_num_threads(4)
    model = torch.hub.load(str(repo.resolve()), "dinov2_vits14", source="local", pretrained=False)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    del state
    model.eval().cpu()

    started = time.perf_counter()
    if features is None:
        features = np.lib.format.open_memmap(feature_file, mode="w+", dtype="float32", shape=feature_shape)
        specifications = []
        for name in reference_union:
            idx = reference_index[name] * len(ANGLES)
            specifications.extend((name, angle, idx + order) for order, angle in enumerate(ANGLES))
        specifications.extend((row["image"], None, test_index[row["image"]]) for row in tests)
        rows_by_name = {row["image"]: row for row in records}
        for start in range(0, len(specifications), 4):
            batch_images = []
            for name, angle, _ in specifications[start:start + 4]:
                image = preprocess_rgb(rows_by_name[name]["image_path"])
                batch_images.append(rotate(image, angle) if angle is not None else image)
            batch_features = embed_batch(model, batch_images, torch)
            for offset, feature in enumerate(batch_features):
                features[specifications[start + offset][2]] = feature
            done = min(start + 4, len(specifications))
            if start % 80 == 0 or done == len(specifications):
                print(f"Embedded {done}/{len(specifications)} DINOv2 views", flush=True)
        features.flush()
        atomic_json(signature_file, signature)
    else:
        print(f"Reusing DINOv2 feature cache ({features.shape[0]} views)", flush=True)

    per_seed = []
    defect_results = []
    active_masks = prepare_foreground_masks(features)
    reference_masks = active_masks[:test_offset].reshape(len(reference_union), len(ANGLES), DINO_PATCH_COUNT)
    query_masks = active_masks[test_offset:]
    duplicate_pairs = {
        sorted(group["records"])[0]: group["record_mask_pairs"]
        for group in duplicate_groups if group["split"] == "pcb_data_dir_test4"
    }
    for seed in SEEDS:
        reference_names = selections[str(seed)]
        bank_parts = []
        for name in reference_names:
            base = reference_index[name] * len(ANGLES)
            for view_offset, feature in enumerate(np.asarray(features[base:base + len(ANGLES)])):
                active = reference_masks[reference_index[name], view_offset]
                bank_parts.append(feature[active])
        bank = np.ascontiguousarray(np.concatenate(bank_parts).astype(np.float32))
        faiss.normalize_L2(bank)
        index = faiss.IndexFlatL2(DINO_DIM)
        index.add(bank)

        image_scores, maps = [], []
        for start in range(0, len(tests), 16):
            selected_parts, active_parts = [], []
            for number in range(start, min(start + 16, len(tests))):
                query = np.asarray(features[test_offset + number], dtype=np.float32)
                active = query_masks[number]
                selected_parts.append(query[active])
                active_parts.append(active)
            lengths = [len(part) for part in selected_parts]
            selected = np.ascontiguousarray(np.concatenate(selected_parts, axis=0))
            faiss.normalize_L2(selected)
            distances, _ = index.search(selected, 1)
            distances = distances[:, 0] / 2.0
            offset = 0
            for length, active in zip(lengths, active_parts):
                patch_distances = np.zeros(DINO_PATCH_COUNT, dtype=np.float32)
                patch_distances[active] = distances[offset:offset + length]
                offset += length
                top_count = max(1, int(np.ceil(DINO_PATCH_COUNT * .01)))
                image_scores.append(float(np.mean(np.sort(patch_distances)[-top_count:])))
                maps.append(scores_to_map(patch_distances))
            if start % 100 == 0 or start + 16 >= len(tests):
                print(f"seed={seed}: scored {min(start + 16, len(tests))}/{len(tests)} RobustAD images", flush=True)

        maps_array = np.asarray(maps, dtype=np.float32)
        masks_array = np.asarray([preprocess_mask(row["mask_paths"]) for row in tests], dtype=bool)
        labels_array = np.asarray([row["label"] for row in tests], dtype=np.uint8)
        for split in SPLITS[1:]:
            indices = np.asarray([i for i, row in enumerate(tests) if row["split"] == split], dtype=np.int64)
            image_metric = ranking_metrics(labels_array[indices], np.asarray(image_scores)[indices])
            pixel_auroc, pixel_ap = binary_ranking_metrics(masks_array[indices].ravel(), maps_array[indices].ravel())
            per_seed.append({
                "method": "AnomalyDINO full-pipeline adaptation",
                "backbone": "DINOv2 ViT-S/14",
                "reference_seed": seed,
                "domain": DOMAIN_LABELS[split],
                "split": split,
                "image_count": int(len(indices)),
                "anomaly_images": int(labels_array[indices].sum()),
                "image_auroc": image_metric["auroc"],
                "image_average_precision": image_metric["average_precision"],
                "pixel_auroc": pixel_auroc,
                "pixel_average_precision": pixel_ap,
                "aupro_fpr_0_30": pro_auc(masks_array[indices], maps_array[indices]),
                "reference_images": REFERENCE_COUNT,
                "reference_rotation_views": REFERENCE_COUNT * len(ANGLES),
                "reference_patch_count": int(len(bank)),
                "reference_bank_bytes": int(bank.nbytes),
                "duplicate_policy": "deduplicate exact test images within split; union referenced masks",
            })
            print(f"seed={seed} {DOMAIN_LABELS[split]} image-AUROC={image_metric['auroc']:.4f} "
                  f"pixel-AUROC={pixel_auroc:.4f} pixel-AP={pixel_ap:.4f}", flush=True)

        # Compare each defect class with normals from the same capture domain.
        # Other defect classes and the ambiguous duplicate frame are excluded.
        for defect_type in DEFECTS:
            for split in SPLITS[1:]:
                indices = np.asarray([
                    i for i, row in enumerate(tests)
                    if row["split"] == split and (row["label"] == 0 or row["defect_type"] == defect_type)
                ], dtype=np.int64)
                if not len(indices) or not any(tests[i]["defect_type"] == defect_type for i in indices):
                    continue
                type_labels = np.asarray([int(tests[i]["defect_type"] == defect_type) for i in indices], dtype=np.uint8)
                type_scores = np.asarray(image_scores, dtype=np.float32)[indices]
                type_image = ranking_metrics(type_labels, type_scores)
                defect_results.append({
                    "method": "AnomalyDINO full-pipeline adaptation",
                    "reference_seed": seed,
                    "domain": DOMAIN_LABELS[split],
                    "split": split,
                    "defect_type": defect_type,
                    "image_count": int(len(indices)),
                    "normal_images": int((type_labels == 0).sum()),
                    "defect_images": int(type_labels.sum()),
                    "image_auroc": type_image["auroc"],
                    "image_average_precision": type_image["average_precision"],
                    "ambiguous_duplicate_excluded": True,
                    "analysis_scope": "image-level defect-type versus normal ranking",
                })

        # Paired sensitivity result for the one exact-duplicate test4 image.
        sens_idx, sens_labels, sens_masks = [], [], []
        for idx, row in enumerate(tests):
            if row["split"] != "pcb_data_dir_test4":
                continue
            pairs = duplicate_pairs.get(row["image"], [])
            if pairs:
                for pair in pairs:
                    sens_idx.append(idx)
                    sens_labels.append(1)
                    sens_masks.append(preprocess_mask([Path(pair["mask_path"])]))
            else:
                sens_idx.append(idx)
                sens_labels.append(row["label"])
                sens_masks.append(masks_array[idx])
        sens_idx = np.asarray(sens_idx, dtype=np.int64)
        sens_masks = np.asarray(sens_masks, dtype=bool)
        sens_maps = maps_array[sens_idx]
        sens_scores = np.asarray(image_scores)[sens_idx]
        sens_image = ranking_metrics(sens_labels, sens_scores)
        sens_pixel_auroc, sens_pixel_ap = binary_ranking_metrics(sens_masks.ravel(), sens_maps.ravel())
        per_seed.append({
            "method": "AnomalyDINO full-pipeline adaptation",
            "result_type": "test4_duplicate_policy_sensitivity",
            "reference_seed": seed,
            "image_count": int(len(sens_idx)),
            "anomaly_images": int(np.sum(sens_labels)),
            "image_auroc": sens_image["auroc"],
            "image_average_precision": sens_image["average_precision"],
            "pixel_auroc": sens_pixel_auroc,
            "pixel_average_precision": sens_pixel_ap,
            "aupro_fpr_0_30": pro_auc(sens_masks, sens_maps),
            "policy": "keep both identical-image metadata rows; use each row's own mask",
        })
        del index, bank, bank_parts, maps_array, masks_array

    domain_summary = []
    for split in SPLITS[1:]:
        rows = [row for row in per_seed if row.get("split") == split]
        domain_summary.append({
            "split": split,
            "domain": DOMAIN_LABELS[split],
            **{
                metric: {
                    "mean": float(np.mean([row[metric] for row in rows])),
                    "sd_across_five_reference_selections": float(np.std([row[metric] for row in rows], ddof=1)),
                }
                for metric in ("image_auroc", "image_average_precision", "pixel_auroc", "pixel_average_precision", "aupro_fpr_0_30")
            },
        })
    shifted = [row for row in domain_summary if row["split"] != "pcb_data_dir_test0"]
    metrics = ("image_auroc", "image_average_precision", "pixel_auroc", "pixel_average_precision", "aupro_fpr_0_30")
    shifted_macro = {metric: float(np.mean([row[metric]["mean"] for row in shifted])) for metric in metrics}
    sensitivity_rows = [row for row in per_seed if row.get("result_type") == "test4_duplicate_policy_sensitivity"]
    sensitivity_summary = {
        metric: {
            "mean": float(np.mean([row[metric] for row in sensitivity_rows])),
            "sd_across_five_reference_selections": float(np.std([row[metric] for row in sensitivity_rows], ddof=1)),
        }
        for metric in metrics
    }
    final = {
        "dataset": "AmazonScience/RobustAD PCB",
        "dataset_revision": REVISION,
        "backbone": "DINOv2 ViT-S/14",
        "duplicate_image_groups": duplicate_groups,
        "reference_selections": selections,
        "domain_results": domain_summary,
        "shifted_domain_macro_mean_test1_test5": shifted_macro,
        "test4_duplicate_policy_sensitivity": {
            "primary_union_deduplicated": next(row for row in domain_summary if row["split"] == "pcb_data_dir_test4"),
            "separate_metadata_rows": sensitivity_summary,
            "per_reference_selection": sensitivity_rows,
        },
        "seed_results": [row for row in per_seed if row.get("split")],
        "defect_type_results": defect_results,
        "protocol": {
            "method": "AnomalyDINO full pipeline adapted for full-frame PCB evaluation",
            "dinov2_repo": DINO_REPO,
            "dinov2_revision": DINO_REVISION,
            "checkpoint_sha256": checkpoint_hash,
            "references": "same five 16-image normal-only selections used by PatchCore",
            "reference_augmentations_degrees": list(ANGLES),
            "preprocessing": "full-frame RGB bicubic resize 448x448; ImageNet normalization; masks evaluated on common 224x224 full-frame field",
            "foreground_mask": "PCA first component, threshold 10, central-area polarity check, 3x3 dilation and closing",
            "score": "mean largest 1% patch cosine distances; reference bank augmented with eight orientations",
            "test_splits": "test0 source condition; test1 lighting; test2 white balance; test3 rotation; test4 position; test5 shadow/background",
            "duplicate_policy": "one test image per exact JPEG hash; referenced masks unioned for primary result",
            "threshold_selection": "none; threshold-free ranking metrics only",
            "comparison_scope": "full-pipeline comparison; backbone, input resolution, augmentation, foreground mask and score differ from PatchCore",
        },
        "provenance": {
            "runner_sha256": runner_hash,
            "dinov2_checkpoint_sha256": checkpoint_hash,
            "torch": importlib.metadata.version("torch"),
            "torchvision": importlib.metadata.version("torchvision"),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "scikit_learn": importlib.metadata.version("scikit-learn"),
            "opencv": importlib.metadata.version("opencv-python-headless"),
            "faiss_cpu": importlib.metadata.version("faiss-cpu"),
            "device": "CPU",
            "elapsed_seconds": time.perf_counter() - started,
        },
    }
    atomic_json(summary_file, final)
    atomic_json(output / "run.json", {"status": "complete", "elapsed_seconds": final["provenance"]["elapsed_seconds"]})
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/robustad-pcb-v1/anomalydino-v1"))
    parser.add_argument("--root", type=Path, default=Path("data/robustad-pcb-v1/PCB"))
    parser.add_argument("--cache", type=Path, default=Path("data/torch-cache"))
    args = parser.parse_args()
    result = evaluate(args.output, args.root, args.cache)
    print(json.dumps({"output": str(args.output / "summary.json"),
                      "shifted_domain_macro_mean_test1_test5": result["shifted_domain_macro_mean_test1_test5"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
