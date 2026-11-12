# AnomalyDINO / DINOv2 – VisA PCB sonuçları

**Deney durumu:** Tamamlandı (9 Kasım 2026)  
**Kapsam:** PCB1–PCB4; beş önceden belirlenmiş referans seçimi (seed 42–46); her seçimden 16 normal görüntü; aynı 802 resmi test görüntüsü.  
**Çalıştırıcı:** [`anomalydino_localization.py`](../src/pcb_anomaly/anomalydino_localization.py)  
**Makinece okunabilir sonuçlar:** [`visa-anomalydino-v1.json`](../reports/visa-anomalydino-v1.json)

## Araştırma amacı ve yorum sınırı

Bu deney, DINOv2 ViT-S/14 yamalarını kullanan AnomalyDINO tam yöntemini, VisA'nın PCB kusurlarında ölçer. PatchCore ile yalnızca aynı sayıda normal referans görüntüsü kullanılmıştır. Yöntemlerin yama temsili, döndürme artırması, bellek büyüklüğü, maskelemesi ve görüntü skoru farklıdır; dolayısıyla bu deney omurga etkisini tek başına ayırmaz. Aşağıdaki PatchCore 64-shot sonuçları bağlam içindir, adil bire bir karşılaştırma değildir.

VisA test kümesi önceki analizlerde de kullanıldı. Beş referans seçimi aynı test görüntülerini tekrar kullanır; standart sapmalar yeni kartlar üzerindeki belirsizlik aralığı değildir. Test sonuçları yalnızca sabit benchmarkın keşifsel/betimsel ölçümü olarak sunulmalıdır.

## Sabit yöntem

- Resmî AnomalyDINO kod commit'i [`b9d1c2648e3a5247437d4d953d907a8f3d994457`](https://github.com/dammsi/AnomalyDINO/tree/b9d1c2648e3a5247437d4d953d907a8f3d994457); DINOv2 kaynak commit'i [`7764ea0f912e53c92e82eb78a2a1631e92725fc8`](https://github.com/facebookresearch/dinov2/tree/7764ea0f912e53c92e82eb78a2a1631e92725fc8); ViT-S/14 ön-eğitim ağırlıkları.
- Aynı görüntü alanı için RGB ve kusur maskeleri önce `Resize(256)+CenterCrop(224)` ile işlenir; RGB sonra 448×448'e büyütülür ve 14 piksellik yama ızgarasına bölünür. Bu, AnomalyDINO makalesindeki kısa kenarı 448'e büyütme varsayılanından farklı, karşılaştırma amacıyla yapılmış bir uyarlamadır.
- Beş sabit referans listesinin ilk 16 görüntüsü kullanılır. Her referans 0°, 45°, 90°, 135°, 180°, 225°, 270° ve 315° döndürülerek özellik belleğine eklenir.
- AnomalyDINO'nun PCA tabanlı ön plan maskesi ve 1-NN kosinüs uzaklığı korunur. Görüntü skoru en yüksek uzaklığa sahip yamaların %1 ortalamasıdır. Kusur haritası 32×32'den 448'e büyütülür, sigma=4 ile yumuşatılır ve ortak değerlendirme alanı olan 224×224'e indirilir.
- Metrikler: görüntü AUROC/AP; piksel AUROC/AP; FPR≤0,30 için AUPRO. Eşik seçimi yoktur. Her kategori/seed ayrı hesaplanıp raporlanır.

## Sonuçlar

Değerler yüzde olarak ortalama ± seed örnek standart sapmasıdır. Dört kategori makrosunda kategoriler eşit ağırlıklıdır.

| PCB grubu | Görüntü AUROC | Görüntü AP | Piksel AUROC | Piksel AP | AUPRO (FPR≤0,30) |
|---|---:|---:|---:|---:|---:|
| PCB1 | 91,89 ± 0,45 | 93,21 ± 0,27 | 96,47 ± 0,01 | 84,59 ± 0,56 | 87,23 ± 0,18 |
| PCB2 | 93,28 ± 0,62 | 94,39 ± 0,50 | 93,33 ± 0,01 | 37,38 ± 0,56 | 86,92 ± 0,28 |
| PCB3 | 96,34 ± 0,90 | 96,69 ± 0,74 | 98,80 ± 0,03 | 54,90 ± 0,47 | 92,40 ± 0,25 |
| PCB4 | 99,23 ± 0,39 | 99,09 ± 0,51 | 96,42 ± 0,12 | 38,20 ± 1,82 | 87,69 ± 0,85 |
| **Makro ortalama** | **95,18 ± 0,17** | **95,85 ± 0,18** | **96,25 ± 0,03** | **53,76 ± 0,59** | **88,56 ± 0,23** |

Piksel AUROC genel olarak yüksek görünse de PCB2 ve PCB4 piksel AP değerleri yaklaşık %37–38'dir. Bu dengesiz kusur piksellerinde AUROC tek başına yeterli değildir. Yüksek görüntü sıralama başarısı, kusur sınırlarının her pikselde doğru bulunması anlamına gelmez.

### PatchCore sonuçlarıyla bağlam

Mevcut eşit 19,598 MiB bellekli WideResNet50-2 PatchCore çalışmasında piksel makro AUROC/AP/AUPRO sırasıyla %98,52/%49,52/%86,62'dir. AnomalyDINO'nun gözlenen değerleri %96,25/%53,76/%88,56'dır. Ancak bu PatchCore çalışması kategori başına 64 normal referans ve 5.017 yama kullanırken AnomalyDINO 16 kaynak görüntünün sekiz yönelimini kullanmış, kategoriye göre yaklaşık 94,5–108,9 MiB özellik belleği oluşturmuştur. Bu nedenle bu sayılardan kazanan veya yöntemin üstünlüğü çıkarılamaz.

Standart WideResNet50 PatchCore aynı ilk 16 referans görüntüsüyle ayrıca çalıştırıldı. Eşit referans sayısında karşılaştırma AnomalyDINO lehine görüntü AP, piksel AP ve AUPRO; PatchCore lehine piksel AUROC ve daha küçük bellek gösteriyor. Ayrıntılı, eşlenmiş tablo [16-shot karşılaştırma raporunda](visa-16shot-comparison.tr.md). Daha güçlü genelleme iddiası için daha önce incelenmemiş, kart/oturum düzeyinde bağımsız test verisi gerekir.

## Yeniden üretim bilgisi

- Test sayıları: PCB1 200, PCB2 200, PCB3 201, PCB4 201; toplam 802.
- Model ağırlığı SHA-256: `b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9`.
- Ortam: CPU, PyTorch 2.10.0+cpu, torchvision 0.25.0+cpu, faiss-cpu 1.15.1, NumPy 1.26.4, SciPy 1.17.1, scikit-learn 1.6.1.
- Ağırlık ve VisA görüntüleri git deposuna eklenmez. Komut: `python -m pcb_anomaly.anomalydino_localization`.
