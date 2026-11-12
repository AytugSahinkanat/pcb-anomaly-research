# VisA piksel düzeyi kusur yerelleştirme sonuçları

**Durum:** Tamamlandı · 4 Kasım 2026  
**Deney çıktısı:** `reports/visa-localization-v1.json`  
**Çalıştırıcı:** `src/pcb_anomaly/visa_localization.py`

## Soru ve deney

ResNet18 ve WideResNet50-2 tabanlı PatchCore modellerinin yalnızca kusurlu görüntüyü ayırıp ayırmadığını değil, kusurun yerini de bulup bulmadığını inceledik. VisA PCB1–PCB4'ün resmi test bölmesindeki 802 görüntüyü ve 400 kusur maskesini kullandık. Beş normal referans seçimi (seed 42–46) aynı test görüntülerinde eşleştirildi. Yama belleği iki omurgada da 5.017 × 1.024 float32 özellik, yani 19,598 MiB olarak sabitlendi; bu tablo büyük ve eşit bellekli merkez-kırpma koşuluna karşılık gelir.

Görüntüler resmi PatchCore ön işlemesiyle 256 kısa kenara ölçeklenip 224 merkez kırpma alır. İkili kusur maskelerine aynı geometrik dönüşüm en yakın komşu enterpolasyonuyla uygulanır. PatchCore'un 28×28 yama uzaklık haritası 224×224'e bilineer büyütülür ve resmi uygulamadaki Gauss sigma=4 yumuşatması kullanılır.

- **Piksel AUROC:** Kusurlu ve normal piksellerin skorla sıralanma başarısı.
- **Piksel AP:** Kusur pikseli seyrek olduğunda daha açıklayıcı hassasiyet-duyarlılık özeti; kategorinin kusur oranından etkilenir.
- **AUPRO:** Bağlı kusur bölgelerinin örtüşmesini yanlış pozitif normal piksel oranına karşı ölçer; FPR 0,30'da kesilip 0–1 aralığına normalize edilir. 200 eşit aralıklı skor eşiği kullanılır.

AUROC ve AP her kategori/seed için o kategorinin test pikselleri üzerinde hesaplanır. Genel sonuç, dört kategorinin her biri eşit ağırlıklandırılarak önce her seed için ortalanmış; tabloda **beş seed makro ortalamasının ortalama ± örnek standart sapması** verilmiştir. Bu sapma yeni kartlar veya yeni test örnekleri üzerinden güven aralığı değildir.

## Sonuçlar

### Dört PCB kategorisinin eşit ağırlıklı özeti

| Omurga | Piksel AUROC (%) | Piksel AP (%) | AUPRO, FPR≤0,30 (%) |
|---|---:|---:|---:|
| ResNet18 | 97,86 ± 0,08 | 44,65 ± 0,33 | 83,16 ± 0,41 |
| WideResNet50-2 | **98,52 ± 0,04** | **49,52 ± 0,45** | **86,62 ± 0,25** |

WideResNet50-2'nin seed-eşlenmiş makro kazancı AUROC'ta **+0,66 ± 0,07**, AP'de **+4,87 ± 0,14**, AUPRO'da **+3,46 ± 0,45 yüzde puanıdır**. Tek standart sapma aralıkları yalnızca referans seçiminin bu beş değeri arasındaki değişimi anlatır.

### Kategori sonuçları

Hücrelerde ortalama ± seed standart sapması vardır; metrikler yüzde olarak gösterilmiştir.

| Kategori | ResNet18 AUROC | WideResNet50-2 AUROC | ResNet18 AP | WideResNet50-2 AP | ResNet18 AUPRO | WideResNet50-2 AUPRO |
|---|---:|---:|---:|---:|---:|---:|
| PCB1 | 99,40 ± 0,04 | **99,54 ± 0,02** | 80,00 ± 0,50 | **88,09 ± 0,16** | 91,63 ± 0,56 | **92,08 ± 0,38** |
| PCB2 | 97,02 ± 0,24 | **98,06 ± 0,05** | 15,90 ± 0,26 | **18,53 ± 0,28** | 84,71 ± 0,80 | **87,64 ± 0,63** |
| PCB3 | 98,75 ± 0,05 | **98,86 ± 0,03** | 45,08 ± 0,48 | **46,40 ± 0,62** | 78,45 ± 1,95 | **83,91 ± 0,83** |
| PCB4 | 96,26 ± 0,28 | **97,61 ± 0,17** | 37,65 ± 1,63 | **45,09 ± 1,73** | 77,87 ± 1,37 | **82,86 ± 1,26** |

## Yorum

WideResNet50-2 dört kategoride de üç yerelleştirme ölçüsünde daha yüksek ortalama verdi. Fakat sonuç, kusurun tümünü bulduğumuz anlamına gelmez: PCB2 piksel AP'si iki modelde de %20'nin altında. PCB2'de yüksek AUROC'un tek başına yeterli olmadığı, seyrek kusur piksellerine duyarlı AP ve bölge örtüşmesini ölçen AUPRO ile birlikte görülüyor. En belirgin AUPRO farkı PCB3'te; en belirgin AP farkları PCB1 ve PCB4'te.

Buradaki ölçümler 224×224'e merkez kırpılan görüntü alanındaki benchmark maskelerine aittir. Görüntüdeki kırpım dışında kalan alan puanlanmaz. Aynı 802 test görüntüsü keşif ve görüntü düzeyi deneylerinde daha önce incelenmişti; beş referans seçimi bağımsız test kümeleri değildir. Bu sonuçlar bağımsız üretim doğrulaması sayılmaz.

## Yeniden üretim

Protokol, seed başına ham ölçüler, ağırlık/manifest SHA-256 özetleri ve yazılım sürümleri `reports/visa-localization-v1.json` içinde saklanır. Çalıştırma 4 CPU iş parçacığıyla yaklaşık 1.136 saniye sürmüştür (PyTorch 2.10.0+cpu, torchvision 0.25.0+cpu, FAISS 1.15.1, NumPy 2.5.2, SciPy 1.18.1, Pillow 12.3.0). Depoda yeni test veya ayrı benchmark koşulmadı; bu komut deney çıktısını yeniden üretir:

```powershell
$env:PYTHONPATH='src'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='4'
$env:TQDM_DISABLE='1'
.\.venv\Scripts\python.exe -m pcb_anomaly.visa_localization
```

