# AnomalyDINO ve 16 referanslı PatchCore karşılaştırması

**Durum:** 9 Kasım 2026'da tamamlandı  
**Veri:** VisA PCB1–PCB4, toplam 802 resmi test görüntüsü  
**Koşullar:** seed 42–46; her kategori/seed için aynı 16 normal referans görüntüsü; toplam 40 kategori-yöntem-seed sonucu.

## Özet

İki yöntemde kaynak normal görüntü sayısını eşitledik. DINO yönteminde her referans sekiz açıyla artırıldı; PatchCore'a döndürme artırması uygulanmadı. DINOv2 özellik belleği yaklaşık 94,5–108,9 MiB; PatchCore'un 10% greedy coreset belleği 4,90 MiB idi. Dolayısıyla kıyas eşit görüntü bütçeli, fakat eşit bellekli veya aynı yöntemli değildir.

Değerler yüzde ve beş referans seçiminin ortalaması ± örnek standart sapmasıdır. Makro ölçüm dört PCB kategorisine eşit ağırlık verir.

| Yöntem | Normal referans görüntüsü | Özellik belleği | Görüntü AUROC | Görüntü AP | Piksel AUROC | Piksel AP | AUPRO (FPR≤0,30) |
|---|---:|---:|---:|---:|---:|---:|---:|
| AnomalyDINO / DINOv2 ViT-S/14 | 16; sekiz yönelim | 94,5–108,9 MiB | 95,18 ± 0,17 | 95,85 ± 0,18 | 96,25 ± 0,03 | 53,76 ± 0,59 | 88,56 ± 0,23 |
| PatchCore / WideResNet50-2 | 16; artırma yok | 4,90 MiB | 91,92 ± 0,99 | 92,06 ± 1,34 | 98,01 ± 0,14 | 47,30 ± 1,62 | 82,92 ± 0,85 |

Eşlenmiş beş referans seçimi üzerinde DINO eksi PatchCore makro farkı görüntü AUROC'unda +3,27 ± 0,85 puan, görüntü AP'sinde +3,79 ± 1,24 puan, piksel AUROC'unda −1,75 ± 0,12 puan, piksel AP'sinde +6,46 ± 1,14 puan ve AUPRO'da +5,64 ± 0,68 puandır. Bu farklar aynı VisA test görüntülerinde ölçülmüştür; yeni kartlara genelleme aralığı değildir.

Sonuçlar tek bir yöntemin her ölçütte öne çıkmadığını gösteriyor: AnomalyDINO bu kurulumda görüntü sıralama, piksel AP ve AUPRO'da daha yüksek; PatchCore ise piksel AUROC'unda daha yüksek ve çok daha küçük özellik belleği kullanıyor. Piksel AP/AUPRO ve bellek birlikte ele alındığında çalışma noktası seçimi üretim ihtiyacına göre değişebilir. Fakat mevcut test seti eşik, model veya yöntem seçimi için yeniden kullanılmamalıdır.

## Kategori bazında kusur yerelleştirme

| PCB | DINO piksel AUROC | PatchCore piksel AUROC | DINO piksel AP | PatchCore piksel AP | DINO AUPRO | PatchCore AUPRO |
|---|---:|---:|---:|---:|---:|---:|
| PCB1 | 96,47 ± 0,01 | 99,21 ± 0,12 | 84,59 ± 0,56 | 86,15 ± 0,85 | 87,23 ± 0,18 | 87,30 ± 1,61 |
| PCB2 | 93,33 ± 0,01 | 97,35 ± 0,24 | 37,38 ± 0,56 | 16,15 ± 1,68 | 86,92 ± 0,28 | 85,25 ± 1,59 |
| PCB3 | 98,80 ± 0,03 | 98,65 ± 0,04 | 54,90 ± 0,47 | 46,57 ± 0,26 | 92,40 ± 0,25 | 80,57 ± 1,43 |
| PCB4 | 96,42 ± 0,12 | 96,82 ± 0,42 | 38,20 ± 1,82 | 40,35 ± 5,28 | 87,69 ± 0,85 | 78,55 ± 1,89 |

PCB2'de AUROC iki modelde de kusur piksellerinin azlığına rağmen yüksek kalırken AP ciddi biçimde ayrışıyor. PCB4'te iki yöntem AP bakımından benzer; seed değişkenliği PatchCore'da daha geniş. Bu kategori farkları, yalnız makro ortalamaya dayanarak tek bir üretim yöntemi önermememiz gerektiğini gösteriyor.

## Karşılaştırma koşulları ve sınırlar

- Aynı seed için seçilen 16 kaynak görüntü iki yöntemde aynıdır. Resmî PatchCore WideResNet50-2, `Resize(256)+CenterCrop(224)`, 1.024 boyutlu layer2/layer3 yamaları, 10% approximate greedy coreset ve 1-NN Öklid uzaklığı kullanır.
- AnomalyDINO, aynı 224×224 görüntü alanını 448×448'e büyütür; referansları sekiz açıyla artırır, PCA tabanlı ön plan maskesi ve kosinüs uzaklığı kullanır, görüntü skorunu en yüksek 1% yamadan hesaplar. Bunlar AnomalyDINO tam yönteminin farklı bileşenleridir.
- DINO ve PatchCore özellik boyutları/ölçekleri ve bankaları eşit değildir. Bu nedenle skor farkları tek başına mimariyi açıklamaz; sonuç bir tam-pipeline kıyasıdır.
- DINO kısa-kenar 448 varsayılanı yerine, PatchCore ile aynı görüş alanını korumak için 224 merkez kırpımını büyütür. Bu bilinçli uyarlama kayda geçirilmiştir.
- Test kümesi daha önceki proje deneylerinde kullanılmıştır. Beş referans seçimi test görüntülerini paylaşır; küçük seed standart sapması bağımsız genelleme kanıtı değildir.
- Bu benchmark eşik, yanlış alarm oranı veya üretim reddi seçmez. Gerçek saha iddiası için kart/oturum bazında bağımsız test verisi gerekir.

## Yeniden üretim

- PatchCore runner: [`visa_patchcore_16shot.py`](../src/pcb_anomaly/visa_patchcore_16shot.py); sonuçlar: [`visa-patchcore-16shot-v1.json`](../reports/visa-patchcore-16shot-v1.json).
- AnomalyDINO runner/sonuçlar: [`anomalydino_localization.py`](../src/pcb_anomaly/anomalydino_localization.py), [`visa-anomalydino.tr.md`](visa-anomalydino.tr.md), [`visa-anomalydino-v1.json`](../reports/visa-anomalydino-v1.json).
- PatchCore modeli ve coreset upstream `patchcore-inspection` commit `fcaa92f124fb1ad74a7acf56726decd4b27cbcad` üzerinden kullanıldı. Ağırlık ve görüntüler git deposuna dahil edilmez.
