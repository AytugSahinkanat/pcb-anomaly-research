# PatchCore Comparisons for Few-Reference PCB Anomaly Detection: Effects of Preprocessing and Memory Budget

**Working manuscript draft — 9 November 2026**

## Abstract

Few-reference visual inspection of printed circuit boards (PCBs) often relies on nearest-neighbour anomaly detection, yet reported backbone comparisons can also change preprocessing and the size of the stored feature bank. This study examines how these choices interact in PatchCore on the four PCB categories of the VisA benchmark. We evaluate ResNet18 and WideResNet50-2 under two input pipelines and two equal, cross-backbone patch-memory budgets, using five selections of 64 normal reference images per category. Across 160 category-level evaluations, the matched center-crop, 19.60 MiB configuration obtains a mean image-level AUROC of 94.84% with ResNet18 and 95.73% with WideResNet50-2, a paired difference of 0.89 ± 0.28 percentage points across reference selections. At 1.96 MiB, the corresponding backbone difference is 3.31 ± 1.13 points. With thresholds calibrated to a nominal 5% false-positive target, observed test false-positive rates are 6.57% for both large-bank ResNet18 and small-bank WideResNet50-2, with defect sensitivities of 78.9% and 78.2%, respectively. In a matched pixel-localization evaluation on the same 802 test images, WideResNet50-2 improves the four-category macro pixel AUROC from 97.86 ± 0.08% to 98.52 ± 0.04%, pixel AP from 44.65 ± 0.33% to 49.52 ± 0.45%, and AUPRO at 30% FPR from 83.16 ± 0.41% to 86.62 ± 0.25%. These results show that the apparent backbone advantage depends on preprocessing and patch-memory budget, and that localization quality varies by PCB category. A separate same-16-reference full-pipeline comparison found macro pixel AP of 53.76% for AnomalyDINO and 47.30% for WideResNet50-2 PatchCore, while PatchCore had higher pixel AUROC (98.01% versus 96.25%) and a smaller feature bank (4.90 versus 94.5–108.9 MiB). The study is a controlled benchmark analysis on the official VisA test images; it does not establish production generalization.

**Keywords:** PCB inspection; visual anomaly detection; few-reference learning; PatchCore; memory bank; calibration; VisA

## 1. Introduction

Visual inspection of PCBs must identify defects that may be rare while normal images are easier to collect. In a one-class or few-reference setting, the detector represents normal appearance from a small reference set and scores a query image according to how far its visual features lie from that reference. PatchCore is a representative patch-based method: it stores a coreset of nominal patch features and uses nearest-neighbour distances for anomaly scoring and localization [1]. The VisA dataset provides high-resolution normal and anomalous images, pixel masks, and four PCB categories for this evaluation [2].

The choice of feature backbone is only one part of such a comparison. Input resizing and cropping change which image content reaches the feature extractor, while memory-bank size changes how densely normal patch appearances are represented. If these settings differ between methods, an observed performance gap cannot be attributed to the backbone alone. This matters in practical inspection because a larger feature memory may improve matching while increasing storage and deployment costs.

This paper measures the interaction between backbone, preprocessing, and patch-memory budget in a controlled PatchCore comparison on VisA PCB1–PCB4. The study asks:

1. How much does the WideResNet50-2 versus ResNet18 image-level anomaly-ranking gap change when preprocessing and patch-memory bytes are matched?
2. Do those rankings correspond to a similar operating point after thresholds are selected from normal calibration images?
3. Which PCB categories and defect cases account for the remaining errors?

The contribution is an empirical analysis of a controlled set of configurations, repeated over five normal-reference selections. It is not a new anomaly-detection architecture. The main finding is that a historical 8.24-point configuration gap narrows substantially when the compared models share preprocessing and memory: in the large-bank center-crop setting, the matched gap is 0.89 ± 0.28 AUROC points. This narrows the interpretation of backbone comparisons on this benchmark and makes the associated false-alarm and sensitivity trade-offs visible.

## 2. Related Work

### 2.1 Patch-based industrial anomaly detection

PatchCore models nominal data with pretrained local features and a coreset memory bank, supporting both image-level anomaly detection and spatial anomaly maps [1]. Its design makes patch-memory size and feature extraction settings explicit experimental factors. This paper keeps the PatchCore scoring implementation fixed while varying the backbone, input preprocessing, and bank budget.

### 2.2 VisA and few-reference evaluation

VisA contains 10,821 high-resolution images across 12 object subsets, including PCB1–PCB4, with pixel-level anomaly masks for anomalous samples [2]. Its PCB subsets provide cluttered, multi-component scenes, making them relevant to small and localized defects. AnomalyDINO is a recent training-free few-shot baseline that uses DINOv2/14 patch features, cosine nearest neighbours, reference rotations and an image score based on the mean of the highest-scoring 1% of patches [3]. Its published VisA evaluation covers 1, 2, 4, 8 and 16 shots at 448- and 672-pixel resolutions, and reports image- and pixel-level AUROC/AP/PRO measures. Its preprocessing and scoring differ from our controlled PatchCore configurations, so a direct result would be a full-pipeline comparison rather than an isolated backbone contrast. A protocol for adding it is documented in [the baseline plan](anomalydino-baseline-plan.tr.md); the present results should therefore be read as a controlled PatchCore ablation, not a current leaderboard comparison.

**Literature review status:** this section needs a broader search and comparison table before submission.

## 3. Data and Experimental Protocol

### 3.1 Dataset

We use the official VisA split for PCB1, PCB2, PCB3, and PCB4. The benchmark audit covers 4,416 images and 400 defect masks across the four PCB subsets. The official test partition contains 802 images. One hundred normal images per category are withheld from the nominal training data for threshold calibration. The same test images are reused across the five reference selections; they are not a new external test set.

### 3.2 PatchCore configurations

The comparison uses the official PatchCore implementation pinned to commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad`. ImageNet-pretrained backbones are frozen. We evaluate:

- **Backbone:** ResNet18 and WideResNet50-2.
- **Preprocessing:** square padding and resize to 224 pixels, or resize the short side to 256 pixels followed by a 224-pixel center crop.
- **Patch-memory budget:** 501 or 5,017 feature vectors, each with 1,024 float32 dimensions. These correspond to 1.957 MiB and 19.598 MiB, matched across backbones.
- **Reference selection:** five selections, seeds 42–46, with 64 normal reference images per category.

The full factorial contains 2 × 2 × 2 × 5 × 4 = 160 category-level evaluations. The factors and reference selections are paired across the evaluated configurations. The reported ± values below are sample standard deviations across the five reference selections; they are not confidence intervals over new boards or new test images.

### 3.3 Metrics and threshold calibration

Image-level AUROC and average precision summarize ranking quality. We also report defect sensitivity and the observed test false-positive rate at thresholds selected from normal calibration scores. The operating-point analysis targets a nominal 5% calibration false-positive rate using 100 normal calibration images per category. The resulting test false-positive rate is measured after calibration and may differ from 5%.

Pixel AUROC and non-interpolated pixel AP are computed over all pixels within each category and test split. For localization, upstream PatchCore patch distances are unpatched to a 28×28 map, bilinearly upsampled to 224×224 and smoothed with the upstream Gaussian filter (sigma 4). Binary masks receive the same resize-and-center-crop geometry as the images, using nearest-neighbour interpolation. AUPRO uses 200 equally spaced score thresholds, averages overlap over connected defect regions, truncates the false-positive rate at 0.30 and normalizes the area by 0.30. Each category/seed is measured separately; the macro result gives equal weight to the four PCB categories. Reported standard deviations are across the five reference selections (seeds 42–46), not confidence intervals over new boards or test samples. Full seed-level measurements and the runner are provided in [the localization report and results](visa-localization.tr.md).

## 4. Results

### 4.1 Matched center-crop comparison

| Backbone | Patch memory | Image AUROC (%) | Image AP (%) | Defect sensitivity (%) | Observed test FPR (%) |
|---|---:|---:|---:|---:|---:|
| ResNet18 | 1.957 MiB | 91.06 ± 0.95 | 91.88 ± 1.03 | 68.50 ± 3.05 | 5.77 ± 0.64 |
| WideResNet50-2 | 1.957 MiB | 94.36 ± 0.29 | 94.84 ± 0.35 | 78.20 ± 3.59 | 6.57 ± 1.38 |
| ResNet18 | 19.598 MiB | 94.84 ± 0.31 | 94.80 ± 0.25 | 78.90 ± 4.13 | 6.57 ± 2.73 |
| WideResNet50-2 | 19.598 MiB | 95.73 ± 0.19 | 95.84 ± 0.25 | 82.10 ± 2.79 | 7.16 ± 1.03 |

Values are means ± sample standard deviations over five reference selections. The sensitivity and FPR columns summarize the calibrated operating-point analysis. Since the observed test FPRs differ, these rows do not compare sensitivity at an exactly equal test FPR.

At the 19.598 MiB budget, WideResNet50-2 exceeds ResNet18 by 0.89 ± 0.28 image-AUROC points across paired reference selections. At 1.957 MiB, the difference is 3.31 ± 1.13 points. Increasing memory improves ResNet18 by 3.78 AUROC points under center-crop preprocessing and WideResNet50-2 by 1.37 points. These results show an interaction between backbone and memory budget: the larger backbone's advantage is smaller with the larger bank.

### 4.2 Calibration operating point

At the nominal 5% calibration target, the large-bank center-crop ResNet18 detects 78.9% of test defects with a 6.57% observed test FPR. The small-bank center-crop WideResNet50-2 detects 78.2% with the same 6.57% observed FPR. The large-bank WideResNet50-2 detects 82.1% but raises the observed test FPR to 7.16%. These are measurements on the previously examined VisA test images and should not be interpreted as production-line performance.

### 4.3 Pixel-level localization

Under the matched 19.598 MiB memory budget and center-crop preprocessing, WideResNet50-2 exceeds ResNet18 on all three pixel-level measures when averaged over PCB1–PCB4. The paired macro gain over five reference selections is 0.66 ± 0.07 percentage points in pixel AUROC, 4.87 ± 0.14 points in pixel AP and 3.46 ± 0.45 points in AUPRO at an FPR cap of 0.30.

| Category | ResNet18 AUROC | WideResNet50-2 AUROC | ResNet18 AP | WideResNet50-2 AP | ResNet18 AUPRO | WideResNet50-2 AUPRO |
|---|---:|---:|---:|---:|---:|---:|
| PCB1 | 99.40 ± 0.04 | **99.54 ± 0.02** | 80.00 ± 0.50 | **88.09 ± 0.16** | 91.63 ± 0.56 | **92.08 ± 0.38** |
| PCB2 | 97.02 ± 0.24 | **98.06 ± 0.05** | 15.90 ± 0.26 | **18.53 ± 0.28** | 84.71 ± 0.80 | **87.64 ± 0.63** |
| PCB3 | 98.75 ± 0.05 | **98.86 ± 0.03** | 45.08 ± 0.48 | **46.40 ± 0.62** | 78.45 ± 1.95 | **83.91 ± 0.83** |
| PCB4 | 96.26 ± 0.28 | **97.61 ± 0.17** | 37.65 ± 1.63 | **45.09 ± 1.73** | 77.87 ± 1.37 | **82.86 ± 1.26** |

Values are percentages, mean ± sample standard deviation over five reference selections. Pixel AP is sensitive to defect-pixel prevalence; PCB2 remains difficult, with AP below 19% for both models despite AUROC near or above 97%. This illustrates why AUROC alone does not describe localization performance. Maps and masks cover the 224×224 center-cropped field only.

### 4.4 Same-reference full-pipeline comparison

We evaluated the pinned WACV 2025 AnomalyDINO pipeline and official WideResNet50-2 PatchCore using the same 16 normal reference images for each of five predeclared selections, across the same 802 VisA PCB test images. Both use the common 224×224 center-cropped field of view. DINOv2 receives the field enlarged to 448×448, uses eight-angle reference augmentation and PCA foreground masking, and scores the top 1% patch cosine distances. PatchCore uses unaugmented 224×224 images, layer2/layer3 features, a 10% approximate greedy coreset, and Euclidean 1-NN distances.

| Method | Reference images | Feature-bank size | Image AUROC (%) | Image AP (%) | Pixel AUROC (%) | Pixel AP (%) | AUPRO (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| AnomalyDINO / DINOv2 ViT-S/14 | 16 | 94.5–108.9 MiB | 95.18 ± 0.17 | 95.85 ± 0.18 | 96.25 ± 0.03 | 53.76 ± 0.59 | 88.56 ± 0.23 |
| PatchCore / WideResNet50-2 | 16 | 4.90 MiB | 91.92 ± 0.99 | 92.06 ± 1.34 | 98.01 ± 0.14 | 47.30 ± 1.62 | 82.92 ± 0.85 |

The paired macro difference (AnomalyDINO minus PatchCore) over five selections is +3.27 ± 0.85 percentage points in image AUROC, +3.79 ± 1.24 in image AP, −1.75 ± 0.12 in pixel AUROC, +6.46 ± 1.14 in pixel AP, and +5.64 ± 0.68 in AUPRO. These standard deviations describe reference-selection variability on the same test images, not uncertainty over new boards.

The comparison does not identify a universal winner. AnomalyDINO gives higher image ranking, pixel AP, and AUPRO in this setup; PatchCore gives higher pixel AUROC and uses a much smaller feature bank. The methods differ in preprocessing interpolation, rotation augmentation, feature representation, masking, bank construction, and scoring. This is a comparison of complete pipelines at the same source-image count, not a backbone ablation or equal-memory test. The [paired report and seed-level results](visa-16shot-comparison.tr.md) provide category details and limitations.

### 4.5 Category variation and image-level errors

PCB3 remains more difficult than the other categories under the large-bank comparison. In the five-seed operating-point study, the large-bank ResNet18 and WideResNet50-2 share 29 persistent misses among the 400 annotated defects; small mask areas are overrepresented among the misses. A submission version should add a compact per-category table and report the exact error-gallery selection procedure.

## 5. Discussion

The matched comparison changes the interpretation of the earlier backbone gap. The earlier 8.24-point difference compared complete configurations that differed in more than backbone. Under common center-crop preprocessing and an equal 19.598 MiB patch bank, the observed difference is below one AUROC point. At a smaller bank, the difference is larger. Therefore, the backbone effect on this benchmark depends on how much nominal patch memory is available and which preprocessing pipeline is used.

Image-level ranking and thresholded inspection are related but distinct. A higher AUROC does not guarantee a better operating point at a fixed false-alarm budget. In the current measurements, the large-bank WideResNet50-2 catches more defects while producing a higher observed test FPR. The small-bank WideResNet50-2 provides a sensitivity/FPR trade-off close to the large-bank ResNet18 while using one tenth of the patch-bank storage, although the complete model memory and inference speed were not matched or benchmarked.

For industrial engineering interpretation, false alarms can increase operator review and rework, while missed defects can pass downstream inspection. The current test set does not establish a plant-level reject threshold: the calibration images and test images come from the benchmark distribution, and no production line, operator workload, or quality-cost function was evaluated.

A related industrial challenge is preparing AOI for a new PCB before a physical golden-board sample is available, then reducing false calls on AOI candidates. Siemens and NVIDIA describe a workflow that connects PCB design and bill-of-material information to a digital twin, generates synthetic good/defect images, and supports secondary review of suspected defects [4, 5]. Our study addresses only anomaly scoring and localization on existing physical VisA images; it does not evaluate digital-twin data generation, AOI integration, or calibration time.

## 6. Limitations

1. All five reference selections use the same public VisA test images. The test set was reused across exploratory analyses; therefore, the current paper should present these numbers as benchmark results and avoid selecting a new method or parameter from these test results.
2. The evaluated feature-bank budgets are matched, but backbone parameter count, activation memory, total RAM/VRAM, and end-to-end runtime are not.
3. Pixel masks and maps were both resized to 224×224; localization metrics do not cover pixels outside the center crop. The AUPRO result uses a finite 200-threshold approximation.
4. All five reference selections reuse the same official test images, which were already examined in earlier project analyses. Seed variability does not replace board-level or independent-test uncertainty.
5. RobustAD-PCB was acquired, audited, and evaluated with three baselines using the same five 16-normal-reference selections. ResNet18 and WideResNet50-2 PatchCore share full-frame 224-pixel preprocessing and an equal 4.90 MiB patch memory; the AnomalyDINO pipeline uses 448-pixel DINOv2 features, eight reference rotations and PCA foreground masking, with an approximately 80 MiB bank. On the five shifted capture domains, macro image AUROC was 44.84% for WideResNet50-2, 37.35% for ResNet18, and 43.52% for AnomalyDINO. AnomalyDINO had higher pixel AP and AUPRO (7.55% and 64.07%) than the PatchCore configurations, while image ranking remained poor; its pipeline and memory differ. All three shifted-domain macro image AUROCs were below 50%. This is initial evidence of capture-domain sensitivity and a separation between image detection and localization, not an unseen-board result. Physical board IDs are absent, and source normal/anomaly labels correlate with image dimensions. No external, board-held-out solder-joint anomaly test has been completed. PCB-AoI's completed result is ROI defect-type classification on defective paste-inspection crops, a different task. SolDef_AI results cover only three source PCB groups and remain descriptive.
6. The current manuscript evaluates PatchCore configurations and AnomalyDINO as a distinct full pipeline; it does not introduce a new method. The same-16-reference comparison is complete, but publication claims remain limited by reuse of the public VisA test split.

## 7. Conclusion

On VisA PCB1–PCB4, matching preprocessing and patch-memory bytes substantially reduces the apparent WideResNet50-2 advantage over ResNet18 at the large-bank image-level operating point, while the smaller bank retains a larger gap. At the matched large bank, WideResNet50-2 also improves macro pixel AUROC, AP and AUPRO; PCB2 nevertheless remains a difficult sparse-defect category. In the separate same-16-reference full-pipeline comparison, AnomalyDINO is higher on image AUROC/AP, pixel AP and AUPRO, while PatchCore is higher on pixel AUROC with a much smaller feature bank. Memory and preprocessing therefore need to be controlled when interpreting model comparisons, and image-level ranking alone does not define localization quality or a practical inspection threshold. Further work should add runtime and full-memory measurements and—if access and board identifiers are obtained—an external board-held-out solder-joint evaluation.

## References

[1] K. Roth, L. Pemula, J. Zepeda, B. Schölkopf, T. Brox, and P. Gehler, “Towards Total Recall in Industrial Anomaly Detection,” *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 2022, pp. 14318–14328. [Paper](https://openaccess.thecvf.com/content/CVPR2022/html/Roth_Towards_Total_Recall_in_Industrial_Anomaly_Detection_CVPR_2022_paper.html).

[2] M. Zou et al., “SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation,” *European Conference on Computer Vision*, 2022. [Paper](https://www.ecva.net/papers/eccv_2022/papers_ECCV/html/2149_ECCV_2022_paper.php).

[3] S. Damm, M. Laszkiewicz, J. Lederer, and A. Fischer, “AnomalyDINO: Boosting Patch-Based Few-Shot Anomaly Detection with DINOv2,” *Proceedings of the IEEE/CVF Winter Conference on Applications of Computer Vision*, 2025, pp. 1319–1329. [Paper](https://openaccess.thecvf.com/content/WACV2025/html/Damm_AnomalyDINO_Boosting_Patch-Based_Few-Shot_Anomaly_Detection_with_DINOv2_WACV_2025_paper.html).

[4] Siemens, “Siemens and NVIDIA advance AI-powered PCB inspection from Digital Twin to factory,” 21 October 2026. [Press release](https://news.siemens.com/en-us/siemens-nvidia-pcba-digital-twin-factory/).

[5] NVIDIA, “Europe’s Industrial Leaders Reinvent Engineering and Manufacturing With NVIDIA,” 21 October 2026. [Article](https://blogs.nvidia.com/blog/europe-industrial-leaders-engineering-manufacturing/).

## Items to complete before submission

- [ ] Audit and document how prior test-set results informed later experiment choices.
- [x] Add pixel AUROC, AP and AUPRO/PRO for the matched center-crop large-bank comparison; a wider factorial localization ablation remains future work.
- [ ] Obtain an untouched, board/session-held-out real-defect test set; freeze all method and threshold choices before evaluation.
- [ ] Add per-category tables and image-/board-level uncertainty intervals where supported.
- [ ] Measure inference time and complete CPU RAM/GPU VRAM, separately from bank bytes.
- [ ] Resolve external data access, source-board grouping, and license; otherwise keep external claims out.
- [ ] Expand the literature review, add data citations/license notes, and proofread the final English manuscript.
