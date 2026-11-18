"""Fixed-reference SIFT registration and board ROI for RobustAD-PCB controls."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .crops import sha256


REGISTRATION_SIZE = 640
SIFT_FEATURES = 4000
LOWE_RATIO = 0.75
RANSAC_REPROJECTION_PX = 4.0
MIN_INLIERS = 50
MIN_INLIER_RATIO = 0.25
MIN_ROI_COVERAGE = 0.95
BOARD_HSV_LOWER = (90, 50, 40)
BOARD_HSV_UPPER = (130, 255, 255)
BOARD_MARGIN_FRACTION = 0.03


def atomic_json(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _read_rgb(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise OSError(f"Could not read image: {path}")
    height, width = image.shape[:2]
    if height != width:
        raise ValueError(f"Expected square RobustAD image: {path} has {width}x{height}")
    return cv2.resize(image, (REGISTRATION_SIZE, REGISTRATION_SIZE), interpolation=cv2.INTER_AREA)


def _board_roi(template_bgr: np.ndarray) -> tuple[int, int, int, int]:
    hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(BOARD_HSV_LOWER), np.array(BOARD_HSV_UPPER))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        raise ValueError("Blue PCB region was not found in the training-only registration template")
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, width, height, area = map(int, stats[component])
    if area < mask.size * 0.05 or area > mask.size * 0.8:
        raise ValueError(f"Implausible template PCB component area fraction: {area / mask.size:.3f}")
    margin_x = max(1, round(width * BOARD_MARGIN_FRACTION))
    margin_y = max(1, round(height * BOARD_MARGIN_FRACTION))
    return (
        max(0, x - margin_x),
        max(0, y - margin_y),
        min(REGISTRATION_SIZE, x + width + margin_x),
        min(REGISTRATION_SIZE, y + height + margin_y),
    )


def _estimate_homography(template_features, query_gray: np.ndarray, sift, matcher):
    template_points, template_desc = template_features
    query_points, query_desc = sift.detectAndCompute(query_gray, None)
    if template_desc is None or query_desc is None:
        return None, 0, 0, 0.0
    pairs = matcher.knnMatch(template_desc, query_desc, k=2)
    good = [first for first, second in pairs if first.distance < LOWE_RATIO * second.distance]
    if len(good) < 4:
        return None, len(good), 0, 0.0
    query_xy = np.float32([query_points[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    template_xy = np.float32([template_points[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(
        query_xy, template_xy, cv2.RANSAC, RANSAC_REPROJECTION_PX
    )
    inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    return homography, len(good), inliers, inliers / max(1, len(good))


def make_registration_plan(records: list[dict], template_record: dict, plan_path: Path) -> dict:
    """Register every frame to one normal training image; no labels are inspected."""
    plan_path = Path(plan_path)
    template_path = Path(template_record["image_path"])
    template_hash = sha256(template_path)
    record_signature = [
        {"key": f"{row['split']}/{row['image']}", "sha256": sha256(row["image_path"])}
        for row in records
    ]
    signature = {
        "template": f"{template_record['split']}/{template_record['image']}",
        "template_sha256": template_hash,
        "records": record_signature,
        "registration_size": REGISTRATION_SIZE,
        "sift_features": SIFT_FEATURES,
        "sift_feature_cache_contract": "reuse-template-descriptors-v2",
        "lowe_ratio": LOWE_RATIO,
        "ransac_reprojection_px": RANSAC_REPROJECTION_PX,
        "roi_hsv_lower": list(BOARD_HSV_LOWER),
        "roi_hsv_upper": list(BOARD_HSV_UPPER),
        "roi_margin_fraction": BOARD_MARGIN_FRACTION,
    }
    if plan_path.is_file():
        try:
            cached = json.loads(plan_path.read_text(encoding="utf-8"))
            if cached.get("signature") == signature:
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    template = _read_rgb(template_path)
    roi = _board_roi(template)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    sift = cv2.SIFT_create(nfeatures=SIFT_FEATURES)
    template_features = sift.detectAndCompute(template_gray, None)
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    rows = []
    for index, record in enumerate(records):
        key = f"{record['split']}/{record['image']}"
        if Path(record["image_path"]).resolve() == template_path.resolve():
            homography = np.eye(3, dtype=np.float64)
            good_count = inliers = len(template_features[0])
            ratio = 1.0
        else:
            query = _read_rgb(Path(record["image_path"]))
            homography, good_count, inliers, ratio = _estimate_homography(
                template_features, cv2.cvtColor(query, cv2.COLOR_BGR2GRAY), sift, matcher
            )
            if homography is None:
                raise ValueError(f"SIFT registration failed for {key}")
        valid = cv2.warpPerspective(
            np.ones((REGISTRATION_SIZE, REGISTRATION_SIZE), dtype=np.uint8),
            homography, (REGISTRATION_SIZE, REGISTRATION_SIZE), flags=cv2.INTER_NEAREST,
        )
        x0, y0, x1, y1 = roi
        coverage = float(valid[y0:y1, x0:x1].mean())
        if inliers < MIN_INLIERS or ratio < MIN_INLIER_RATIO or coverage < MIN_ROI_COVERAGE:
            raise ValueError(
                f"Registration quality failed for {key}: matches={good_count}, inliers={inliers}, "
                f"ratio={ratio:.3f}, roi_coverage={coverage:.3f}"
            )
        rows.append({
            "key": key,
            "homography_query_to_template": homography.tolist(),
            "good_matches": int(good_count),
            "inliers": int(inliers),
            "inlier_ratio": float(ratio),
            "roi_coverage": coverage,
        })
        if index % 100 == 0 or index + 1 == len(records):
            print(f"Registered {index + 1}/{len(records)} images", flush=True)

    result = {
        "signature": signature,
        "template": signature["template"],
        "roi_xyxy_640": list(roi),
        "records": rows,
        "quality_gate": {
            "minimum_inliers": MIN_INLIERS,
            "minimum_inlier_ratio": MIN_INLIER_RATIO,
            "minimum_roi_coverage": MIN_ROI_COVERAGE,
            "registered_images": len(rows),
            "failed_images": 0,
            "mean_inliers": float(np.mean([row["inliers"] for row in rows])),
            "min_inliers": int(min(row["inliers"] for row in rows)),
            "mean_roi_coverage": float(np.mean([row["roi_coverage"] for row in rows])),
            "min_roi_coverage": float(min(row["roi_coverage"] for row in rows)),
        },
    }
    atomic_json(plan_path, result)
    return result


def registration_lookup(plan: dict) -> dict[str, tuple[np.ndarray, tuple[int, int, int, int]]]:
    roi = tuple(int(value) for value in plan["roi_xyxy_640"])
    return {
        row["key"]: (np.asarray(row["homography_query_to_template"], dtype=np.float64), roi)
        for row in plan["records"]
    }


def registered_image(path: Path, transform: tuple[np.ndarray, tuple[int, int, int, int]]) -> Image.Image:
    homography, roi = transform
    image = _read_rgb(Path(path))
    aligned = cv2.warpPerspective(image, homography, (REGISTRATION_SIZE, REGISTRATION_SIZE))
    x0, y0, x1, y1 = roi
    crop = cv2.cvtColor(aligned[y0:y1, x0:x1], cv2.COLOR_BGR2RGB)
    return Image.fromarray(crop)


def registered_mask(paths: list[Path], transform: tuple[np.ndarray, tuple[int, int, int, int]],
                    output_size: int) -> np.ndarray:
    homography, roi = transform
    x0, y0, x1, y1 = roi
    combined = np.zeros((REGISTRATION_SIZE, REGISTRATION_SIZE), dtype=bool)
    for path in paths:
        with Image.open(path) as image:
            raw = np.asarray(image.convert("L").resize(
                (REGISTRATION_SIZE, REGISTRATION_SIZE), Image.Resampling.NEAREST
            ), dtype=np.uint8)
        warped = cv2.warpPerspective(
            raw, homography, (REGISTRATION_SIZE, REGISTRATION_SIZE),
            flags=cv2.INTER_NEAREST,
        )
        combined |= warped > 0
    crop = combined[y0:y1, x0:x1].astype(np.uint8) * 255
    height, width = crop.shape
    side = max(height, width)
    top = (side - height) // 2
    bottom = side - height - top
    left = (side - width) // 2
    right = side - width - left
    crop = cv2.copyMakeBorder(crop, top, bottom, left, right, cv2.BORDER_CONSTANT, value=0)
    resized = Image.fromarray(crop).resize((output_size, output_size), Image.Resampling.NEAREST)
    return np.asarray(resized, dtype=np.uint8) > 0
