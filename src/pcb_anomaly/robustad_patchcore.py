"""Few-reference PatchCore evaluation on the audited RobustAD PCB subset."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from .audit_robustad_pcb import DEFECTS, DOMAIN_LABELS, REVISION, SPLITS, _read_rows
from .crops import sha256, square_input
from .robustad_registration import (
    make_registration_plan,
    registered_image,
    registered_mask,
    registration_lookup,
)
from .visa_benchmark import ranking_metrics
from .visa_localization import binary_ranking_metrics, pro_auc


SEEDS = (42, 43, 44, 45, 46)
REFERENCE_COUNT = 16
IMAGE_SIZE = 224
FEATURE_DIM = 1024
PATCH_COUNT = 784
PATCHCORE_COMMIT = "fcaa92f124fb1ad74a7acf56726decd4b27cbcad"
BACKBONES = {
    "wrn50": {
        "name": "WideResNet50-2",
        "weights": "95faca4d11227dddf8633dbb5ff6c8a9003c1aa5b8945c73834b8007b10950b8",
    },
    "rn18": {
        "name": "ResNet18",
        "weights": "f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec",
    },
}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def load_records(root: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Return normal reference candidates and test records with exact duplicates merged."""
    references = []
    tests = []
    for split in SPLITS:
        split_root = root / split
        rows = list(_read_rows(split_root / "metadata.jsonl"))
        for row in rows:
            record = {
                "split": split,
                "domain": DOMAIN_LABELS[split],
                "image": row["file_name"],
                "label": int(row["label"]),
                "mask": row.get("mask"),
                "defect_type": next((name for name in DEFECTS if name in row["file_name"]), None),
            }
            record["image_path"] = (split_root / row["file_name"]).resolve()
            if split == "pcb_data_dir_train":
                if record["label"] == 0:
                    references.append(record)
            else:
                record["mask_paths"] = [((root.parent / row["mask"]).resolve())] if row.get("mask") else []
                tests.append(record)

    # Deduplicate only within each official test condition. Merge masks so one physical
    # frame contributes one image-level and pixel-level observation to the main result.
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in tests:
        key = (record["split"], sha256(record["image_path"]))
        grouped[key].append(record)
    unique_tests = []
    duplicate_groups = []
    for group in grouped.values():
        primary = dict(sorted(group, key=lambda item: item["image"])[0])
        primary["mask_paths"] = sorted({p for item in group for p in item["mask_paths"]})
        primary["label"] = int(any(item["label"] == 1 for item in group))
        primary["duplicate_records_merged"] = len(group) - 1
        primary["defect_type"] = group[0]["defect_type"] if len(group) == 1 else None
        if len(group) > 1:
            duplicate_groups.append({
                "split": primary["split"],
                "image_sha256": sha256(primary["image_path"]),
                "records": [item["image"] for item in group],
                "mask_paths": [str(path) for path in primary["mask_paths"]],
                "record_mask_pairs": [
                    {"image": item["image"], "mask_path": str(item["mask_paths"][0]) if item["mask_paths"] else None}
                    for item in group
                ],
                "policy": "one image observation; binary union of all referenced masks",
            })
        unique_tests.append(primary)
    references.sort(key=lambda item: item["image"])
    unique_tests.sort(key=lambda item: (item["split"], item["image"]))
    if len(references) != 180 or len(unique_tests) != 1004:
        raise ValueError(f"Unexpected dataset counts: {len(references)} normal references, {len(unique_tests)} unique test images")
    if any(record["label"] == 1 and not record["mask_paths"] for record in unique_tests):
        raise ValueError("Anomaly test image is missing its mask")
    return references, unique_tests, duplicate_groups


def select_references(references: list[dict]) -> dict[str, list[str]]:
    selections = {}
    for seed in SEEDS:
        ranked = sorted(
            references,
            key=lambda row: hashlib.sha256(f"robustad-pcb-v1:{seed}:{row['image']}".encode()).hexdigest(),
        )
        selections[str(seed)] = [row["image"] for row in ranked[:REFERENCE_COUNT]]
    return selections


def preprocess_image(path: Path, to_tensor, normalize, transform=None):
    if transform is None:
        with Image.open(path) as image:
            image = image.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR)
    else:
        image = registered_image(path, transform)
        image = square_input(image, IMAGE_SIZE)
    return normalize(to_tensor(image))


def preprocess_mask(paths: list[Path], transform=None) -> np.ndarray:
    if transform is not None:
        return registered_mask(paths, transform, IMAGE_SIZE)
    combined = np.zeros((IMAGE_SIZE, IMAGE_SIZE), dtype=bool)
    for path in paths:
        with Image.open(path) as image:
            mask = image.convert("L").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.NEAREST)
            combined |= np.asarray(mask, dtype=np.uint8) > 0
    return combined


def embed_records(records, model, pc, torch, to_tensor, normalize, output_path, batch_size=4,
                  transform_lookup=None):
    embeddings = np.lib.format.open_memmap(
        output_path, mode="w+", dtype="float32", shape=(len(records), PATCH_COUNT, FEATURE_DIM)
    )
    for start in range(0, len(records), batch_size):
        batch = torch.stack([
            preprocess_image(
                row["image_path"], to_tensor, normalize,
                transform_lookup.get(f"{row['split']}/{row['image']}") if transform_lookup else None,
            )
            for row in records[start:start + batch_size]
        ])
        with torch.inference_mode():
            feature_batch = np.asarray(pc._embed(batch), dtype=np.float32)
        if feature_batch.shape != (len(batch) * PATCH_COUNT, FEATURE_DIM):
            raise ValueError(f"Unexpected patch embedding shape: {feature_batch.shape}")
        embeddings[start:start + len(batch)] = feature_batch.reshape(len(batch), PATCH_COUNT, FEATURE_DIM)
        done = min(start + batch_size, len(records))
        if start % 80 == 0 or done == len(records):
            print(f"Embedded {done}/{len(records)} images", flush=True)
    embeddings.flush()
    return embeddings


def evaluate(output: Path, root: Path, cache: Path, vendor: Path, backbone_name: str = "wrn50",
             view_contract: str = "full_frame", registration_plan_path: Path | None = None) -> dict:
    import torch
    from torchvision import models
    from torchvision.transforms.functional import normalize, to_tensor

    output, root, cache, vendor = map(Path, (output, root, cache, vendor))
    if backbone_name not in BACKBONES:
        raise ValueError(f"Unsupported backbone {backbone_name}; choose from {sorted(BACKBONES)}")
    if view_contract not in {"full_frame", "registered_board"}:
        raise ValueError(f"Unsupported view contract: {view_contract}")
    backbone = BACKBONES[backbone_name]
    audit_path = Path("reports/robustad-pcb-audit-v1.json")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("revision") != REVISION or audit.get("total_images_verified") != 1260:
        raise ValueError("Expected the locally audited, pinned RobustAD PCB revision")

    references, tests, duplicate_groups = load_records(root)
    selections = select_references(references)
    records = references + tests
    registration_plan = None
    transform_lookup = None
    if view_contract == "registered_board":
        if registration_plan_path is None:
            registration_plan_path = output.parent / "registration-v1" / "plan.json"
        registration_plan = make_registration_plan(records, references[0], registration_plan_path)
        transform_lookup = registration_lookup(registration_plan)
    vendor_provenance = json.loads((vendor / "provenance.json").read_text(encoding="utf-8"))
    if vendor_provenance.get("commit") != PATCHCORE_COMMIT:
        raise ValueError(f"Expected upstream PatchCore commit {PATCHCORE_COMMIT}")
    signature = {
        "dataset_revision": REVISION,
        "embedding_contract": f"{backbone_name}-layer2-layer3-3x3-v1",
        "records": [{"split": row["split"], "image": row["image"], "sha256": sha256(row["image_path"])} for row in records],
        "transform": (
            "RGB bilinear full-frame resize to 224x224; ImageNet normalization"
            if view_contract == "full_frame" else
            "640px SIFT homography to one training-normal template; fixed training-only PCB ROI with 3% margin; aspect-preserving mean-pad then bilinear resize to 224x224; ImageNet normalization"
        ),
        "view_contract": view_contract,
        "registration_signature": registration_plan["signature"] if registration_plan else None,
        "backbone": f"{backbone['name']} ImageNet1K V1",
        "weights_sha256": backbone["weights"],
        "embedding_shape": [PATCH_COUNT, FEATURE_DIM],
    }
    signature_path = output / "features.signature.json"
    feature_path = output / "features.npy"
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "run.json", {"status": "running", "started_unix": time.time()})
    atomic_json(output / "reference-selections.json", {
        "dataset_revision": REVISION,
        "policy": "SHA-256 ranking of normal training image path keyed by seed; 16 unique images per seed",
        "selections": selections,
    })

    if signature_path.exists() and feature_path.exists() and json.loads(signature_path.read_text(encoding="utf-8")) == signature:
        features = np.load(feature_path, mmap_mode="r")
        finite = features.shape == (len(records), PATCH_COUNT, FEATURE_DIM)
        if finite:
            for offset in range(0, len(records), 16):
                if not np.isfinite(features[offset:offset + 16]).all():
                    finite = False
                    break
        if not finite:
            del features
            feature_path.unlink(missing_ok=True)
            signature_path.unlink(missing_ok=True)
            features = None
        else:
            print(f"Reusing embeddings for {len(records)} images", flush=True)
    else:
        features = None

    sys.path.insert(0, str((vendor / "src").resolve()))
    import patchcore.patchcore
    import patchcore.sampler
    import patchcore.common

    torch.set_num_threads(4)
    torch.manual_seed(42)
    np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(cache.resolve()))
    if backbone_name == "wrn50":
        model = models.wide_resnet50_2(weights=models.Wide_ResNet50_2_Weights.IMAGENET1K_V1)
    else:
        model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model = model.eval().requires_grad_(False)
    pc = patchcore.patchcore.PatchCore(torch.device("cpu"))
    pc.load(model, ["layer2", "layer3"], torch.device("cpu"), (3, IMAGE_SIZE, IMAGE_SIZE),
            FEATURE_DIM, FEATURE_DIM, patchsize=3, anomaly_score_num_nn=1,
            featuresampler=patchcore.sampler.IdentitySampler(),
            nn_method=patchcore.common.FaissNN(False, 4))
    imagenet_norm = lambda tensor: normalize(tensor, [0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    started = time.perf_counter()
    if features is None:
        features = embed_records(records, model, pc, torch, to_tensor, imagenet_norm, feature_path,
                                 transform_lookup=transform_lookup)
        atomic_json(signature_path, signature)

    reference_index = {row["image"]: idx for idx, row in enumerate(references)}
    test_offset = len(references)
    results = []
    defect_results = []
    duplicate_sensitivity = []
    duplicate_pairs_by_image = {
        sorted(group["records"])[0]: group["record_mask_pairs"]
        for group in duplicate_groups if group["split"] == "pcb_data_dir_test4"
    }
    for seed in SEEDS:
        selected = selections[str(seed)]
        candidate_features = np.asarray(
            features[[reference_index[name] for name in selected]], dtype=np.float32
        ).reshape(-1, FEATURE_DIM)
        sampler = patchcore.sampler.ApproximateGreedyCoresetSampler(0.1, torch.device("cpu"))
        torch.manual_seed(42)
        np.random.seed(42)
        bank = np.ascontiguousarray(sampler.run(candidate_features))
        pc.anomaly_scorer.fit([bank])
        patch_maps, image_scores = [], []
        for index, row in enumerate(tests):
            patch_scores = pc.anomaly_scorer.predict([
                np.asarray(features[test_offset + index], dtype=np.float32)
            ])[0].reshape(1, 28, 28)
            image_scores.append(float(np.max(patch_scores)))
            patch_maps.append(pc.anomaly_segmentor.convert_to_segmentation(patch_scores)[0].astype(np.float32))
        patch_maps = np.asarray(patch_maps, dtype=np.float32)
        image_labels = np.asarray([row["label"] for row in tests], dtype=np.uint8)
        masks = [preprocess_mask(
            row["mask_paths"],
            transform_lookup.get(f"{row['split']}/{row['image']}") if transform_lookup else None,
        ) for row in tests]
        masks = np.asarray(masks, dtype=bool)
        for split in SPLITS[1:]:
            indices = np.asarray([i for i, row in enumerate(tests) if row["split"] == split], dtype=np.int64)
            labels = image_labels[indices]
            scores = np.asarray(image_scores, dtype=np.float32)[indices]
            image_metrics = ranking_metrics(labels, scores)
            pixel_auroc, pixel_ap = binary_ranking_metrics(masks[indices].ravel(), patch_maps[indices].ravel())
            result = {
                "method": f"upstream PatchCore {backbone['name']}",
                "reference_seed": seed,
                "domain": DOMAIN_LABELS[split],
                "split": split,
                "image_count": int(len(indices)),
                "anomaly_images": int(labels.sum()),
                "image_auroc": image_metrics["auroc"],
                "image_average_precision": image_metrics["average_precision"],
                "pixel_auroc": pixel_auroc,
                "pixel_average_precision": pixel_ap,
                "aupro_fpr_0_30": pro_auc(masks[indices], patch_maps[indices]),
                "reference_images": REFERENCE_COUNT,
                "reference_patch_count": int(len(bank)),
                "reference_bank_bytes": int(bank.nbytes),
                "duplicate_policy": "deduplicate exact test images within split; union referenced masks",
            }
            results.append(result)
            print(f"seed={seed} {DOMAIN_LABELS[split]} image-AUROC={image_metrics['auroc']:.4f} "
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
                labels = np.asarray([int(tests[i]["defect_type"] == defect_type) for i in indices], dtype=np.uint8)
                scores = np.asarray(image_scores, dtype=np.float32)[indices]
                type_image = ranking_metrics(labels, scores)
                defect_results.append({
                    "method": f"upstream PatchCore {backbone['name']}",
                    "reference_seed": seed,
                    "domain": DOMAIN_LABELS[split],
                    "split": split,
                    "defect_type": defect_type,
                    "image_count": int(len(indices)),
                    "normal_images": int((labels == 0).sum()),
                    "defect_images": int(labels.sum()),
                    "image_auroc": type_image["auroc"],
                    "image_average_precision": type_image["average_precision"],
                    "ambiguous_duplicate_excluded": True,
                    "analysis_scope": "image-level defect-type versus normal ranking",
                })

        # Sensitivity analysis for the duplicate test4 frame: preserve its two
        # metadata rows and score each row against its own defect mask.
        sensitivity_indices, sensitivity_labels, sensitivity_masks = [], [], []
        for index, row in enumerate(tests):
            if row["split"] != "pcb_data_dir_test4":
                continue
            pairs = duplicate_pairs_by_image.get(row["image"], [])
            if pairs:
                for pair in pairs:
                    sensitivity_indices.append(index)
                    sensitivity_labels.append(1)
                    sensitivity_masks.append(preprocess_mask([Path(pair["mask_path"])]))
            else:
                sensitivity_indices.append(index)
                sensitivity_labels.append(row["label"])
                sensitivity_masks.append(preprocess_mask(row["mask_paths"]))
        sensitivity_indices = np.asarray(sensitivity_indices, dtype=np.int64)
        sensitivity_masks = np.asarray(sensitivity_masks, dtype=bool)
        sensitivity_maps = patch_maps[sensitivity_indices]
        sensitivity_scores = np.asarray(image_scores, dtype=np.float32)[sensitivity_indices]
        sensitivity_image = ranking_metrics(sensitivity_labels, sensitivity_scores)
        sensitivity_pixel_auroc, sensitivity_pixel_ap = binary_ranking_metrics(
            sensitivity_masks.ravel(), sensitivity_maps.ravel()
        )
        duplicate_sensitivity.append({
            "reference_seed": seed,
            "image_count": int(len(sensitivity_indices)),
            "anomaly_images": int(np.sum(sensitivity_labels)),
            "image_auroc": sensitivity_image["auroc"],
            "image_average_precision": sensitivity_image["average_precision"],
            "pixel_auroc": sensitivity_pixel_auroc,
            "pixel_average_precision": sensitivity_pixel_ap,
            "aupro_fpr_0_30": pro_auc(sensitivity_masks, sensitivity_maps),
            "policy": "keep both identical-image metadata rows; use each row's own mask",
        })
        del patch_maps, masks, bank, candidate_features

    summary = []
    for split in SPLITS[1:]:
        domain_rows = [row for row in results if row["split"] == split]
        summary.append({
            "split": split,
            "domain": DOMAIN_LABELS[split],
            **{
                metric: {
                    "mean": float(np.mean([row[metric] for row in domain_rows])),
                    "sd_across_five_reference_selections": float(np.std([row[metric] for row in domain_rows], ddof=1)),
                }
                for metric in ("image_auroc", "image_average_precision", "pixel_auroc", "pixel_average_precision", "aupro_fpr_0_30")
            },
        })
    shifted = [row for row in summary if row["split"] != "pcb_data_dir_test0"]
    metrics = ("image_auroc", "image_average_precision", "pixel_auroc", "pixel_average_precision", "aupro_fpr_0_30")
    shifted_macro = {
        metric: float(np.mean([row[metric]["mean"] for row in shifted]))
        for metric in metrics
    }
    duplicate_sensitivity_summary = {
        metric: {
            "mean": float(np.mean([row[metric] for row in duplicate_sensitivity])),
            "sd_across_five_reference_selections": float(np.std([row[metric] for row in duplicate_sensitivity], ddof=1)),
        }
        for metric in metrics
    }
    final = {
        "dataset": "AmazonScience/RobustAD PCB",
        "dataset_revision": REVISION,
        "backbone": backbone["name"],
        "duplicate_image_groups": duplicate_groups,
        "reference_selections": selections,
        "view_contract": view_contract,
        "registration_quality": registration_plan["quality_gate"] if registration_plan else None,
        "registration_template": registration_plan["template"] if registration_plan else None,
        "registration_roi_xyxy_640": registration_plan["roi_xyxy_640"] if registration_plan else None,
        "category_scope": "image normal-versus-anomaly by domain; target-domain image normal-versus-one-defect-subtype results are supplementary",
        "domain_results": summary,
        "shifted_domain_macro_mean_test1_test5": shifted_macro,
        "test4_duplicate_policy_sensitivity": {
            "primary_union_deduplicated": next(row for row in summary if row["split"] == "pcb_data_dir_test4"),
            "separate_metadata_rows": duplicate_sensitivity_summary,
            "per_reference_selection": duplicate_sensitivity,
        },
        "seed_results": results,
        "defect_type_results": defect_results,
        "protocol": {
            "backbone": f"torchvision {backbone['name']} ImageNet1K V1",
            "implementation": "upstream PatchCore",
            "patchcore_commit": PATCHCORE_COMMIT,
            "weights_sha256": backbone["weights"],
            "references": f"{REFERENCE_COUNT} normal images sampled only from the 180 pcb_data_dir_train normal images; five fixed SHA-256-ranked selections",
            "training_anomalies_used": 0,
            "preprocessing": signature["transform"],
            "patchcore": "layer2+layer3, 3x3 patches, Euclidean 1-NN, approximate greedy 10% coreset, 128D projection",
            "test_splits": "test0 source condition; test1 lighting; test2 white balance; test3 rotation; test4 position; test5 shadow/background",
            "duplicate_policy": "within each test split, exact duplicate JPEGs are one image observation; referenced masks are unioned",
            "threshold_selection": "none; all reported metrics are threshold-free ranking metrics",
            "pixel_map": "upstream PatchCore bilinear map upsampling and Gaussian sigma=4",
            "seed_summary": "mean and sample standard deviation across five reference selections; describes selection variability, not a confidence interval",
        },
        "provenance": {
            "runner_sha256": sha256(Path(__file__)),
            "torch": importlib.metadata.version("torch"),
            "torchvision": importlib.metadata.version("torchvision"),
            "numpy": importlib.metadata.version("numpy"),
            "pillow": importlib.metadata.version("Pillow"),
            "device": "CPU",
            "elapsed_seconds": time.perf_counter() - started,
        },
    }
    atomic_json(output / "summary.json", final)
    atomic_json(output / "run.json", {"status": "complete", "elapsed_seconds": final["provenance"]["elapsed_seconds"]})
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--root", type=Path, default=Path("data/robustad-pcb-v1/PCB"))
    parser.add_argument("--cache", type=Path, default=Path("data/torch-cache"))
    parser.add_argument("--vendor", type=Path, default=Path("data/vendor/patchcore-inspection"))
    parser.add_argument("--backbone", choices=sorted(BACKBONES), default="wrn50")
    parser.add_argument("--view-contract", choices=("full_frame", "registered_board"), default="full_frame")
    parser.add_argument("--registration-plan", type=Path)
    args = parser.parse_args()
    suffix = "registered-v1" if args.view_contract == "registered_board" else "v1"
    output = args.output or Path(f"data/robustad-pcb-v1/patchcore-{args.backbone}-{suffix}")
    result = evaluate(output, args.root, args.cache, args.vendor, args.backbone,
                      args.view_contract, args.registration_plan)
    print(json.dumps({"output": str(output / "summary.json"),
                      "domain_results": result["domain_results"],
                      "shifted_domain_macro_mean_test1_test5": result["shifted_domain_macro_mean_test1_test5"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
