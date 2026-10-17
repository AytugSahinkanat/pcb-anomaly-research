# PCB Anomaly Research

Reproducible data auditing and evaluation utilities for PCB component anomaly research.

**Status:** research infrastructure. No trained detector or validated real-defect benchmark is provided yet.

See the [project status and research roadmap (Turkish)](docs/project-status.tr.md) for completed evidence, missing validation and publication goals.

## Implemented

- Read-only ZIP audit, image/XML matching and bounding-box validation.
- Quoted multi-word category parsing and unique annotation IDs.
- Reproducible candidate board-group splits with class coverage reports.
- Reference/calibration/test leakage checks, self-excluding kNN and threshold calibration.
- Visual review sheets, lossless component crops and frozen ResNet18 features.
- Calibration-to-reference neighbor galleries with cross-board filtering.
- Paired rotation/resolution sensitivity with a fixed reference bank.
- Four-orientation mean pooling and comparison with the single-view baseline.
- Resolution-augmented reference banks with unique-component neighbor ranking.
- Thirty unit tests and a GitHub Actions workflow.

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

## Visual review, crops and features

The initial review covers all 47 board images and 141 sampled boxes, not every annotation. See [review findings (Turkish)](docs/visual-review.tr.md). Board identities and layout families remain provisional.

```console
python -m pcb_anomaly.review /path/to/pcb_wacv_2019.zip --audit data/audit-v1 --output data/review-v1
python -m pcb_anomaly.crops /path/to/pcb_wacv_2019.zip --manifest data/audit-v1/manifest.jsonl --output data/crops-v1
python -m pip install -e ".[features]"
python -m pcb_anomaly.features --manifest data/crops-v1/manifest.jsonl --output data/features-resnet18-v1
```

For CPU-only PyTorch, first install `torch==2.10.0 torchvision==0.25.0` with `--index-url https://download.pytorch.org/whl/cpu`. The feature command runs on CPU and downloads official ImageNet weights on first use to `data/torch-cache`. The extraction was run with Python 3.12; use a Python/platform combination with compatible PyTorch wheels.

Crops retain original pixels and all 8,016 eligible samples; small and elongated crops carry quality flags. Features use square padding to preserve the whole component, bilinear resize to 224, ImageNet normalization, frozen ResNet18 pooling and L2 normalization. This deliberately differs from torchvision's default center-crop transform. Outputs contain ordered sample metadata, hashes and run provenance. Output directories must be new; only a `run.json` with `status=complete` confirms completion. No defect labels are inferred.

## Evaluation contract

Inspect feature neighborhoods without using the held-out test set:

```console
python -m pcb_anomaly.neighbors --features data/features-resnet18-v1 --crops data/crops-v1 --output data/neighbors-v1
```

Open the local `index.html` to compare same-category nearest/farthest crops and unrestricted nearest neighbors. The [initial review (Turkish)](docs/neighbor-review.tr.md) covers 61 selected queries across 22 categories. Category agreement is exploratory and must not be interpreted as defect detection accuracy.

Call `validate_splits` before evaluating precomputed features. Keep all views, crops and augmentations of a board together. For unseen-layout experiments, group by layout family. Build reference banks per category, calibrate thresholds on separate normal samples, and evaluate against independent annotations. Unknown classes require abstention.

`knn_scores` excludes the query's own sample ID. Accurate IDs and label provenance are the caller's responsibility. Synthetic perturbation results must be separated from real-defect results.

## Rotation and resolution sensitivity

Run the calibration-only sensitivity experiment (cached baseline weights required):

```console
python -m pcb_anomaly.sensitivity --features data/features-resnet18-v1 --crops data/crops-v1 --output data/sensitivity-v2
```

It compares identity, 90/180/270-degree rotations and native-crop downsampling to 50%/25% per dimension. Original reference embeddings stay fixed. Outputs include paired per-sample metrics, category/board/size summaries and transformed embeddings. Only `run.json` with `status=complete` confirms completion. Top-1 retention measures the same exact reference sample; top-5 overlap is intersection size divided by the available k (at most 5). These are representation stability measures, not defect accuracy.

See the [measured sensitivity results (Turkish)](docs/sensitivity.tr.md). The full run covers 1,156 calibration queries; no test queries are used. On CPUs with excessive BLAS threading, set `OPENBLAS_NUM_THREADS=1` before starting Python.

## Four-orientation pooling

Compare four-view pooled features with the single-view sensitivity results:

```console
python -m pcb_anomaly.multiview --features data/features-resnet18-v1 --sensitivity data/sensitivity-v2 --crops data/crops-v1 --output data/multiview-v1
```

Both queries and reference crops use the mean of four normalized 0/90/180/270-degree embeddings, followed by L2 normalization. The representation remains 512-dimensional. Right-angle invariance is structural; resolution robustness is measured separately. See the [four-view experiment (Turkish)](docs/multiview.tr.md).

## Resolution-augmented reference bank

Evaluate the original/50%/25% reference bank using fixed single-view queries:

```console
python -m pcb_anomaly.scale_bank --features data/features-resnet18-v1 --sensitivity data/sensitivity-v2 --crops data/crops-v1 --output data/scale-bank-v1
```

Each reference component contributes its maximum cosine across three resolutions; top-k counts distinct component IDs, not augmented views. Original reference vectors are reused, and only reference downsampling features are newly extracted. Test data is excluded. `run.json` with `status=complete` confirms completion.

See the [measured reference-bank results (Turkish)](docs/scale-bank.tr.md). Category agreement improves for degraded queries, but exact-neighbor stability has mixed results; real-defect performance remains untested.

## Roadmap

1. Extend sampled visual review to physical identities, layout families and near duplicates.
2. Inspect category-specific feature neighborhoods and collect independent defect labels.
3. Extend the completed five-reference-selection study with matched preprocessing and memory budgets.
4. Compare corrected ResNet18+kNN, PatchCore, EfficientAD and AnomalyDINO.
5. Measure the effect of board context at controlled false-alarm budgets.

## Data and attribution

Kuo, Ashmore, Huggins and Kira, *Data-Efficient Graph Embedding Learning for PCB Component Detection*, WACV 2019. [Paper](https://arxiv.org/abs/1811.06994).

Defect-data preparation is implemented for [VisA / SPot-the-Difference](https://github.com/amazon-science/spot-diff) PCB1–PCB4 and an annotation inventory for [SolDef_AI](https://www.kaggle.com/datasets/mauriziocalabrese/soldef-ai-pcb-dataset-for-defect-detection). See the [data audit and evaluation protocol (Turkish)](docs/defect-data.tr.md).

```console
python -m pcb_anomaly.visa acquire --root data/visa-pcb-v2 --archive data/downloads/VisA_20220922.tar
python -m pcb_anomaly.visa audit --root data/visa-pcb-v2 --output data/visa-audit-v1
python -m pcb_anomaly.soldef acquire --root data/soldef-ai
python -m pcb_anomaly.soldef audit --root data/soldef-ai --output data/soldef-audit-v1
```

VisA preserves the official test split and holds out 100 normal training images per PCB category for calibration. Image/mask geometry and cross-split exact RGB duplicates are checked. Physical-board independence is not established. SolDef inventories raw polygon labels and repeated files without assuming unlabeled images are normal; its split remains unassigned pending source/view grouping.

## First real-defect benchmark

The matched-backbone, 64-reference-per-category comparison is complete: global ResNet18+3NN versus a PatchCore–ResNet18 implementation variant, at 224 pixels. Macro image AUROC is 85.52% versus 86.16%. At independently calibrated category thresholds, sensitivity is 51.25% versus 59.50%, with observed false-positive rates of 6.97% versus 5.47%. The paired bootstrap interval for the AUROC difference includes zero, and PCB1 regresses. This is not a reproduction of the original WideResNet50 configuration or a production-quality detector. See the [full benchmark report (Turkish)](docs/visa-benchmark.tr.md).

```console
python -m pcb_anomaly.visa_benchmark --output data/visa-benchmark-v1
python -m pcb_anomaly.benchmark_review --benchmark data/visa-benchmark-v1
```

Use a new output directory for a new run. The experiment saves its fixed protocol and reference IDs before computing test scores. Raw predictions, memory banks and qualitative patch maps stay local. Pixel-level localization metrics have not yet been evaluated.

## Five reference selections and official WideResNet50 PatchCore

The study is complete for seeds 42–46, with 64 normal references/category and the same 802 test images throughout. The official PatchCore implementation is pinned to commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad` and uses the README's 224-pixel WideResNet50 setup with a 10% coreset.

| Method | Macro AUROC (%) | Sensitivity (%) | Observed FPR (%) |
|---|---:|---:|---:|
| Global ResNet18 + 3NN | 84.93 ± 0.68 | 48.10 ± 2.17 | 5.67 ± 1.13 |
| PatchCore–ResNet18 variant | 87.49 ± 1.33 | 60.35 ± 5.11 | 6.47 ± 2.37 |
| Official PatchCore–WideResNet50 | 95.73 ± 0.19 | 82.10 ± 2.79 | 7.16 ± 1.03 |

Values are mean ± sample SD across reference selections, not confidence intervals. Backbone, preprocessing and memory size differ; this is a comparison of full configurations. The WideResNet50 model misses 43 defects in all five runs. See the [full study and category results (Turkish)](docs/visa-five-seeds.tr.md), [plot](docs/figures/visa-five-seeds.png), and [machine-readable results](reports/visa-five-seeds-v1.json).

```console
python -m pip install -e ".[features,benchmark]"
python -m pcb_anomaly.upstream_patchcore
python -m pcb_anomaly.multiseed plan
python -m pcb_anomaly.multiseed rn
python -m pcb_anomaly.multiseed wrn
python -m pcb_anomaly.multiseed_report
```

Fetch upstream code once into the ignored data directory. Use a fresh `--output` directory for a new study. A stopped WRN run can continue with `wrn --resume`. The tests do not require downloading models or installing the benchmark extra. Tested benchmark environment: Python 3.12, CPU PyTorch 2.10.0.

Raw data, weights, local analyses and project reports are excluded from Git. Dataset terms are separate from code licensing. A code license and citation metadata have not yet been selected; public visibility alone does not grant an open-source license.
