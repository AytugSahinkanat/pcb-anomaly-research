"""Audit the locally downloaded AmazonScience/RobustAD PCB subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


DATASET = "AmazonScience/RobustAD"
REVISION = "82c642b2d18be60f2dab104f8dd4dea1f4ccfacb"
SPLITS = [
    "pcb_data_dir_train",
    "pcb_data_dir_test0",
    "pcb_data_dir_test1",
    "pcb_data_dir_test2",
    "pcb_data_dir_test3",
    "pcb_data_dir_test4",
    "pcb_data_dir_test5",
]
DOMAIN_LABELS = {
    "pcb_data_dir_train": "source_train",
    "pcb_data_dir_test0": "source_test",
    "pcb_data_dir_test1": "lighting",
    "pcb_data_dir_test2": "white_balance",
    "pcb_data_dir_test3": "rotation",
    "pcb_data_dir_test4": "position",
    "pcb_data_dir_test5": "shadow_background",
}
DEFECTS = ["Missing Component", "Soldering Melt", "Scratch"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def count_images(directory: Path, suffixes: tuple[str, ...]) -> int:
    return sum(1 for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)


def audit(root: Path) -> dict:
    root = root.resolve()
    issues: list[dict] = []
    all_images: list[tuple[str, Path]] = []
    image_annotations: dict[str, dict] = {}
    split_reports: list[dict] = []
    exact_hashes: dict[str, list[str]] = defaultdict(list)
    image_total = mask_total = 0

    for split in SPLITS:
        directory = root / split
        metadata_path = directory / "metadata.jsonl"
        if not metadata_path.is_file():
            issues.append({"split": split, "type": "missing_metadata", "path": str(metadata_path)})
            continue
        rows = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        label_counts = Counter()
        defect_counts = Counter()
        file_names = Counter(row.get("file_name") for row in rows)
        mask_paths: list[str] = []
        image_paths: set[str] = set()
        sizes = Counter()
        sizes_by_label = defaultdict(Counter)
        modes = Counter()
        mask_sizes = Counter()
        mask_modes = Counter()
        mask_values = Counter()
        mask_positive_pixels = []
        split_errors = []

        for row in rows:
            rel = row.get("file_name")
            label = row.get("label")
            label_counts[str(label)] += 1
            if not rel:
                split_errors.append({"type": "empty_file_name", "row": row})
                continue
            if rel in image_paths:
                split_errors.append({"type": "duplicate_manifest_path", "path": rel})
            image_paths.add(rel)
            image_path = directory / rel
            if not image_path.is_file():
                split_errors.append({"type": "missing_image", "path": rel})
                continue
            try:
                with Image.open(image_path) as im:
                    im.verify()
                with Image.open(image_path) as im:
                    sizes[str(im.size)] += 1
                    sizes_by_label[str(label)][str(im.size)] += 1
                    modes[im.mode] += 1
            except Exception as exc:
                split_errors.append({"type": "invalid_image", "path": rel, "error": str(exc)})
                continue
            all_images.append((split, image_path))
            manifest_key = f"{split}/{rel}"
            exact_hashes[sha256(image_path)].append(manifest_key)
            image_annotations[manifest_key] = row
            image_total += 1

            if label == 1:
                base = image_path.stem
                found = next((d for d in DEFECTS if d in base), None)
                defect_counts[found or "unrecognized"] += 1
                mask_rel = row.get("mask")
                if not mask_rel:
                    split_errors.append({"type": "anomaly_without_mask_reference", "path": rel})
                    continue
                mask_paths.append(mask_rel)
                mask_path = root.parent / mask_rel
                if not mask_path.is_file():
                    split_errors.append({"type": "missing_mask", "path": mask_rel})
                    continue
                try:
                    with Image.open(mask_path) as mask:
                        mask.verify()
                    with Image.open(mask_path) as mask:
                        mask_array = np.asarray(mask)
                        mask_sizes[str(mask.size)] += 1
                        mask_modes[mask.mode] += 1
                        values = np.unique(mask_array)
                        mask_values[",".join(map(str, values[:16]))] += 1
                        mask_positive_pixels.append(int(np.count_nonzero(mask_array)))
                        if tuple(mask.size) != tuple(Image.open(image_path).size):
                            split_errors.append({
                                "type": "image_mask_size_mismatch",
                                "image": rel,
                                "mask": mask_rel,
                                "image_size": list(Image.open(image_path).size),
                                "mask_size": list(mask.size),
                            })
                except Exception as exc:
                    split_errors.append({"type": "invalid_mask", "path": mask_rel, "error": str(exc)})
                    continue
                mask_total += 1
            elif row.get("mask") not in (None, ""):
                split_errors.append({"type": "normal_has_mask_reference", "path": rel, "mask": row.get("mask")})

        actual_images = {
            p.relative_to(directory).as_posix()
            for p in directory.rglob("*.jpg")
            if p.is_file() and p.parent.name in {"normal", "anomaly"}
        }
        unlisted_images = sorted(actual_images - image_paths)
        unreferenced_masks = sorted(
            p.relative_to(root.parent).as_posix()
            for p in (directory / "masks").glob("*.png")
            if p.is_file() and p.relative_to(root.parent).as_posix() not in mask_paths
        )
        if unlisted_images:
            split_errors.append({"type": "unlisted_images", "count": len(unlisted_images), "examples": unlisted_images[:10]})
        if unreferenced_masks:
            split_errors.append({"type": "unreferenced_masks", "count": len(unreferenced_masks), "examples": unreferenced_masks[:10]})
        for path, count in file_names.items():
            if count > 1:
                split_errors.append({"type": "duplicate_manifest_path", "path": path, "count": count})
        issues.extend({"split": split, **e} for e in split_errors)
        split_reports.append({
            "split": split,
            "domain": DOMAIN_LABELS[split],
            "metadata_rows": len(rows),
            "image_count": sum(label_counts.values()),
            "labels": dict(label_counts),
            "defect_types": dict(defect_counts),
            "mask_count": sum(1 for row in rows if row.get("label") == 1 and row.get("mask")),
            "image_dimensions": dict(sizes),
            "image_dimensions_by_label": {k: dict(v) for k, v in sizes_by_label.items()},
            "image_modes": dict(modes),
            "mask_dimensions": dict(mask_sizes),
            "mask_modes": dict(mask_modes),
            "mask_value_sets": dict(mask_values),
            "mask_positive_pixels_min": min(mask_positive_pixels) if mask_positive_pixels else None,
            "mask_positive_pixels_max": max(mask_positive_pixels) if mask_positive_pixels else None,
            "unlisted_image_count": len(unlisted_images),
        })

    duplicate_groups = [paths for paths in exact_hashes.values() if len(paths) > 1]
    duplicate_annotation_reviews = []
    for paths in duplicate_groups:
        annotations = [image_annotations[p] for p in paths]
        masks = []
        for p, row in zip(paths, annotations):
            mask_rel = row.get("mask")
            masks.append(mask_rel)
        mask_iou = mask_overlap = None
        if len(paths) == 2 and all(masks):
            arrays = [np.asarray(Image.open(root.parent / m)) > 0 for m in masks]
            if arrays[0].shape == arrays[1].shape:
                intersection = int(np.logical_and(arrays[0], arrays[1]).sum())
                union = int(np.logical_or(arrays[0], arrays[1]).sum())
                mask_iou = float(intersection / union) if union else 1.0
                mask_overlap = {
                    "intersection_pixels": intersection,
                    "union_pixels": union,
                    "mask_a_pixels": int(arrays[0].sum()),
                    "mask_b_pixels": int(arrays[1].sum()),
                    "a_fraction_inside_b": float(intersection / arrays[0].sum()) if arrays[0].sum() else None,
                    "b_fraction_inside_a": float(intersection / arrays[1].sum()) if arrays[1].sum() else None,
                }
        review = {
            "identical_image_paths": paths,
            "labels": [row.get("label") for row in annotations],
            "mask_paths": masks,
            "mask_iou": mask_iou,
            "mask_overlap": mask_overlap,
            "review_required": True,
        }
        duplicate_annotation_reviews.append(review)
        issues.append({"type": "exact_duplicate_images", **review})

    file_count = sum(1 for p in root.rglob("*") if p.is_file())
    total_bytes = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    metadata_fields = sorted({key for split in SPLITS for row in _read_rows(root / split / "metadata.jsonl") for key in row})
    return {
        "dataset": DATASET,
        "revision": REVISION,
        "license": "CC BY 4.0 (dataset card)",
        "root": str(root),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "total_images_verified": image_total,
        "total_anomaly_masks_verified": mask_total,
        "metadata_fields": metadata_fields,
        "split_reports": split_reports,
        "exact_duplicate_image_groups": duplicate_groups,
        "exact_duplicate_annotation_reviews": duplicate_annotation_reviews,
        "issues": issues,
        "dataset_identity_note": "metadata fields include file_name, label, mask only; no explicit physical board or board-design ID",
    }


def _read_rows(path: Path):
    if not path.is_file():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("data/robustad-pcb-v1/PCB"))
    parser.add_argument("--output", type=Path, default=Path("reports/robustad-pcb-audit-v1.json"))
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "total_images_verified": result["total_images_verified"],
        "total_anomaly_masks_verified": result["total_anomaly_masks_verified"],
        "issue_count": len(result["issues"]),
        "exact_duplicate_image_groups": len(result["exact_duplicate_image_groups"]),
        "metadata_fields": result["metadata_fields"],
        "splits": [{"split": r["split"], "images": r["image_count"], "labels": r["labels"], "defects": r["defect_types"]} for r in result["split_reports"]],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
