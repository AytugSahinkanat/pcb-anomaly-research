"""Frozen ImageNet ResNet18 nearest-centroid baseline on board-held-out SolDef crops."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import platform
import time
import zipfile

import numpy as np
from PIL import Image

from .crops import sha256


TASK_LABELS = {
    "position": ("good", "no_good"),
    "solder": ("exc_solder", "good", "poor_solder", "spike"),
}
TASK_VIEWS = {"position": {"V1"}, "solder": {"V2", "V2.1"}}
IMAGE_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def polygon_crop(image, points, padding=0.20, size=224):
    """Crop a polygon's box with fixed relative context and mean-color letterboxing."""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("Invalid polygon")
    width, height = image.size
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    dx, dy = max(x1 - x0, 1.0) * padding, max(y1 - y0, 1.0) * padding
    box = (max(0, int(np.floor(x0 - dx))), max(0, int(np.floor(y0 - dy))),
           min(width, int(np.ceil(x1 + dx))), min(height, int(np.ceil(y1 + dy))))
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError("Polygon crop is empty")
    crop = image.crop(box).convert("RGB")
    scale = min(size / crop.width, size / crop.height)
    resized_size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    resized = crop.resize(resized_size, Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), (124, 116, 104))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def extract_crops(archive, split_rows):
    unique = {}
    for row in split_rows:
        task = row["task"]
        if row["view_id"] not in TASK_VIEWS[task]:
            raise ValueError(f"Unexpected view {row['view_id']} for task {task}")
        unique.setdefault((task, row["image"]), row)

    samples = []
    for (task, image_id), row in sorted(unique.items()):
        image = Image.open(archive.open(row["source_path"])).convert("RGB")
        annotation = json.loads(archive.read(row["annotation"]))
        if (annotation.get("imageWidth"), annotation.get("imageHeight")) != image.size:
            raise ValueError(f"Source/annotation geometry mismatch: {image_id}")
        for shape_index, shape in enumerate(annotation["shapes"]):
            label = shape["label"]
            if label not in TASK_LABELS[task]:
                raise ValueError(f"Unexpected label {label} in {image_id}")
            crop = polygon_crop(image, shape["points"])
            samples.append({"sample_id": f"{task}|{row['source_board_group']}|{image_id}|{shape_index}",
                            "task": task, "board": row["source_board_group"],
                            "image": image_id, "annotation": row["annotation"],
                            "shape_index": shape_index, "label": label, "crop": crop})
        image.close()
    if len({sample["sample_id"] for sample in samples}) != len(samples):
        raise ValueError("Duplicate polygon sample identifiers")
    return samples


def image_tensor(image):
    import torch
    values = np.asarray(image, dtype=np.float32) / 255.0
    values = (values - IMAGE_MEAN) / IMAGE_STD
    return torch.from_numpy(values.transpose(2, 0, 1).copy())


def embed(samples, cache, batch_size=32, threads=4):
    import torch
    import torchvision
    from torchvision.models import ResNet18_Weights, resnet18

    if batch_size < 1 or threads < 1:
        raise ValueError("batch size and threads must be positive")
    torch.set_num_threads(threads)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(Path(cache).resolve()))
    weights = ResNet18_Weights.IMAGENET1K_V1
    model = resnet18(weights=weights).eval()
    model.fc = torch.nn.Identity()
    model.requires_grad_(False)
    output = np.empty((len(samples), 512), dtype=np.float32)
    with torch.inference_mode():
        for start in range(0, len(samples), batch_size):
            batch = torch.stack([image_tensor(row["crop"]) for row in samples[start:start + batch_size]])
            values = model(batch)
            if not torch.isfinite(values).all() or (values.norm(dim=1) <= 0).any():
                raise ValueError("Nonfinite or zero ResNet18 embedding")
            output[start:start + len(batch)] = torch.nn.functional.normalize(values, dim=1).numpy()
    checkpoint = Path(cache) / "checkpoints" / weights.url.rsplit("/", 1)[-1]
    return output, {"architecture": "torchvision ResNet18, fc=Identity, frozen global-average-pooled features",
                    "weights": str(weights), "weights_url": weights.url,
                    "weights_sha256": sha256(checkpoint), "torch": torch.__version__,
                    "torchvision": torchvision.__version__, "python": platform.python_version(),
                    "device": "cpu", "threads": threads, "batch_size": batch_size,
                    "preprocessing": "polygon bounding box with 20% relative context; aspect-ratio-preserving 224x224 letterbox RGB(124,116,104); ImageNet normalization; L2-normalized 512D embedding"}


def metrics(y_true, y_pred, labels):
    matrix = np.zeros((len(labels), len(labels)), dtype=np.int64)
    index = {label: i for i, label in enumerate(labels)}
    for truth, pred in zip(y_true, y_pred):
        matrix[index[truth], index[pred]] += 1
    recalls, f1s = {}, {}
    for i, label in enumerate(labels):
        tp = int(matrix[i, i])
        support = int(matrix[i].sum())
        predicted = int(matrix[:, i].sum())
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        recalls[label] = recall
        f1s[label] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total = int(matrix.sum())
    return {"n": total, "accuracy": float(np.trace(matrix) / total) if total else 0.0,
            "balanced_accuracy": float(np.mean(list(recalls.values()))),
            "macro_f1": float(np.mean(list(f1s.values()))), "recall_by_class": recalls,
            "f1_by_class": f1s, "confusion_matrix_labels": list(labels),
            "confusion_matrix": matrix.tolist()}


def run(split_manifest, archive_path, output, cache, batch_size=32, threads=4):
    split_manifest, archive_path, output = Path(split_manifest), Path(archive_path), Path(output)
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    split_rows = read_jsonl(split_manifest)
    partitions = {}
    folds = defaultdict(dict)
    for row in split_rows:
        task, fold, partition = row["task"], row["fold"], row["partition"]
        sample_key = (task, row["image"])
        stable = {key: value for key, value in row.items() if key not in {"fold", "partition"}}
        if sample_key in partitions and partitions[sample_key] != stable:
            raise ValueError(f"Inconsistent split row for {sample_key}")
        partitions[sample_key] = stable
        folds[(task, fold)].setdefault(partition, set()).add(row["source_board_group"])
    for (task, fold), groups in folds.items():
        train_groups, test_groups = groups.get("train", set()), groups.get("test", set())
        if train_groups & test_groups or len(test_groups) != 1:
            raise ValueError(f"Board leakage or invalid held-out group in {task}/{fold}")

    started = time.perf_counter()
    with zipfile.ZipFile(archive_path) as archive:
        samples = extract_crops(archive, list(partitions.values()))
    features, model_info = embed(samples, cache, batch_size, threads)
    by_task_image = defaultdict(list)
    for i, row in enumerate(samples):
        by_task_image[(row["task"], row["image"])].append(i)

    results, predictions = {}, []
    for task, labels in TASK_LABELS.items():
        task_rows = [row for row in split_rows if row["task"] == task]
        task_folds = sorted({row["fold"] for row in task_rows})
        fold_metrics = []
        majority_predictions = []
        for fold in task_folds:
            train_keys = {(r["task"], r["image"]) for r in task_rows if r["fold"] == fold and r["partition"] == "train"}
            test_keys = {(r["task"], r["image"]) for r in task_rows if r["fold"] == fold and r["partition"] == "test"}
            train_idx = [i for key in sorted(train_keys) for i in by_task_image[key]]
            test_idx = [i for key in sorted(test_keys) for i in by_task_image[key]]
            prototypes = []
            for label in labels:
                selected = [i for i in train_idx if samples[i]["label"] == label]
                if not selected:
                    raise ValueError(f"Missing training class {label} in {task}/{fold}")
                center = features[selected].mean(axis=0)
                prototypes.append(center / max(float(np.linalg.norm(center)), 1e-12))
            similarities = features[test_idx] @ np.stack(prototypes, axis=1)
            y_true = [samples[i]["label"] for i in test_idx]
            y_pred = [labels[int(j)] for j in similarities.argmax(axis=1)]
            fold_result = metrics(y_true, y_pred, labels)
            train_counts = {label: sum(samples[i]["label"] == label for i in train_idx)
                            for label in labels}
            majority_label = max(labels, key=lambda label: train_counts[label])
            majority_pred = [majority_label] * len(y_true)
            majority_result = metrics(y_true, majority_pred, labels)
            held_out = sorted({samples[i]["board"] for i in test_idx})
            fold_metrics.append({"fold": fold, "held_out_boards": held_out,
                                 "training_majority_label": majority_label,
                                 "training_class_counts": train_counts,
                                 "majority_control": majority_result, **fold_result})
            majority_predictions.extend(majority_pred)
            for i, truth, pred, scores in zip(test_idx, y_true, y_pred, similarities):
                predictions.append({"task": task, "fold": fold, "sample_id": samples[i]["sample_id"],
                                    "board": samples[i]["board"], "image": samples[i]["image"],
                                    "shape_index": samples[i]["shape_index"], "true": truth,
                                    "predicted": pred, "cosine_scores": dict(zip(labels, map(float, scores)))})
        task_sample_count = sum(len(indices) for (name, _), indices in by_task_image.items() if name == task)
        if sum(row["task"] == task for row in predictions) != task_sample_count:
            raise ValueError(f"Incomplete held-out predictions for {task}")
        task_predictions = [row for row in predictions if row["task"] == task]
        task_gt = [row["true"] for row in task_predictions]
        task_pred = [row["predicted"] for row in task_predictions]
        if len(majority_predictions) != len(task_gt):
            raise ValueError(f"Incomplete majority-control predictions for {task}")
        fold_bacc = [row["balanced_accuracy"] for row in fold_metrics]
        fold_f1 = [row["macro_f1"] for row in fold_metrics]
        results[task] = {"out_of_fold": metrics(task_gt, task_pred, labels),
                         "majority_control_out_of_fold": metrics(task_gt, majority_predictions, labels),
                         "folds": fold_metrics,
                         "fold_mean_balanced_accuracy": float(np.mean(fold_bacc)),
                         "fold_sd_balanced_accuracy": float(np.std(fold_bacc, ddof=1)) if len(fold_bacc) > 1 else 0.0,
                         "fold_mean_macro_f1": float(np.mean(fold_f1)),
                         "fold_sd_macro_f1": float(np.std(fold_f1, ddof=1)) if len(fold_f1) > 1 else 0.0}

    output.mkdir(parents=True)
    (output / "predictions.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in predictions), encoding="utf-8")
    summary = {"status": "complete_descriptive_board_held_out_baseline",
               "split_manifest": str(split_manifest), "split_manifest_sha256": sha256(split_manifest),
               "source_archive_sha256": sha256(archive_path), "unique_polygons": len(samples),
               "runner_sha256": sha256(Path(__file__)),
               "model": model_info, "classifier": "cosine nearest class centroid fit on each fold's training-board embeddings; no hyperparameter tuning",
               "tasks": results, "elapsed_seconds": round(time.perf_counter() - started, 2),
               "limits": ["Three solder-board groups provide only a pilot estimate.",
                          "All held-out folds are used for the cross-validated summary; selecting methods on these scores requires a new independent test.",
                          "ROI boxes and labels are annotation-supervised; this is not unsupervised PatchCore or full-image anomaly detection."]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "output": str(output),
                      "unique_polygons": len(samples), "elapsed_seconds": summary["elapsed_seconds"],
                      "tasks": {k: v["out_of_fold"] for k, v in results.items()}},
                     indent=2, ensure_ascii=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-manifest", type=Path, default=Path("data/soldef-board-splits-v1/manifest.jsonl"))
    parser.add_argument("--archive", type=Path, default=Path("data/soldef-ai/archive.zip"))
    parser.add_argument("--output", type=Path, default=Path("data/soldef-resnet18-v1"))
    parser.add_argument("--cache", type=Path, default=Path("data/torch-cache"))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    run(args.split_manifest, args.archive, args.output, args.cache, args.batch_size, args.threads)


if __name__ == "__main__":
    main()
