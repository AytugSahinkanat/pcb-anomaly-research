"""Explicit reference/calibration/test separation for precomputed embeddings.

Inputs must use independently curated normal reference/calibration samples.
These utilities cannot verify the scientific provenance of supplied labels.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Split:
    sample_ids: tuple[str, ...]
    board_ids: tuple[str, ...]


def validate_splits(reference: Split, calibration: Split, test: Split) -> None:
    """Require disjoint physical boards and samples for unseen-board evaluation.

    All views/crops/augmentations of a board must share its curated board_id.
    For unseen-layout claims, use the layout family as board_id instead.
    """
    splits = (reference, calibration, test)
    for split in splits:
        if not split.sample_ids or len(split.sample_ids) != len(split.board_ids):
            raise ValueError("Each split needs equally sized, nonempty ID columns")
        if any(not isinstance(x, str) or not x.strip()
               for x in (*split.sample_ids, *split.board_ids)):
            raise ValueError("IDs must be nonempty strings")
        if len(set(split.sample_ids)) != len(split.sample_ids):
            raise ValueError("Duplicate sample IDs within split")
    for i, left in enumerate(splits):
        for right in splits[i + 1:]:
            if set(left.sample_ids) & set(right.sample_ids):
                raise ValueError("Sample leakage between splits")
            if set(left.board_ids) & set(right.board_ids):
                raise ValueError("Board leakage between splits")


def _matrix(values):
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or 0 in x.shape or not np.isfinite(x).all():
        raise ValueError("Expected a finite, nonempty feature matrix")
    return x


def l2_normalize(features):
    x = _matrix(features)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    if (norms <= 0).any() or not np.isfinite(norms).all():
        raise ValueError("Zero or nonfinite feature norm")
    return x / norms


def knn_scores(reference, query, *, k=3, reference_ids, query_ids,
               batch_size=128):
    """Mean Euclidean distance, excluding same-ID matches explicitly.

    IDs must identify the original sample, not a newly assigned row number.
    Cross-split isolation must additionally be checked with validate_splits.
    Run per component class; unknown classes require abstention.
    """
    ref, qry = _matrix(reference), _matrix(query)
    if ref.shape[1] != qry.shape[1]:
        raise ValueError("Feature dimensions differ")
    if (not isinstance(k, int) or k < 1 or not isinstance(batch_size, int)
            or batch_size < 1):
        raise ValueError("k and batch_size must be positive integers")
    rid, qid = np.asarray(reference_ids), np.asarray(query_ids)
    if rid.shape != (len(ref),) or qid.shape != (len(qry),):
        raise ValueError("Feature/ID alignment mismatch")
    if len(set(rid.tolist())) != len(rid):
        raise ValueError("Reference IDs must be unique")
    available = len(ref) - np.isin(qid, rid).astype(int)
    if (available < k).any():
        raise ValueError("Insufficient distinct reference samples")
    result = []
    for start in range(0, len(qry), batch_size):
        block = qry[start:start + batch_size]
        d2 = ((block * block).sum(1)[:, None]
              + (ref * ref).sum(1)[None, :] - 2 * block @ ref.T)
        distance = np.sqrt(np.maximum(d2, 0))
        distance[qid[start:start + batch_size, None] == rid[None, :]] = np.inf
        result.append(np.partition(distance, k - 1, axis=1)[:, :k].mean(1))
    return np.concatenate(result)


def calibrate_threshold(normal_calibration_scores, *, quantile=0.95):
    """Empirical quantile; not a guaranteed future false-positive rate."""
    scores = np.asarray(normal_calibration_scores, dtype=float)
    if (scores.ndim != 1 or not len(scores) or not np.isfinite(scores).all()
            or not 0 < quantile < 1):
        raise ValueError("Invalid calibration scores or quantile")
    return float(np.quantile(scores, quantile, method="higher"))


def binary_metrics(labels, scores, *, threshold, label_source):
    """Threshold metrics; synthetic results must be reported separately."""
    if label_source not in {"independent_annotation", "synthetic_perturbation"}:
        raise ValueError("Labels must not be derived from model scores")
    y, s = np.asarray(labels), np.asarray(scores, dtype=float)
    if (y.ndim != 1 or not len(y) or y.shape != s.shape
            or not np.isin(y, [0, 1]).all() or not np.isfinite(s).all()
            or not np.isfinite(threshold)):
        raise ValueError("Invalid labels, scores or threshold")
    if len(np.unique(y)) < 2:
        raise ValueError("Both normal and anomalous labels required")
    pred = s > threshold
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1)))
    tn = int(np.sum(~pred & (y == 0)))
    return {"label_source": label_source, "n": len(y), "tp": tp, "fp": fp,
            "fn": fn, "tn": tn, "accuracy": (tp + tn) / len(y),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn), "fpr": fp / (fp + tn),
            "f1": 2 * tp / (2 * tp + fp + fn)}

