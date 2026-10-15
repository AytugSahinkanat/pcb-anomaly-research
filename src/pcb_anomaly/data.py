"""Read-only audit of the original Kuo ZIP; never infer defect labels."""
import argparse
import collections
import hashlib
import io
import json
import random
import re
import shlex
import zipfile
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

from PIL import Image


def parse_label(raw):
    tokens = shlex.split(raw)
    if not tokens:
        raise ValueError("Empty label")
    return tokens[0].lower(), " ".join(tokens[1:])


def board_group(stem):
    """Conservative name-based candidate group, not verified physical identity."""
    match = re.fullmatch(r"(.+)_(Top|Bottom)(\d*)", stem, re.IGNORECASE)
    return (match[1], match[2].lower()) if match else (stem, "unknown")


def match_image(xml_name, filename, members):
    folder = PurePosixPath(xml_name).parent
    local = [n for n in members if PurePosixPath(n).parent == folder
             and PurePosixPath(n).suffix.lower() in {".jpg", ".jpeg", ".png"}]
    # XML may contain a Windows path or a stale filename: use only the basename.
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    exact = [n for n in local if PurePosixPath(n).name.lower() == basename.lower()]
    if len(exact) == 1:
        return exact[0], "filename"
    if len(exact) > 1:
        raise ValueError("Ambiguous filename match")
    same_stem = [n for n in local if PurePosixPath(n).stem.lower()
                 == PurePosixPath(xml_name).stem.lower()]
    if len(same_stem) == 1:
        return same_stem[0], "stem_fallback"
    raise ValueError("Missing or ambiguous image match")


def convert_bbox(values, width, height):
    """VOC 1-based inclusive -> 0-based half-open; reject rather than clip."""
    xmin, ymin, xmax, ymax = values
    if not (1 <= xmin <= xmax <= width and 1 <= ymin <= ymax <= height):
        raise ValueError("Box outside VOC image bounds")
    return xmin - 1, ymin - 1, xmax, ymax


def audit(archive):
    rows, images, issues = [], [], []
    classes = collections.Counter()
    with zipfile.ZipFile(archive) as z:
        members = z.namelist()
        if len(members) != len(set(members)):
            raise ValueError("Duplicate ZIP member names")
        for xml in sorted(n for n in members if n.lower().endswith(".xml")):
            root = ET.fromstring(z.read(xml))
            stem = PurePosixPath(xml).stem
            group, side = board_group(stem)
            try:
                image, matching = match_image(xml, root.findtext("filename", ""), members)
                payload = z.read(image)
                with Image.open(io.BytesIO(payload)) as im:
                    width, height = im.size
                    im.verify()
            except (ValueError, OSError) as exc:
                issues.append({"xml": xml, "issue": str(exc)})
                continue
            size = (int(root.findtext("size/width")), int(root.findtext("size/height")))
            dimension_ok = size == (width, height)
            if not dimension_ok:
                issues.append({"xml": xml, "issue": "XML/image dimension mismatch"})
            images.append({"image_id": stem, "board_group": group, "side": side,
                           "group_status": "name_inferred", "image_path": image,
                           "xml_path": xml, "width": width, "height": height,
                           "sha256": hashlib.sha256(payload).hexdigest(),
                           "matching": matching, "dimensions_match": dimension_ok})
            seen = collections.Counter()
            for index, obj in enumerate(root.findall("object")):
                raw = obj.findtext("name", "")
                flags = []
                try:
                    category, refdes = parse_label(raw)
                except ValueError:
                    category, refdes = "", ""
                    flags.append("invalid_label")
                classes[category] += 1
                seen[raw] += 1
                if seen[raw] > 1:
                    flags.append("repeated_raw_label")
                bbox, original = [], []
                try:
                    original = [int(obj.findtext(f"bndbox/{k}"))
                                for k in ("xmin", "ymin", "xmax", "ymax")]
                    bbox = list(convert_bbox(original, width, height))
                except (TypeError, ValueError):
                    flags.append("invalid_bbox")
                if not dimension_ok:
                    flags.append("dimension_mismatch")
                is_text = category in {"text", "component text"}
                rows.append({"sample_id": f"{stem}:{index:05d}", "image_id": stem,
                             "board_group": group, "group_status": "name_inferred",
                             "side": side, "category": category, "raw_label": raw,
                             "refdes": refdes, "bbox_voc": original, "bbox": bbox,
                             "image_path": image, "xml_path": xml,
                             "is_text": is_text, "label": None, "label_source": "unlabeled",
                             "crop_eligible": bool(category and bbox and dimension_ok and not is_text),
                             "issues": flags})
        used = {x['image_path'] for x in images}
        unused = sorted(n for n in members if PurePosixPath(n).suffix.lower()
                        in {'.jpg', '.jpeg', '.png'} and n not in used)
    hashes = collections.defaultdict(list)
    for im in images:
        hashes[im['sha256']].append(im['image_id'])
    summary = {"xml_count": sum(n.lower().endswith('.xml') for n in members),
               "matched_images": len(images), "objects": len(rows),
               "text_objects": sum(r['is_text'] for r in rows),
               "component_objects": sum(not r['is_text'] for r in rows),
               "eligible_components": sum(r['crop_eligible'] for r in rows),
               "candidate_board_groups": len({i['board_group'] for i in images}),
               "classes": dict(sorted(classes.items())), "image_issues": issues,
               "object_issues": dict(collections.Counter(f for r in rows for f in r['issues'])),
               "unused_images": unused,
               "duplicate_images": [v for v in hashes.values() if len(v) > 1],
               "group_status": "name_inferred_requires_review",
               "bbox_convention": "VOC 1-based inclusive; stored bbox is zero-based half-open",
               "label_status": "No defect labels inferred"}
    return rows, images, summary


def propose_splits(rows, seed=42):
    """Reproducible candidate board split; no class stratification claim."""
    groups = sorted({r['board_group'] for r in rows if r['crop_eligible']})
    if len(groups) < 3:
        raise ValueError("At least three eligible board groups required")
    random.Random(seed).shuffle(groups)
    n = max(1, len(groups) // 5)
    assignment = {g: ('test' if i < n else 'calibration' if i < 2*n else 'reference')
                  for i, g in enumerate(groups)}
    return {"seed": seed, "status": "provisional_name_based_groups",
            "assignments": dict(sorted(assignment.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, images, summary = audit(args.archive)
    with args.archive.open('rb') as f:
        digest = hashlib.sha256()
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    summary['archive_sha256'] = digest.hexdigest()
    split = propose_splits(rows)
    coverage = collections.defaultdict(collections.Counter)
    for row in rows:
        row['split'] = split['assignments'].get(row['board_group'], 'excluded')
        if row['crop_eligible']:
            coverage[row['category']][row['split']] += 1
    summary['class_split_counts'] = {k: dict(v) for k, v in sorted(coverage.items())}
    summary['test_classes_without_reference'] = [k for k,v in coverage.items()
                                                if v['test'] and not v['reference']]
    args.output.mkdir(parents=True, exist_ok=False)
    for name, obj in [('audit.json', summary), ('images.json', images), ('splits.json', split)]:
        (args.output / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')
    with (args.output / 'manifest.jsonl').open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(json.dumps({k: summary[k] for k in ['xml_count','matched_images','objects',
          'text_objects','component_objects','eligible_components','candidate_board_groups',
          'object_issues','image_issues','test_classes_without_reference']}, indent=2))


if __name__ == '__main__':
    main()
