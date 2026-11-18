# RobustAD-PCB: ortak kart görünümüne hizalama deneyi

**Durum: Tamamlandı — 18 Kasım 2026**

## Soru

Tam PCB karesindeki konum, ölçek ve arka plan değişimleri düşük görüntü düzeyi AUROC'un önemli bir kısmını açıklıyor mu? Aynı PatchCore omurgalarını aynı test karelerinde, aynı beş 16-referans seçimiyle çalıştırıp yalnızca tam-kare ön işlemesini sabit kart görünümüne hizalama ile değiştirdik.

## Değiştirilen ve sabit tutulanlar

**Tam-kare başlangıç:** bütün kareyi doğrudan 224×224'e indir.

**Hizalı koşul:** kareleri önce 640×640'e indir; sonra her görüntüyü, yalnız eğitim normalinden seçilen tek bir şablona SIFT eşleşmeleri ve RANSAC homografisiyle kaydet. Şablondaki sabit kart ROI'sini al, en-boy oranını koruyarak ImageNet ortalama rengiyle kareye tamamla ve 224×224'e indir. Test görüntülerinin kusur maskeleri aynı homografiyle taşındı. Dört target koşulundan örnek hizalı kırpımlar görsel olarak kontrol edildi.

Hizalama ayarları sonuçlara bakarak değiştirilmedi: SIFT en fazla 4.000 özellik, Lowe oranı 0,75, RANSAC hata sınırı 4 piksel; minimum 50 iç eşleşme, eşleşmelerin en az %25'i iç eşleşme ve ROI örtüşmesi en az %95. Kart ROI'si şablonun HSV `[90,50,40]`–`[130,255,255]` aralığındaki en büyük bileşeninden çıkarıldı ve her kenara %3 bağlam eklendi. Kalite kapısından **1.184/1.184 görüntü** geçti; en düşük iç eşleşme 73, en düşük ROI örtüşmesi %100 oldu.

Özellik omurgaları, PatchCore katmanları ve puanlama değişmedi. Aynı normal referans listeleri (seed 42–46), her seed'de 16 kusur belleği görüntüsü, %10 coreset, Euclidean 1-NN, en yüksek yama puanı ve 4,90 MiB bellek kullanıldı. Eşik seçilmedi. `test4` yinelenen karesi başlangıç deneyindeki gibi bir kere sayıldı ve iki maske birleştirildi.

**Ek kaynak açıkça belirtilmeli:** SIFT hizalaması için `train/normal/Train_PCB_resized_None_None_Normal_Set1_1.jpg` adlı bir eğitim normal görüntüsü sabit geometrik şablon olarak kullanıldı. Bu kare hiçbir seed'in 16 örneklik özellik bankasında yoktur; kusur puanlamasına girmez, ancak hizalı yöntem bir ek eğitim-normal görünümünden yararlanır. Yani yama belleği eşit, toplam referans görseli sayısı tam eşit değildir.

## Ana sonuç

Kaymış alanlar `test1`–`test5` üzerinde eşit ağırlıklı makro. Metrikler yüzde; `±` aynı beş test kümesini kullanan beş referans seçiminin eşlenmiş farkındaki örnek standart sapmadır, güven aralığı değildir.

| Omurga | Ölçüt | Tam kare | Hizalı kart | Değişim |
|---|---|---:|---:|---:|
| WideResNet50-2 | Görüntü AUROC | 44,84 | 62,79 | **+17,95 ± 5,74 puan** |
| WideResNet50-2 | Görüntü AP | 43,17 | 56,31 | **+13,14 ± 2,51 puan** |
| WideResNet50-2 | Piksel AUROC | 87,16 | 89,75 | +2,59 ± 0,77 puan |
| WideResNet50-2 | Piksel AP | 5,42 | 18,14 | **+12,72 ± 0,73 puan** |
| WideResNet50-2 | AUPRO | 48,84 | 55,82 | +6,98 ± 1,74 puan |
| ResNet18 | Görüntü AUROC | 37,35 | 51,87 | **+14,52 ± 3,55 puan** |
| ResNet18 | Görüntü AP | 40,60 | 48,55 | +7,95 ± 3,73 puan |
| ResNet18 | Piksel AUROC | 85,71 | 88,98 | +3,27 ± 0,87 puan |
| ResNet18 | Piksel AP | 5,71 | 15,62 | **+9,90 ± 1,26 puan** |
| ResNet18 | AUPRO | 41,57 | 47,89 | +6,33 ± 2,35 puan |

### Alan bazında görüntü AUROC

| Çekim koşulu | WideResNet50-2 tam → hizalı | ResNet18 tam → hizalı |
|---|---:|---:|
| Aydınlatma | 40,1 → **63,2** | 27,8 → **58,7** |
| Beyaz dengesi | 53,6 → **69,4** | 27,6 → **48,2** |
| Dönüş | 39,4 → **62,0** | 35,9 → **46,4** |
| Konum | 43,1 → **57,2** | 30,0 → **43,9** |
| Gölge / arka plan | 47,9 → **62,2** | 65,5 → 62,2 |

Hizalama iki omurganın hedef alan makro sonuçlarını yükseltti. En büyük ve tutarlı kazanımlar görüntü düzeyi AUROC/AP ile piksel AP'de. ResNet18 için gölge/arka plan alanı tek istisna: AUROC %65,5'ten %62,2'ye indi; yine de bu alan güçlü kaldı. Hizalamadan sonra WideResNet50 bütün beş alanı %50 AUROC üstünde sıralarken ResNet18 beyaz dengesi, dönüş ve konumda %50'nin altında kaldı.

## Ne anlama geliyor?

Sonuç, düşük eski skorların **önemli bir bölümünün tam-kare görünüm/konum/ölçek değişimine duyarlı olmasından kaynaklanabileceği** hipotezini destekliyor. Tek başına “görüntü çözünürlüğü sebep” demiyor: bu müdahale homografi hizalaması, sabit ROI kırpımı, arka planı çıkarma ve göreli ölçek normalizasyonunu birlikte değiştirdi. Bu bileşenlerin katkısı ayrı ablation ile ölçülmedi.

Önceki kaynak bölümdeki çözünürlük–etiket çakışması da sürüyor: train ve test0'da normals 2560×2560, anomalies 2048×2048. Kaymış test1–test5'te bütün kareler 2048×2048. Hizalama karşılaştırması hedef alan performansını iyileştirse de fiziksel kart/oturum ID'si bulunmadığı için yeni kart genellemesini kanıtlamıyor.

Bu deney **keşifsel/teşhis amaçlıdır**. Tam koşudan önce her hedef alandan metadata etiketiyle bir kusurlu örnek seçilip hizalamanın görsel fizibilitesi incelendi; bu kareler maske veya performans metriğiyle parametre ayarı için kullanılmadı. Yine de test görüntüleri görülmüş olduğundan bu, hiç dokunulmamış doğrulama değildir. Mevcut benchmark da aynı görüntülerde tekrarlandı; sonucu bağımsız ve hiç görülmemiş test başarısı gibi sunmamalıyız.

## Devam planı

1. Yanlış alarmlar ve kaçırılmış kusurlar için hizalı/tam-kare görsel galerisi oluştur; özellikle ResNet18'in beyaz dengesi, dönüş ve konum alanlarını incele.
2. Geometrik şablonun ek kaynak etkisini raporla; mümkünse aynı toplam normal-görüntü bütçesinde şablonlu/şablonsuz ablation yap.
3. Hizalama, ROI crop ve arka plan çıkarımını ayrı ayrı ablation et. Yeni kart/oturum verisi gelene kadar test setini yöntem seçimi için tekrar tekrar kullanma.
4. AnomalyDINO'yu aynı hizalı ROI üzerinde çalıştırmak istenirse bunu ayrı bir tam-pipeline uzantısı olarak etiketle; mevcut PatchCore bulgusuyla karıştırma.

Kod: [`robustad_registration.py`](../src/pcb_anomaly/robustad_registration.py), [`robustad_patchcore.py`](../src/pcb_anomaly/robustad_patchcore.py). Tüm seed/alan sayıları: [`robustad-pcb-registered-board-comparison-v1.json`](../reports/robustad-pcb-registered-board-comparison-v1.json).
