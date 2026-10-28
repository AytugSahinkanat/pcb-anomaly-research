# PCB Anomaly Research

Reproducible data auditing and evaluation utilities for PCB component anomaly research.

**Status:** research code and controlled real-defect benchmark results. No production-validated detector is provided.

See the [project status and research roadmap (Turkish)](docs/project-status.tr.md) for completed evidence, missing validation and publication goals.

## Implemented

- Read-only ZIP audit, image/XML matching and bounding-box validation.
- Quoted multi-word category parsing and unique annotation IDs.
- Reproducible candidate board-group splits with class coverage reports.
- Task-specific leave-one-source-PCB-out split manifests for SolDef_AI annotations.
- Board-held-out frozen ResNet18 and HOG ROI classification baselines for SolDef_AI.
- Reproducible PCB-AoI archive/XML audit and board-held-out frozen-feature defect-type ROI baseline.
- Fixed torchvision Faster R-CNN baseline and AP evaluation on the official PCB-AoI board split.
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
3. Validate the matched operating-point analysis on independent, board-separated images and more calibration normals.
4. Compare corrected ResNet18+kNN, PatchCore, EfficientAD and AnomalyDINO.
5. Measure the effect of board context at controlled false-alarm budgets.

## Data and attribution

Kuo, Ashmore, Huggins and Kira, *Data-Efficient Graph Embedding Learning for PCB Component Detection*, WACV 2019. [Paper](https://arxiv.org/abs/1811.06994).

Defect-data preparation is implemented for [VisA / SPot-the-Difference](https://github.com/amazon-science/spot-diff) PCB1–PCB4 and an annotation inventory for [SolDef_AI](https://www.kaggle.com/datasets/mauriziocalabrese/soldef-ai-pcb-dataset-for-defect-detection). See the [data audit and evaluation protocol (Turkish)](docs/defect-data.tr.md).

The public [PCB-AoI SPI dataset](https://kaggle.com/datasets/kubeedgeianvs/pcb-aoi) now has an archive/XML audit, board-held-out ROI class baseline, and end-to-end detector pilot. Its test contains no normal images, so false-alarm or one-class anomaly performance cannot be estimated. See the [ROI classification report](docs/pcb-aoi-classifier.tr.md) and [full-box detection report](docs/pcb-aoi-detector.tr.md) (Turkish).

An external-data review records candidate datasets, access conditions and task mismatches in the [independent defect-data review (Turkish)](docs/independent-data-review.tr.md). No new independent SMD solder validation result has been produced yet.

```console
python -m pcb_anomaly.visa acquire --root data/visa-pcb-v2 --archive data/downloads/VisA_20220922.tar
python -m pcb_anomaly.visa audit --root data/visa-pcb-v2 --output data/visa-audit-v1
python -m pcb_anomaly.soldef acquire --root data/soldef-ai
python -m pcb_anomaly.soldef audit --root data/soldef-ai --output data/soldef-audit-v1
python -m pcb_anomaly.soldef_split --manifest data/soldef-audit-v1/annotations.jsonl --output data/soldef-board-splits-v1
python -m pcb_anomaly.soldef_resnet --split-manifest data/soldef-board-splits-v1/manifest.jsonl --archive data/soldef-ai/archive.zip --output data/soldef-resnet18-new
```

VisA preserves the official test split and holds out 100 normal training images per PCB category for calibration. Image/mask geometry and cross-split exact RGB duplicates are checked. Physical-board independence is not established. SolDef inventories raw polygon labels and repeated files without assuming unlabeled images are normal. Task-specific source-PCB splits and frozen ResNet18/HOG ROI-classification baselines are available. See the [board-separated split report](docs/soldef-board-splits.tr.md) and [first results (Turkish)](docs/soldef-resnet18.tr.md).

ResNet18 reaches 57.4% / 52.3% pooled balanced accuracy for position / solder classification; HOG reaches 55.1% / 42.8%. These are small descriptive ROI results, not full-image anomaly detection or independent final validation. See the [fold and class metrics](docs/soldef-resnet18.tr.md).

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

## Matched preprocessing and memory ablation

The 2-backbone × 2-preprocessing × 2-bank-budget study is complete across five reference selections and four PCB categories: 160 evaluations, including 20 exact prior configurations reused with prediction checks. Both backbones use the same pinned upstream PatchCore implementation, 1,024-dimensional float32 features and identical bank bytes.

With common resize256/center-crop224 preprocessing:

| Backbone | Feature-bank MiB | Macro AUROC (%) | Sensitivity (%) | Observed FPR (%) |
|---|---:|---:|---:|---:|
| ResNet18 | 1.96 | 91.06 ± 0.95 | 68.50 ± 3.05 | 5.77 ± 0.64 |
| WideResNet50-2 | 1.96 | 94.36 ± 0.29 | 78.20 ± 3.59 | 6.57 ± 1.38 |
| ResNet18 | 19.60 | 94.84 ± 0.31 | 78.90 ± 4.13 | 6.57 ± 2.73 |
| WideResNet50-2 | 19.60 | 95.73 ± 0.19 | 82.10 ± 2.79 | 7.16 ± 1.03 |

The matched large-bank backbone gap is **0.89 ± 0.28 AUROC percentage points**, compared with the historical configuration gap of 8.24 points. The small-bank gap is **3.31 ± 1.13 points**. Preprocessing and bank size explain much of the historical difference along the documented sequential comparison; effects interact, so there is no unique additive attribution. Bank equality excludes backbone parameters and activation memory. The same inspected test set is reused; this is a descriptive ablation, not independent final validation.

See the [full factorial report (Turkish)](docs/visa-controlled.tr.md), [comparison figure](docs/figures/visa-controlled.png), [preprocessing examples](docs/figures/visa-controlled-preprocessing.png), and [results/provenance](reports/visa-controlled-v1.json).

```console
python -m pcb_anomaly.controlled plan
python -m pcb_anomaly.controlled run
python -m pcb_anomaly.preprocessing_review
python -m pcb_anomaly.controlled_report
```

Requires the completed previous study and cached data/weights. Use a fresh `--output` for a new plan; rerun `run` to continue interrupted evaluations from atomic checkpoints. New bank indices/hashes and all predictions remain local. All 160 first-query checks agree exactly with upstream full prediction; 24,040 nested-bank distance checks and 48 unit tests pass. Timing is not an isolated speed benchmark.

## Calibration operating points and missed defects

Existing scores were recalibrated at nominal 1%, 5% and 10% false-alarm quantiles using 100 normal calibration images/category. At the 5% target (4% empirical calibration alarms), large-bank crop ResNet18 and small-bank crop WideResNet50-2 both have 6.57% observed test FPR and 78.9%/78.2% defect recall. Large-bank WideResNet50-2 reaches 82.1% recall at 7.16% FPR. These are measurements on the previously examined test images, not independent validation.

At the same 5% threshold, 43/400 defects are persistently missed by each large-bank model, with 29 shared misses. The smallest defect-mask quartile contains most persistent misses; PCB3 remains hardest. See the [operating-point and error report (Turkish)](docs/visa-operating-points.tr.md), [threshold plot](docs/figures/visa-operating-points.png), [miss gallery](docs/figures/visa-operating-points-misses.png), and [full result/provenance file](reports/visa-operating-points-v1.json).

```console
python -m pcb_anomaly.operating_points --output data/visa-operating-points-v2
```

This reads the completed `visa-controlled-v1` output, VisA manifest and defect masks. It recomputes thresholds from calibration scores and produces descriptive error reports without model inference.

Raw data and weights stay outside Git. Numerical summaries and attributed research figures are versioned. Dataset terms are separate from code licensing. A code license and citation metadata have not yet been selected; public visibility alone does not grant an open-source license.
