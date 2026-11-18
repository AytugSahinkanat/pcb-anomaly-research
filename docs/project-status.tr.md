# Projenin durumu ve araştırma hedefi

12 Kasım 2026. Bu belge mevcut kanıtı, hedefi ve henüz gösterilmemiş iddiaları ayırır.

Makale hazırlık kararı: İngilizce taslak sürüyor. ResNet18/WideResNet50-2 yerelleştirme deneyleri ve AnomalyDINO–WideResNet50 PatchCore tam-pipeline karşılaştırması tamamlandı. Aynı 16 normal referans görüntüsüyle (4 PCB kategorisi × 5 seçim) DINO makro görüntü AUROC/AP'si %95,18/%95,85; piksel AUROC/AP'si %96,25/%53,76; AUPRO'su %88,56. PatchCore değerleri sırasıyla %91,92/%92,06, %98,01/%47,30 ve %82,92. DINO'nun özellik belleği 94,5–108,9 MiB, PatchCore'unki 4,90 MiB; dolayısıyla kaynak görüntü sayısı aynı olsa da bellek ve tam yöntem adımları eşit değil. Tek bir genel kazanan iddiası desteklenmiyor. Üstelik aynı VisA resmi test görüntüleri önceki deneylerde kullanıldı; seed yayılımı bağımsız kartlara genelleme belirsizliği değildir. [Eşlenmiş karşılaştırma](visa-16shot-comparison.tr.md). Siemens–NVIDIA'nın yeni kartta golden board beklemeden AOI hazırlama fikri olası sonraki yönümüz; mevcut verimiz dijital ikiz veya üretim false-call etiketleri içermiyor. [Araştırma önerisi](siemens-nvidia-research-direction.tr.md), [İngilizce makale taslağı](paper-draft.en.md) ve [makale hazırlığı](paper-readiness.tr.md).

RobustAD-PCB'de üç başlangıç yöntemi ve test4 yinelenen-kare duyarlılığı tamamlandı. Eşit yama belleği kullanan WideResNet50-2 / ResNet18 PatchCore hedef-alan makro görüntü AUROC'u %44,84 / %37,35 verdi. AnomalyDINO'nun farklı, yönelim-artırmalı tam hattı %43,52 görüntü AUROC, %7,55 piksel AP ve %64,07 AUPRO verdi; AUPRO iki PatchCore sonucundan yüksek, ancak belleği yaklaşık 80 MiB (PatchCore 4,90 MiB) ve yöntemin diğer adımları eşit değil. Üç yöntemde de hedef-alan görüntü AUROC'u %50'nin altında kaldı. Bu çekim koşulu hassasiyeti ve yerelleştirme/görüntü tespitinin ayrışması için başlangıç kanıtıdır; yöntem katkısı veya yeni kart tasarımı genellemesi değildir. Kaynak train/test0 çözünürlük-kusur ilişkisi ve eksik board ID sınırlamaları sürüyor. [Üç yöntem raporu](robustad-pcb-method-comparison.tr.md), [PatchCore ayrıntıları](robustad-pcb-patchcore.tr.md), [makine-okunur sonuçlar](../reports/robustad-pcb-method-comparison-v1.json).

18 Kasım kontrol deneyi: bütün kareleri tek eğitim-normal PCB şablonuna SIFT/RANSAC ile hizalayıp sabit kart ROI'si kullandık. Aynı beş referans seçimi ve PatchCore bellek ayarlarıyla kaymış-alan görüntü AUROC'u WideResNet50-2'de %44,84'ten %62,79'a, ResNet18'de %37,35'ten %51,87'ye çıktı; iki modelde piksel AP de yaklaşık 10–13 puan arttı. Görünüm hizalaması faydalı görünüyor; deney hizalama, kırpım, arka plan ve ölçek etkilerini ayrı ayrı ayırmıyor, ayrıca özellik bankası dışında bir normal şablon kullanıyor. Keşifseldir, bağımsız board-held-out doğrulama değildir. [Kontrol deneyi ve sınırlamaları](robustad-registered-board-experiment.tr.md).

Kusur türüne göre görüntü skoru alt analizi de iki PatchCore omurgasında tamamlandı: eksik komponentte ResNet18 daha iyi makro sıralama verirken, lehim erimesi ve çizikte WideResNet50-2 daha iyi AUROC verdi. Bu küçük, eşiksiz analiz DINO'yu kapsamıyor; onun sınıf bazlı sonucu ve örnek görüntülerin görsel hata incelemesi sırada. [Kusur türü raporu](robustad-pcb-defect-type-error-analysis.tr.md), [sonuç JSON'u](../reports/robustad-pcb-defect-type-image-ranking-v1.json).

Son güncelleme: [ortak ön işleme ve eşit yama belleği deneyi tamamlandı](visa-controlled.tr.md). İki omurga × iki ön işleme × iki bütçe × beş referans seçimi × dört kategori = 160 sonuç (140 yeni, 20 doğrulanarak yeniden kullanılan koşul). Aynı merkez kırpma ve 19,60 MiB yama belleğinde AUROC ResNet18'de %94,84, WideResNet50'de %95,73: eşlenmiş fark yalnızca 0,89 ± 0,28 puan. Küçük 1,96 MiB bankada fark 3,31 ± 1,13 puan. Önceki 8,24 puanlık farkın büyük kısmı omurga dışındaki ayarlara bağlıydı; etkiler etkileşiyor ve tek bir toplamsal neden payı yok. Büyük bankada kusur yakalama %78,90 / %82,10, yanlış alarm %6,57 / %7,16; eşit test yanlış alarmında bir karşılaştırma henüz yapılmadı. 48 birim test ve bütün deney doğrulamaları geçti. Toplam model RAM'i eşitlenmedi; aynı 802 test görüntüsü yeniden kullanıldı.

26 Ekim kaynak taramasında PCB-SAID ve PCB-IND adayları kaydedildi; ardından PCB-AoI'nin uygun resmi kart bölmesi bulundu ve ayrıca denetlendi.

30 Ekim kaynak güncellemesi: Ulger ve arkadaşlarının SMD lehim kırpımları SolDef_AI ROI deneyine en yakın dış veri adayı. Daha derin incelemede GitHub deposu 3.390 örnek bildirirken makale 4.052 örnek (3.292 normal + 760 kusurlu) bildiriyor. Makale ayrıca yalnızca 7 kaynak kart kullandığını ve örnekleri rastgele kırpım düzeyinde böldüğünü söylüyor; bu bölme yeni karta genelleme kanıtı değildir. Depoda kullanım lisansı ve kart eşleme tablosu doğrulanmadı. Bu yüzden aday henüz benchmarka alınmadı; önce sürüm farkı, kullanım hakkı ve her kırpımın kaynak karta bağlanması çözülmeli. [Kaynak ve görev sınırları](independent-data-review.tr.md).

Aynı incelemede 2023 tarihli LightJoint-D çalışmasının 93 PCB görüntüsünden 1.804 lehim ROI'si kullandığı, ancak veriyi yalnızca sorumlu yazardan isteyerek edinmenin mümkün olduğu görüldü. Daha fazla kaynak kart içerdiği için olası dış doğrulama adayıdır; fakat tam kart görüntüleri, ROI-kart eşlemesi ve kullanım koşulları doğrulanmadan bağımsız test sayılamaz. Bu çalışma için e-posta gönderilmedi. [Kaynak ve görev sınırları](independent-data-review.tr.md).

29 Ekim güncellemesi: PCB-AoI'nin Apache 2.0 lisanslı arşivi indirildi ve denetlendi; resmi 173 train / 60 test kart bölmesi korunarak, eğitim artırmaları hariç tutuldu. Testte yalnız kusurlu örnek bulunduğundan sabit ResNet18/HOG **kusur türü ROI sınıflandırması** yapıldı: ResNet18 %95,78 dengeli doğruluk ve %96,88 makro F1; HOG %63,00 / %65,59. Eşleştirilmiş kart-bootstrap farkı dengeli doğrulukta +32,96 puan (%95 aralık +18,94–+45,78). Sonuç nesne tespiti, yanlış alarm veya PatchCore değerlendirmesi değildir. [Denetim ve sonuç raporu](pcb-aoi-classifier.tr.md).

Aynı veride tam kutu tespit pilotu da tamamlandı: COCO başlangıçlı Faster R-CNN MobileNetV3-Large 320, eğitim içi doğrulamada 9. epoch'ta seçildi; resmi 60 test kartında mAP@0.5 %1,77 ve mAP@0.5:0.95 %0,38. Bu, verilen kutudan tür sınıflandırmasına göre çok daha zor olan konum bulma aşamasının mevcut kurulumda başarısız olduğunu gösteriyor. Normal test görüntüsü olmadığından yanlış alarm ölçülemedi; test tekrar model ayarı için kullanılmamalı. [Tam detector raporu](pcb-aoi-detector.tr.md).

29 Ekim devam denemesi: aynı 137/34 eğitim/doğrulama bölmesinde 640 px giriş ve küçük anchor kullanan Faster R-CNN'i yalnız eğitim içi doğrulamada denedik. En iyi mAP@0.5:0.95 %0,0523 oldu; 320 px başlangıç koşulunun %0,4104 değerinden düşük ve CPU süresi yaklaşık 1.200 saniye. Resmî test açılmadı. Bu keşif, söz konusu iki ayarın bu bölmede yarar göstermediğini ortaya koyuyor; yeni test sonucu değildir. [Rapor ve JSON](pcb-aoi-detector.tr.md).

Yeni [kalibrasyon eşiği ve hata incelemesi](visa-operating-points.tr.md) tamamlandı. %5 kalibrasyon hedefinde büyük bankalı ResNet18 ve küçük bankalı WideResNet50 testte %6,57 yanlış alarm ve yaklaşık %78 kusur yakalama veriyor. Büyük WRN %82,1 kusur yakalıyor, %7,16 yanlış alarm veriyor. İki büyük bankalı modelin 400 kusurdan 29 ortak kalıcı kaçırması var; küçük anotasyonlar ve PCB3 daha zor. Sonraki adım daha fazla normal kalibrasyon görüntüsü ve fiziksel kart/oturum bazında ayrılmış bağımsız test. Bu test kümesi eşik seçimi ya da yeni performans iddiası için kullanılmamalı.

SolDef_AI'da kart dışarıda bırakmalı ROI karşılaştırması tamamlandı: ResNet18 dengeli doğruluk konumda %57,4 ve lehimde %52,3; HOG %55,1 ve %42,8. Konum sınıfı hataları yöntemler arasında dengesi değişiyor; lehimde ResNet18 daha iyi. Bunlar anotasyonlu poligon sınıflandırmasıdır, tam görüntü kusur tespiti veya bağımsız son doğrulama değildir. [Yöntem, sınıflar ve hata görselleri](soldef-resnet18.tr.md).

Önceki [beş referans çalışması](visa-five-seeds.tr.md) ve [ilk tek-seed çalışma](visa-benchmark.tr.md) tarihsel başlangıç sonuçları olarak korunuyor.

[Kusur veri denetimi](defect-data.tr.md): VisA PCB1–PCB4 için 4.416 görüntü ve 400 kusur maskesi hazır; resmi test ayrımı korunarak normal eğitimden kalibrasyon ayrıldı, birebir RGB kopyası bulunmadı. SolDef_AI arşivinde 428 anotasyonlu görüntü ve 671 poligon doğrulandı. `CS1`–`CS6` PCB gruplarıyla konum için 6, lehim için 3 fold üzerinde ResNet18 ve HOG ilk kez karşılaştırıldı ([rapor](soldef-resnet18.tr.md)).

## Bugün elimizde ne var?

- 47 kaynak görüntü, 29 aday kart grubu, 31 kategori ve 8.016 komponent kırpması; dosya/örnek kimlikleri ve kaynak özetleri izlenebilir.
- 47 görüntü ve 141 kutu örneğinin görsel incelemesi; bütün kutuların uzman doğrulaması henüz yok. Fiziksel kart ve yerleşim ailesi ayrımı kesinleşmiş değil.
- Reference/calibration/test ayrımı; temsil geliştirmesinde test kullanılmıyor. Tek görüntüden çok sayıda komponent çıkması bağımsız kart sayısını artırmaz.
- Donmuş ResNet18, komşuluk görselleri, kontrollü yönelim/çözünürlük deneyi, dört yönelim ortalaması ve otomatik doğrulamalar.
- Dört yönelim ortalaması 90° katlarında değişmez; buna karşılık çözünürlük kararlılığı genel olarak iyileşmedi. Özgün sorgularda kategori uyumu %58,8→%56,3. Bu sonuçlar kusur doğruluğu değildir.

Yazılım altyapısı ve ilk VisA görüntü düzeyi benchmarkı bir araştırma başlangıç noktasıdır. Nicel kusur lokalizasyonu, üretim hattı performansı veya yayınlanabilir özgün yöntem henüz gösterilmedi. Kuo verisi komponent tespiti anotasyonları içerir; anotasyonlu bir parçayı otomatik olarak hatasız sayamayız. Var olan parçaları kırpmak eksik komponenti tespit etmek için yeterli değildir.

## Savunulabilir araştırma sorusu

17 Ekim ek deneyi: özgün/%50/%25 reference bankası, çeyrek boyuttaki sorguların kategori uyumunu %34,5→%51,1 artırdı. Ancak kategori içi top-5 örtüşmesi yalnızca %22,1→%23,6; yarı boyutta örtüşme geriledi. Bu nedenle [çok çözünürlüklü banka](scale-bank.tr.md) bir sonraki gerçek-kusur benchmarkına adaydır, doğrulanmış kusur çözümü değildir. Toplam 30 birim test geçti.

Önerilen soru: **Az referanslı PCB incelemesinde görüntü çözünürlüğü ve yönelim değişimi altında, hangi temsil ve referans seçimi yaklaşımı gerçek kusurları korurken yanlış alarmları azaltır?**

ResNet18 kullanımı tek başına sorun değil; anlaşılır bir başlangıç modeli sağlar. Yeni katkı yalnızca modeli değiştirmek, dört yönelim ortalaması almak veya bilinen referans artırma yöntemini uygulamak olamaz. Katkı, açık bir problem tanımı, iyi kontrol edilmiş değerlendirme ve yeni yöntemin bağımsız kusurlarda ölçülen faydasına dayanmalı. Bunlar sağlanmazsa çalışma, sınırları açık bir ampirik sağlamlık analizi olarak çerçevelenmeli.

Mevcut gözlemden çıkarılabilecek çalışma hipotezi: temsil değişmezliği, komşuluk kararlılığı ve kategori/kusur ayrımı aynı hedef değildir. Bunu genel sonuç olarak sunabilmek için modern temsiller ve bağımsız veriyle tekrar gerekir.

## Literatürle konumlandırma

[VisA'nın resmi deposu](https://github.com/amazon-science/spot-diff), dört PCB alt kümesi, normal/kusurlu görüntüler, kusur maskeleri ve resmi bölme dosyaları sağlıyor. Ana gerçek-kusur deneyini PCB1–PCB4 üzerinde kurabiliriz. Bu veri, mevcut Kuo komponent kırpmalarıyla aynı görev veya birebir eşleştirilebilir örnekler değildir; iki veri üzerindeki sonuçlar ayrı tablolanmalı.

[AnomalyDINO WACV 2025 makalesi](https://openaccess.thecvf.com/content/WACV2025/papers/Damm_AnomalyDINO_Boosting_Patch-Based_Few-Shot_Anomaly_Detection_with_DINOv2_WACV_2025_paper.pdf) ve [resmi kodu](https://github.com/dammsi/AnomalyDINO) dört kategorili VisA çalışmasında, aynı 16 normal referansla WideResNet50 PatchCore karşısında tam-pipeline kıyası olarak değerlendirildi. Aynı yaklaşım RobustAD-PCB'de de test edildi; orada piksel AP/AUPRO yüksek, görüntü sınıflandırması zayıf ve bellek bankası PatchCore'dan çok daha büyük. [RobustAD üç-yöntem raporu](robustad-pcb-method-comparison.tr.md), [VisA deney planı](anomalydino-baseline-plan.tr.md).

[Beyond Academic Benchmarks, CVPR Workshops 2025](https://arxiv.org/abs/2503.23451) gerçek üretim verileri, çözünürlük/dağılım değişimi ve pratik değerlendirme sorunlarını ele alıyor. Dolayısıyla “çözünürlük etkisini inceledik” tek başına yeni bir araştırma boşluğu iddiası değil; PCB'ye özgü problem, veri ve ölçülmüş katkı netleştirilmeli. Bu kaynak kontrolü sistematik literatür taraması değildir.

## Sonraki işler ve geçiş koşulları

| Aşama | Çıktı | Sonraki aşamaya geçiş koşulu |
|---|---|---|
| Mevcut temsil denemelerini kapat | Tek görünüm, dört yönelim ve çok çözünürlüklü reference karşılaştırması | Aynı sorgularla kayıtlı sonuçlar; fayda sağlamayan yöntemleri de raporlama |
| Gerçek kusur benchmarkı | VisA sonuçları tamam; RobustAD’da üç yöntem, beş ortak seçim ve kopya anotasyon duyarlılığı raporlandı | Alan/kusur türü hata analizi ve test alanlarına dokunmadan kaynak-normal kalibrasyon protokolü hazırla; sonra yöntem katkısı için bağımsız kart verisi edin |
| Modern karşılaştırmalar | VisA'da ve RobustAD-PCB'de AnomalyDINO/WideResNet50 PatchCore tam-pipeline sonuçları; RobustAD'da eşit-bellek ResNet18/WRN50 kıyası | Sonuçları sabitle; yeni model/parametre seçimini testlere göre yapma; bağımsız kart/oturum verisi edin |
| Hedefe yönelik yöntem | Örneğin çözünürlük bilgili reference seçimi veya yerel/mekânsal bağlam | Sabit yanlış alarm düzeyinde kusur duyarlılığında fayda; ablation ve maliyet ölçümü |
| Makale ve yeniden üretim | Ana tablolar, belirsizlik aralıkları, yöntem ayrıntıları, erişilebilir kod | Bağımsız son test; veri erişim/lisans ve kaynak gösterimi; iddiaların sonuçlarla sınırlandırılması |

Önerilen ölçümler: görüntü AUROC/AP, eşik calibration'da seçilerek testte gerçekleşen yanlış alarm ve duyarlılık; maskeli görevde piksel AP/AUPRO; görüntü başına süre, model/reference bellek maliyeti. Hedef yanlış alarm seviyesi ayrıca önceden belirlenmeli. Reference örnek bütçesi ve seed listesi deney başlamadan sabitlenmeli. Mevcut beş calibration kartıyla güvenilir üretim genellemesi iddia edilmemeli; kart/ürün bazlı belirsizlik değerlendirmesi planlanmalı.

## Proje nereye gelebilir?

**Mevcut kanıtla:** iyi belgelenmiş bitirme projesi, yeniden üretilebilir kod ve bir sağlamlık ön çalışması. Henüz güçlü bir kusur tespit makalesi değil.

**Bağımsız kusur verisi ve modern karşılaştırmalar eklenirse:** uygulamalı bir araştırma makalesi veya uygun bir workshop çalışması hedeflenebilir. Hedef yayın seviyesi ve kabul, katkının yeniliğine, bulguların gücüne ve değerlendirmeye bağlıdır; garanti edilemez.

**Ek özgün yöntem ve farklı veri/koşullarda tutarlı kazanç gösterilirse:** daha güçlü bir yöntem makalesi düşünülebilir. Negatif deneyler burada yöntemin sınırlarını ve seçilme nedenini destekler; tek başına yenilik kanıtı olmaz.

**Ürün tarafında:** ilk gerçekçi çıktı, operatöre şüpheli bölgeleri ve benzer referansları sunan bir karar destek prototipi. Otomatik üretim kabul/red sistemi için görüntü yakalama, kart hizalama, beklenen komponent yerleşimi, gerçek hatalar, eşik kararlılığı, süre ve saha doğrulaması gerekir. Bunların önemli kısmı mevcut kapsamın dışında.

## Makale iskeleti

1. Problem: düşük maliyetli/değişken görüntü koşullarında PCB incelemesi; görev ve kapsam.
2. İlgili çalışmalar: komponent tespiti, referans/yama tabanlı anomali, sağlamlık ve değerlendirme.
3. Veri ve protokol: görevleri ayrı tanımlama, kart ayrımı, calibration, etiket kaynağı.
4. Ön analiz: mevcut yönelim ve çözünürlük bulguları.
5. Yöntem/karşılaştırmalar: açık hipotezler ve ablation.
6. Gerçek kusur sonuçları: ana katkının sınandığı bölüm; şu an eksik.
7. Maliyet, sınırlamalar ve sonuç.

Öncelik, mevcut veri üstünde sınırsız küçük denemeler yapmak yerine temsil aşamasını kapatıp gerçek kusur değerlendirmesine geçmektir.

Ayrıntılı eşik tablosu ve görsel hata galerisi: [kalibrasyon işletim noktaları](visa-operating-points.tr.md).
