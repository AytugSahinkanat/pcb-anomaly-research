# DINOv2 / AnomalyDINO karşılaştırma planı

**Durum:** AnomalyDINO benchmarkı ve aynı 16 referanslı WideResNet50 PatchCore karşılaştırması tamamlandı; her yöntem için 4 kategori × 5 seçim. Ayrıntılı sonuçlar [`visa-16shot-comparison.tr.md`](visa-16shot-comparison.tr.md) içinde.  
**İncelenen resmi kod sürümü:** [`dammsi/AnomalyDINO`, `b9d1c2648e3a5247437d4d953d907a8f3d994457`](https://github.com/dammsi/AnomalyDINO/tree/b9d1c2648e3a5247437d4d953d907a8f3d994457)
**DINOv2 sürümü:** [`facebookresearch/dinov2`, `7764ea0f912e53c92e82eb78a2a1631e92725fc8`](https://github.com/facebookresearch/dinov2/tree/7764ea0f912e53c92e82eb78a2a1631e92725fc8)

## Yöntem PatchCore'dan nasıl ayrılıyor?

AnomalyDINO, DINOv2 ViT-S/14 yama özellikleriyle bir nearest-neighbor bellek yaklaşımıdır. Yöntem kosinüs uzaklığı kullanır; görüntü puanı en yüksek uzaklığa sahip yamaların ilk %1'inin ortalamasıdır. Resmi varsayılan “agnostic” ayar, uygun gördüğü VisA nesnelerinde PCA tabanlı maske çıkarır ve normal referansları 90° dönüşlerle artırır. Makale 448 ve 672 kısa kenar çözünürlüklerini, 1/2/4/8/16 referans örneği ve görüntü/piksel AUROC, F1-max, AP/PRO ölçülerini raporlar. Piksel dengesizliği nedeniyle tek başına segmentasyon AUROC'a güvenmemeyi özellikle belirtir. Kaynak: [WACV 2025 makalesi](https://openaccess.thecvf.com/content/WACV2025/papers/Damm_AnomalyDINO_Boosting_Patch-Based_Few-Shot_Anomaly_Detection_with_DINOv2_WACV_2025_paper.pdf) ve [resmi uygulama](https://github.com/dammsi/AnomalyDINO).

Bu nedenle AnomalyDINO, yalnızca PatchCore'daki ResNet omurgasını değiştirerek elde edilen eşdeğer bir faktöriyel koşul değildir. Girdi çözünürlüğü, yama özellikleri, referans artırması, maskeleme ve görüntü puanı da farklıdır. Sonuçlar **modern tam-pipeline kıyası** olarak raporlanmalı; bu tablodan DINOv2 omurgasının tek başına nedensel katkısı çıkarılmamalı.

## Sabitlenecek deney tasarımı

1. Yalnız PCB1–PCB4 ve resmi test görüntüleri; önceki PatchCore yerelleştirmesiyle aynı 802 test görüntüsü ve aynı maskeler. Kategori dağılımı: 200/200/201/201.
2. Önceden kaydedilmiş beş referans listesinin her birinden 16 görüntü kullan. 16, makaledeki raporlanmış en büyük shot sayısıdır. Seçim sırası mevcut 64'lü listenin ilk 16'sı olarak sabitlenir; yeni seçim test sonucuna göre yapılmaz.
3. Resmi AnomalyDINO-S/14, 448 çözünürlük, agnostic ön işleme, referanslarda 0°, 45°, 90°, 135°, 180°, 225°, 270° ve 315° dönüş artırması, kosinüs 1-NN ve üst %1 yama ortalaması. PatchCore ile test edilen görüntü alanını eşitlemek için aynı `Resize(256)+CenterCrop(224)` alanını 448×448'e büyüten uyarlama ayrıca kayda geçirilmeli; bu, makaledeki kısa kenar 448 varsayılanıyla aynı değildir.
4. Segmentasyon maskesi/maps ve metrikler için aynı resmi test listesi; piksel AUROC/AP ve AUPRO (FPR≤0,30). AnomalyDINO'nun haritası 32×32 yama ızgarasından resmi bilineer ölçekleme ve sigma=4 yumuşatma ile çıkarılır.
5. Aynı ilk 16 referans görüntüsüyle WideResNet50 PatchCore koşusu tamamlandı. AnomalyDINO bankası kategori/seed'e göre 94,5–108,9 MiB; PatchCore 4,90 MiB kullandı. Yöntemler eşit kaynak görüntüsü sayısında karşılaştırıldı; bellek, maske ve skor farklılıkları nedeniyle bu, omurga ablationı değil tam-pipeline kıyasıdır.
6. Sonuçlar mevcut VisA test setinde keşifsel kıyas olarak işaretlenir. Beş seçim aynı test görüntülerini tekrarlar; beş bağımsız test değildir. Testte yeni parametre seçilmez.

## Tam benchmark sonucu

Makro (PCB1–PCB4 eşit ağırlık) görüntü AUROC/AP %95,18/%95,85; piksel AUROC/AP %96,25/%53,76; AUPRO(FPR≤0,30) %88,56. Düşük piksel AP, özellikle PCB2 (%37,38) ve PCB4'te (%38,20), yüksek AUROC'un tek başına kusur yerelleştirmesini göstermediğini ortaya koyuyor. Beş referans seçimi aynı test görüntülerini kullanır; seed standart sapması yeni kartlarda belirsizlik değildir.

Tam kategori tablosu ve yorum: [eşlenmiş 16-shot sonuç raporu](visa-16shot-comparison.tr.md); AnomalyDINO'nun 20 seed-kategori kaydı: [JSON](../reports/visa-anomalydino-v1.json); PatchCore kayıtları: [JSON](../reports/visa-patchcore-16shot-v1.json).

## Bu makinedeki durum

- Makine CPU-only; `torch.cuda.is_available()` false. Resmî AnomalyDINO çalıştırıcısı GPU'yu varsayılan kabul ediyor ve CPU FAISS seçeneğine rağmen `torch.cuda.synchronize()` çağırıyor; kendi CPU uyarlama betiği gerekli.
- Proje `.venv` ortamında NumPy 1.26.4, scikit-learn 1.6.1, OpenCV 4.11.0 ve SciPy 1.17.1 kuruldu. Mevcut grafik bağımlılığıyla çakışmayı önlemek için contourpy 1.3.2'ye sabitlendi.
- DINOv2 kodu ve 84,2 MB ViT-S/14 ağırlığı `data/torch-cache` içinde. CPU runner, öznitelik önbelleği ve küçük parçalara bölünmüş FAISS sorgusu ile 20 koşuyu tamamladı.

Bu sonuçlar üretim iddiası oluşturmaz. Bir sonraki bilimsel darboğaz, önceden incelenmemiş ve PCB/oturum bazında ayrılmış dış test verisidir; yeni yöntem veya eşik kararı bu VisA testine göre seçilmemelidir.
