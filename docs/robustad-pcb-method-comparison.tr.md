# RobustAD-PCB: üç PatchCore / AnomalyDINO başlangıç yöntemi

**Durum:** Üç yöntem aynı RobustAD-PCB çekim koşullarında, beş ortak normal-referans seçimiyle çalıştırıldı. Sonuçlar eşik değil sıralama ölçüleridir; henüz üretim çalışma noktası veya yeni kart tasarımına genelleme kanıtı değildir.

## Ortak değerlendirme protokolü

Veri sürümü `82c642b2d18be60f2dab104f8dd4dea1f4ccfacb`. Her seed'de referanslar, yalnızca eğitim bölümündeki 180 normal görüntü arasından seçilen aynı 16 görüntüdür (`42–46`). Eğitim kusurları kullanılmadı. Aynı resmî `test0`–`test5` alanları ve tam PCB görüntü alanı korundu; `test4` içindeki SHA-256 eş görüntü ana analizde bir kez sayıldı ve iki maskesi birleştirildi. Ayrı kayıt/maske duyarlılığı ayrıca hesaplandı.

ResNet18 ve WideResNet50-2, aynı 224×224 tam-kare ön işlemeyi ve PatchCore yapılandırmasını kullandı: 1.024 boyutlu yamalar, yaklaşık %10 greedy coreset ve Öklid 1-NN. Her iki bankada da 1.254 yama / 5.136.384 bayt (4,90 MiB) vardı.

AnomalyDINO sonucu **tam-pipeline kıyasıdır**. DINOv2 ViT-S/14'e tam PCB karesi 448×448 olarak verildi; 16 referansın her biri sekiz yönelimde artırıldı, PCA tabanlı ön plan maskesi kullanıldı ve en yüksek %1 yama kosinüs uzaklığı ortalandı. Bunun DINO referans belleği seed'e göre 79,68–80,47 MiB oldu. Girdi çözünürlüğü, artırma, ön plan maskesi, özellik ve skor PatchCore'dan farklı olduğu için bu fark yalnızca omurga etkisi sayılamaz.

Maskeler ve skor haritaları ortak 224×224 tam-kare değerlendirme alanında ölçüldü. Eşik ayarlanmadı. Hedef-alan makro ortalaması, test1–test5'in eşit ağırlıklı ortalamasıdır. ± değerler beş eşlenmiş referans seçiminin farklarındaki örnek standart sapmadır; güven aralığı değildir.

## Kaynak ve değişen alan sonuçları

Tüm metrikler yüzde cinsindendir.

| Yöntem | Kaynak test görüntü AUROC | test1–test5 görüntü AUROC | Görüntü AP | Piksel AUROC | Piksel AP | AUPRO@FPR≤0,30 |
|---|---:|---:|---:|---:|---:|---:|
| WideResNet50-2 PatchCore | 96,35 | **44,84** | **43,17** | 87,16 | 5,42 | 48,84 |
| ResNet18 PatchCore | 90,27 | 37,35 | 40,60 | 85,71 | 5,71 | 41,57 |
| AnomalyDINO full pipeline | 90,12 | 43,52 | 39,04 | **91,97** | **7,55** | **64,07** |

AnomalyDINO, iki PatchCore hattından daha yüksek piksel AP ve AUPRO verdi; yama uzaklık haritası kusur bölgelerini sıralamada umut verici görünüyor. Görüntü tespitinde ise WideResNet50-2'nin altında kaldı: DINO için hedef-alan görüntü AUROC'u %43,52, WideResNet50-2 için %44,84. Üç yöntemin de hedef-alan ortalama görüntü AUROC'u %50'nin altında.

| Hedef alan | WRN50 görüntü AUROC / AUPRO | ResNet18 görüntü AUROC / AUPRO | AnomalyDINO görüntü AUROC / AUPRO |
|---|---:|---:|---:|
| Aydınlatma | 40,07 / 46,50 | 27,83 / 38,79 | 49,72 / 70,40 |
| Beyaz dengesi | 53,64 / 55,07 | 27,58 / 42,83 | 40,40 / 64,21 |
| Dönüş | 39,45 / 60,64 | 35,89 / 48,05 | 47,07 / 60,50 |
| Konum | 43,11 / 46,72 | 29,99 / 42,95 | 35,17 / 65,55 |
| Gölge / arka plan | 47,94 / 35,28 | **65,46** / 35,21 | 45,27 / 59,68 |

Seed eşleştirmeli test1–test5 farklarında DINO eksi WideResNet50 görüntü AUROC'u **−1,32 ± 4,51** puan; piksel AUROC'u **+4,81 ± 0,48**; piksel AP'si **+2,13 ± 2,48**; AUPRO'su **+15,23 ± 2,03** puandı. DINO eksi ResNet18 farkları görüntü AUROC'ta **+6,17 ± 2,61**, piksel AUROC'ta **+6,26 ± 0,70** ve AUPRO'da **+22,50 ± 1,92** puandı. Bu beş seçim aynı test karelerini kullandığı için seed sapmaları bağımsız kart belirsizliği değildir.

Piksel AP ölçülerini seyreklikle birlikte okumak gerekir: kusur pikselleri yeniden ölçeklenmiş görüntü alanının yaklaşık %0,02–0,06'sıdır. Bu nedenle yüksek piksel AUROC tek başına iyi lokalizasyon kanıtı değildir; AP ve AUPRO tamamlayıcıdır.

## Yinelenen kare duyarlılığı

test4'te iki ayrı kayıt/maske kullanmak yerine tek görüntü ve birleşik maskeyle değerlendirme, DINO için görüntü AUROC'unu **0,34 puan**, AUPRO'yu **0,43 puan** değiştirdi. Diğer metriklerdeki farklar daha küçüktü. Bu tek kare, genel sonuçların büyüklüğünü belirlemiyor. Bununla birlikte kaynak etiketleme açıklaması olmadığı için ana tabloda kullanılan birleştirme kuralı açıkça korunmalı.

## Kusur türü alt analizi

İki aynı bellekli PatchCore omurgası için kaymış alanlardaki görüntü skorları kusur sınıfına göre de incelendi. WideResNet50-2, lehim erimesi/çizik sınıflarında daha yüksek makro AUROC; ResNet18 ise eksik komponentlerde daha yüksek makro AUROC verdi. Bu analiz görüntü düzeyindedir ve DINO'yu içermiyor; ayrıntı [kusur türü raporunda](robustad-pcb-defect-type-error-analysis.tr.md). Dolayısıyla DINO'nun alan makro tablosundaki genel yerelleştirme sonuçları bu sınıf tablosuna taşınmamalı.

## Sınırlar ve sonraki adım

- Bu, bir veri kümesinde üç başlangıç yapılandırmasının karşılaştırmasıdır. Yeni yöntem katkısı veya üretim doğrulaması değildir.
- AnomalyDINO'nun yerelleştirme üstünlüğü daha büyük, yönelim artırmalı belleği ve farklı ön plan/puan hattı ile birlikte gelir; bellek ve işlem maliyeti eşit değildir.
- Kaynak train/test0'da normal görüntüler 2560×2560, kusurlular 2048×2048. Tam kareyi ortak boyuta indirmek tensör boyutunu eşitler ama görüntü ölçeği/görüş alanı farkını gidermez; yüksek kaynak sonucu bu nedenle ihtiyatla yorumlanmalı.
- Metadata'da fiziksel kart/tasarım ID yok. Bu sonuç çekim koşulu dayanıklılığı hakkındadır; yeni PCB tasarımında board-held-out doğrulama değildir.
- Alan bazında hata incelemesi tamamlandı; PatchCore için görüntü düzeyinde kusur türü alt analizi de eklendi. DINO'nun kusur alt grubu ve örnek karelerin nitel incelemesi sırada. Model seçimi veya eşik ayarı için test alanlarını kullanmamak gerekir. Eşikli çalışma noktası için eğitimden ayrılmış normal kalibrasyon örnekleri ve son testten ayrı değerlendirme protokolü önceden tanımlanmalıdır.
- Kusur türü alt sonuçları keşifseldir, az örnek içerir ve DINO'yu kapsamaz.

## Üretilebilirlik

- Veri denetimi: [RobustAD-PCB audit](robustad-pcb-audit.tr.md)
- PatchCore ayrıntıları: [ResNet18 / WideResNet50 raporu](robustad-pcb-patchcore.tr.md)
- AnomalyDINO koşucusu: [`robustad_anomalydino.py`](../src/pcb_anomaly/robustad_anomalydino.py)
- Üç yöntemin per-seed, alan ve maske-duyarlılık sonuçları: [`robustad-pcb-method-comparison-v1.json`](../reports/robustad-pcb-method-comparison-v1.json)
- DINO'nun tam makine-okunur çıktısı: [`robustad-pcb-anomalydino-v1.json`](../reports/robustad-pcb-anomalydino-v1.json)
