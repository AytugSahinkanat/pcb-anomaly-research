# PCB Anomaly Research

Reproducible data auditing and evaluation utilities for PCB component anomaly research.

**Status:** research infrastructure. No trained detector or validated real-defect benchmark is provided yet.

## Implemented

- Read-only ZIP audit, image/XML matching and bounding-box validation.
- Quoted multi-word category parsing and unique annotation IDs.
- Reproducible candidate board-group splits with class coverage reports.
- Reference/calibration/test leakage checks, self-excluding kNN and threshold calibration.
- Thirteen unit tests and a GitHub Actions workflow.

The audited archive contains 47 matched images and 8,016 component annotations across 31 categories. See the [data audit (Turkish)](docs/data-audit.tr.md) for provenance and limitations.

## Install and test

Python 3.10 or later. In PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

On Linux/macOS, activate with `source .venv/bin/activate` instead. Tests require NumPy and Pillow, but no GPU, model weights or dataset downloads.

## Audit the data

Obtain the ZIP from the [original dataset page](https://sites.google.com/view/chiawen-kuo/home/pcb-component-detection), then run:

```console
python -m pcb_anomaly.data /path/to/pcb_wacv_2019.zip --output data/audit-v1
```

The output directory must not already exist. The command produces `audit.json` (counts, issues, hashes and coverage), `images.json` (image metadata), `manifest.jsonl` (annotations) and `splits.json` (candidate assignments). It does not modify the archive.

Component annotations are not defect labels. Defect labels remain unknown. Filename-based board groups require visual review before experiments; rare categories may lack reference or calibration samples.

## Evaluation contract

Call `validate_splits` before evaluating precomputed features. Keep all views, crops and augmentations of a board together. For unseen-layout experiments, group by layout family. Build reference banks per category, calibrate thresholds on separate normal samples, and evaluate against independent annotations. Unknown classes require abstention.

`knn_scores` excludes the query's own sample ID. Accurate IDs and label provenance are the caller's responsibility. Synthetic perturbation results must be separated from real-defect results.

## Roadmap

1. Visually review board identities, near duplicates and bounding boxes.
2. Add manifest-based crop and feature extraction.
3. Add VisA PCB evaluation with fixed configurations.
4. Compare corrected ResNet18+kNN, PatchCore, EfficientAD and AnomalyDINO.
5. Measure the effect of board context at controlled false-alarm budgets.

## Data and attribution

Kuo, Ashmore, Huggins and Kira, *Data-Efficient Graph Embedding Learning for PCB Component Detection*, WACV 2019. [Paper](https://arxiv.org/abs/1811.06994).

Candidate anomaly benchmark: [VisA / SPot-the-Difference](https://github.com/amazon-science/spot-diff).

Raw data, weights, local analyses and project reports are excluded from Git. Dataset terms are separate from code licensing. A code license and citation metadata have not yet been selected; public visibility alone does not grant an open-source license.
