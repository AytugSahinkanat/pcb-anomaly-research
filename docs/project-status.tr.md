# Projenin durumu ve araştırma hedefi

25 Ekim 2026. Bu belge mevcut kanıtı, hedefi ve henüz gösterilmemiş iddiaları ayırır.

Son güncelleme: [ortak ön işleme ve eşit yama belleği deneyi tamamlandı](visa-controlled.tr.md). İki omurga × iki ön işleme × iki bütçe × beş referans seçimi × dört kategori = 160 sonuç (140 yeni, 20 doğrulanarak yeniden kullanılan koşul). Aynı merkez kırpma ve 19,60 MiB yama belleğinde AUROC ResNet18'de %94,84, WideResNet50'de %95,73: eşlenmiş fark yalnızca 0,89 ± 0,28 puan. Küçük 1,96 MiB bankada fark 3,31 ± 1,13 puan. Önceki 8,24 puanlık farkın büyük kısmı omurga dışındaki ayarlara bağlıydı; etkiler etkileşiyor ve tek bir toplamsal neden payı yok. Büyük bankada kusur yakalama %78,90 / %82,10, yanlış alarm %6,57 / %7,16; eşit test yanlış alarmında bir karşılaştırma henüz yapılmadı. 48 birim test ve bütün deney doğrulamaları geçti. Toplam model RAM'i eşitlenmedi; aynı 802 test görüntüsü yeniden kullanıldı.

Yeni [kalibrasyon eşiği ve hata incelemesi](visa-operating-points.tr.md) tamamlandı. %5 kalibrasyon hedefinde büyük bankalı ResNet18 ve küçük bankalı WideResNet50 testte %6,57 yanlış alarm ve yaklaşık %78 kusur yakalama veriyor. Büyük WRN %82,1 kusur yakalıyor, %7,16 yanlış alarm veriyor. İki büyük bankalı modelin 400 kusurdan 29 ortak kalıcı kaçırması var; küçük anotasyonlar ve PCB3 daha zor. Sonraki adım daha fazla normal kalibrasyon görüntüsü ve fiziksel kart/oturum bazında ayrılmış bağımsız test. Bu test kümesi eşik seçimi ya da yeni performans iddiası için kullanılmamalı.

SolDef_AI'da bu planı kullanan ilk donmuş ResNet18 ROI sınıflandırması da tamamlandı: kart dışarıda bırakmalı OOF dengeli doğruluk konumda %57,4, lehimde %52,3; eğitim çoğunluk sınıfı kontrolü %42,6 / %17,9. Bunlar anotasyonlu poligon sınıflandırmasıdır; tam görüntü kusur tespiti veya bağımsız son doğrulama değildir. [Yöntem ve fold ayrıntıları](soldef-resnet18.tr.md).

Önceki [beş referans çalışması](visa-five-seeds.tr.md) ve [ilk tek-seed çalışma](visa-benchmark.tr.md) tarihsel başlangıç sonuçları olarak korunuyor.

[Kusur veri denetimi](defect-data.tr.md): VisA PCB1–PCB4 için 4.416 görüntü ve 400 kusur maskesi hazır; resmi test ayrımı korunarak normal eğitimden kalibrasyon ayrıldı, birebir RGB kopyası bulunmadı. SolDef_AI arşivinde 428 anotasyonlu görüntü ve 671 poligon doğrulandı. `CS1`–`CS6` PCB gruplarıyla konum için 6, lehim için 3 fold hazır; ilk ResNet18 sonuçları [kart ayrımlı baseline raporunda](soldef-resnet18.tr.md).

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

[AnomalyDINO'nun resmi deposu](https://github.com/OJ2001/AnomalyDINO) yöntemin WACV 2025 kabulünü belirtiyor; DINOv2 yama özellikleriyle eğitim gerektirmeyen az örnekli anomali yaklaşımı modern karşılaştırma adayıdır. Önceki araştırma notundaki yalnızca “2024 ön baskı” tanımı bu açıdan güncel değildir. PatchCore yama hafızası ve donmuş ResNet18 başlangıç modeliyle birlikte kontrollü karşılaştırma yapılmalı.

[Beyond Academic Benchmarks, CVPR Workshops 2025](https://arxiv.org/abs/2503.23451) gerçek üretim verileri, çözünürlük/dağılım değişimi ve pratik değerlendirme sorunlarını ele alıyor. Dolayısıyla “çözünürlük etkisini inceledik” tek başına yeni bir araştırma boşluğu iddiası değil; PCB'ye özgü problem, veri ve ölçülmüş katkı netleştirilmeli. Bu kaynak kontrolü sistematik literatür taraması değildir.

## Sonraki işler ve geçiş koşulları

| Aşama | Çıktı | Sonraki aşamaya geçiş koşulu |
|---|---|---|
| Mevcut temsil denemelerini kapat | Tek görünüm, dört yönelim ve çok çözünürlüklü reference karşılaştırması | Aynı sorgularla kayıtlı sonuçlar; fayda sağlamayan yöntemleri de raporlama |
| Gerçek kusur benchmarkı | VisA PCB1–PCB4; resmi test ayrımı; normal eğitimden ayrılan calibration | Teste bakılarak model/parametre seçilmemesi; veri ve maskelerin doğrulanması |
| Modern karşılaştırmalar | ResNet18, PatchCore, AnomalyDINO; aynı örnek bütçesi ve girdi boyutu | Birden fazla reference seçimi/tohum; kategori ve veri bazında ayrı sonuç |
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
