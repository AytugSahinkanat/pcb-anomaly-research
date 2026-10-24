"""Build task-specific leave-one-source-PCB-out SolDef_AI split manifests."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


TASK_VIEWS = {
    "position": {"V1"},
    "solder": {"V2", "V2.1"},
}
TASK_LABELS = {
    "position": {"good", "no_good"},
    "solder": {"good", "exc_solder", "poor_solder", "spike"},
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_metadata(record):
    candidates = record.get("source_candidates", [])
    if len(candidates) != 1:
        raise ValueError(f"Expected one verified source path: {record.get('image')}")
    parts = candidates[0].split("/")
    if (len(parts) < 6 or parts[0:2] != ["SolDef_AI", "Dataset"]
            or not parts[2].startswith("CS") or not parts[3]
            or not parts[4].startswith("V")):
        raise ValueError(f"Unexpected SolDef source path: {candidates[0]}")
    return {"source_board_group": parts[2], "component_type": parts[3],
            "view_id": parts[4], "source_path": candidates[0]}


def read_records(path):
    records = []
    seen = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        record = json.loads(line)
        metadata = source_metadata(record)
        key = (record["image"], metadata["source_board_group"])
        if key in seen:
            raise ValueError(f"Duplicate annotated image at line {line_number}: {record['image']}")
        seen.add(key)
        record.update(metadata)
        records.append(record)
    if not records:
        raise ValueError("No annotated records")
    return records


def counts(rows):
    image_counts = Counter()
    polygon_counts = Counter()
    for row in rows:
        image_counts.update(row["labels"].keys())
        polygon_counts.update(row["labels"])
    return {"images": len(rows), "images_with_label": dict(sorted(image_counts.items())),
            "polygons": dict(sorted(polygon_counts.items()))}


def make_plan(records):
    folds = []
    manifest = []
    task_summaries = {}
    for task, views in TASK_VIEWS.items():
        eligible = []
        for row in records:
            if row["view_id"] not in views:
                continue
            unexpected = set(row["labels"]) - TASK_LABELS[task]
            if unexpected:
                raise ValueError(f"Unexpected {task} labels in {row['image']}: {sorted(unexpected)}")
            if row["labels"]:
                eligible.append(row)
        groups = sorted({row["source_board_group"] for row in eligible})
        if len(groups) < 3:
            raise ValueError(f"At least three source boards required for {task}: {groups}")
        task_summaries[task] = {
            "views": sorted(views), "labels": sorted(TASK_LABELS[task]),
            "source_boards": groups, "all_annotations": counts(eligible),
            "by_board": {group: counts([r for r in eligible if r["source_board_group"] == group])
                         for group in groups},
        }
        for held_out in groups:
            train = [row for row in eligible if row["source_board_group"] != held_out]
            test = [row for row in eligible if row["source_board_group"] == held_out]
            train_groups = {row["source_board_group"] for row in train}
            test_groups = {row["source_board_group"] for row in test}
            if train_groups & test_groups or test_groups != {held_out}:
                raise AssertionError("Source-board leakage in generated fold")
            fold_id = f"{task}-holdout-{held_out.lower()}"
            folds.append({"task": task, "fold": fold_id, "held_out_board": held_out,
                          "train_boards": sorted(train_groups), "test_boards": sorted(test_groups),
                          "train": counts(train), "test": counts(test)})
            for partition, rows in (("train", train), ("test", test)):
                for row in rows:
                    manifest.append({"task": task, "fold": fold_id, "partition": partition,
                                     **row})
    return {"status": "split_plan_complete_not_model_evaluated",
            "grouping": "source PCB directory CS1-CS6; all views and component types from one CS stay together",
            "normality_policy": "Only explicitly annotated polygons are included; unannotated images are not labeled normal",
            "tasks": task_summaries, "folds": folds}, manifest


def build(manifest_path, output):
    manifest_path, output = Path(manifest_path), Path(output)
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    records = read_records(manifest_path)
    plan, rows = make_plan(records)
    plan.update({"source_manifest": str(manifest_path),
                 "source_manifest_sha256": sha256(manifest_path),
                 "source_annotation_images": len(records),
                 "citation": "Fontana et al., J. Manuf. Mater. Process. 8(3), 117 (2024), DOI: 10.3390/jmmp8030117"})
    output.mkdir(parents=True)
    (output / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    with (output / "manifest.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"status": plan["status"], "output": str(output),
                      "source_annotation_images": len(records),
                      "folds": len(plan["folds"]), "plan": str(output / "plan.json")},
                     ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/soldef-audit-v1/annotations.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/soldef-board-splits-v1"))
    args = parser.parse_args()
    build(args.manifest, args.output)


if __name__ == "__main__":
    main()
