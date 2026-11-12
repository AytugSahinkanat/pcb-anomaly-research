# Siemens–NVIDIA PCB inspection yaklaşımı ve bizim araştırma yönümüz

**Güncelleme:** 6 Kasım 2026  
**İncelenen yazı:** [The Factory Problems AI Is Learning to Solve](https://www.linkedin.com/pulse/factory-problems-ai-learning-solve-siemens-8ue6e/)

## Yazı ne söylüyor?

Yazı Siemens Electronics Factory Erlangen'deki yüksek ürün çeşitliliği ve sık değişen üretim ortamından dört örnek veriyor: dijital ikizi güncel tutmak, fiziksel örnek kart olmadan AOI hazırlamak, üretim planını hızla değiştirmek ve değişken nesneleri robotla tutmak. Bizim projemiz yalnızca **PCB kalite denetimi/AOI** kısmına doğrudan temas ediyor.

Yeni kart geldiğinde klasik süreç, ilk gerçek “golden board” üretimini bekleyip AOI programını ve referanslarını sonra hazırlamak. Siemens–NVIDIA akışı PCB tasarımı, BOM ve komponent bilgisini Teamcenter/Process Preparation X ile ürün ve üretim dijital ikizine taşıyor; NVIDIA Cosmos ve Cosmos Data Factory ile sanal iyi/kusurlu görüntüler oluşturup ilk fiziksel kart gelmeden denetimi hazırlamayı hedefliyor. Ardından AOI'nin şüpheli bulguları için ikinci aşama inceleme gerçek kusur ile yanlış alarmı ayırmaya yardım ediyor. Siemens, Process Preparation X’in kart dijital ikizi oluşturduğunu ve sanal altın kart/sentetik örneklerin üretim öncesi hazırlıkta kullanılacağını açıklıyor. [Siemens duyurusu](https://news.siemens.com/en-us/siemens-nvidia-pcba-digital-twin-factory/)

Rakamları dikkatle ayırmak gerekir: Siemens’in 21 Ekim duyurusu **%85'e kadar daha az manuel mühendislik işi, %40'tan fazla daha az false call ve %5'ten fazla first-pass-yield artışını proje hedefi** olarak veriyor. NVIDIA’nın aynı dönem yazısı Erlangen’de denetim kalibrasyonu için **%40 süre azalması** bildiriyor. Bunlar şirket açıklamalarıdır; bağımsız akademik doğrulama veya bizim projemizin sonucu değiller. [NVIDIA yazısı](https://blogs.nvidia.com/blog/europe-industrial-leaders-engineering-manufacturing/)

## Bizim yaptıklarımızla kesişim

| Fabrika ihtiyacı | Bizdeki yakın çalışma | Aradaki boşluk |
|---|---|---|
| İlk fiziksel kart gelmeden denetime hazırlanma | VisA'da 64 normal referanslı PatchCore ve DINOv2 tabanı hazırlığı; benzer normal görüntülerden sapma puanı ve haritası | PCB CAD/Gerber/BOM/yerleşim ikizimiz ve henüz üretilmemiş tasarım yok; bugünkü VisA kartları mevcut fiziksel örnekler |
| Gerçek kusuru yanlış alarmdan ayırma | VisA gerçek maske verisinde piksel haritaları; eşik kalibrasyonu; kategori bazlı görüntü ve piksel metrikleri | Siemens’in THT lehim AOI aday bulguları için “gerçek hata/false call” etiketi bizde yok. VisA genel PCB görüntüsü aynı karar görevi değil |
| Kart/ürün değişiminde hızlı uyum | Yönelim ve çözünürlük etkisi, çoklu referans seçimi ve yama belleği analizleri | Aynı test görüntüleri tekrar kullanıldı; fiziksel kart/ürün ailesi bazında bağımsız, görülmemiş varyant testi yok |
| Sentetik veriyle kusur çeşitliliğini artırma | Gerçek kusur maskeli VisA ve komponent kutuları, sentetik/maske deneyleri için başlangıç malzemesi | Kuo kutuları komponent etiketidir, kusur maskesi değildir. Gerçek PCB tasarımından renderer'a giden dijital ikiz veya sentetik-gerçek eşlemesi yok |

NVIDIA’nın Cosmos Data Factory sayfası sentetik PCB kusur görüntüsü üretimini yeni yeteneklerden biri olarak tanımlıyor; NVIDIA Omniverse Replicator ise sahne/ışık/poz değişimlerini ve etiket üretimini sağlayan daha genel bir simülasyon çerçevesi. Ancak sentetik-gerçek görünüm farkını gerçek kartta ölçmek gerektiğini NVIDIA’nın kendi dokümantasyonu da vurguluyor. [NVIDIA Cosmos Data Factory](https://blogs.nvidia.com/blog/cosmos-open-train-evaluate-deploy-world-models/), [Omniverse Replicator](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html)

## Yeni araştırma adayı

**Aday soru:** *PCB tasarımı ve BOM’dan gelen yerleşim bilgisini az referanslı anomali belleği ve hedefli sentetik kusurlarla birleştirmek, daha önce görülmemiş kart varyantlarında sabit yanlış-alarm düzeyinde kusur yakalamayı artırıyor mu?*

Bu yön, bugünkü PatchCore/DINOv2 ve komponent tespiti altyapısını koruyup fabrika ihtiyacına bağlar. Olası yöntemde her komponent bölgesi tasarım/BOM kimliği ve beklenen yerleşimiyle eşleşir; normal referans belleği bu bilgiye göre daraltılır; dijital ikizden üretilen ışık, kamera ve olası hata örnekleriyle model hazırlanır; şüpheli AOI adayları operatöre benzer örnekler, belirsizlik ve neden puanı ile gösterilir. Nihai eşik ve alarm kabulü operatör/kalite mühendisi denetiminde kalır.

Özgün katkı, “DINOv2 ekledik” veya “sentetik görüntü ürettik” olmamalı. Araştırma iddiası şu karşılaştırma ile sınanabilir:

1. **Klasik referans:** normal gerçek kartlar + standart PatchCore/AnomalyDINO.
2. **Yerleşim bilgili referans:** normal yamaları kart tasarımı/komponent/konumla eşleştiren bellek.
3. **Sentetik destekli:** aynı referanslara dijital ikizden iyi/kusurlu varyasyonlar ekleme.
4. **Birleşik yöntem:** yerleşim bilgisi + hedefli sentetik veri.

Test, eğitimde hiç görülmemiş gerçek fiziksel kart/ürün varyantlarında tutulmalı. Ana endüstriyel ölçüler yalnız AUROC olmamalı: belirli bir yanlış alarm sayısında kusur yakalama, kart başına false-call oranı, kaç gerçek kusurun kaçtığı, kalibrasyon için gereken normal/altın kart sayısı, operatörün çözdüğü bulgu oranı ve yeni tasarıma hazırlık süresi. Sentetik veri, sadece aynı simülatörde başarı gösterirse yeterli değildir; görülmemiş **gerçek** kartlardaki kazanç ölçülmelidir.

## Bugünkü proje için uygulanabilir aşamalar

### Kısa vadede — mevcut veriyle

- RobustAD-PCB'de üç başlangıç hattı karşılaştırıldı; WideResNet50 PatchCore, ResNet18 PatchCore ve AnomalyDINO sonuçları [raporda](robustad-pcb-method-comparison.tr.md). Görüntü tespiti hedef alanlarda zayıf kalırken DINO'nun yerelleştirme ölçüleri daha yüksek; bellek maliyeti ve tam pipeline farkları hesaba katılmalı.
- VisA PCB kategorilerinde gerçek maskelerle sınırları belirli sentetik kusur kompozisyonu deneyi tasarla; sentetik örnekleri yalnız eğitim/ayar tarafında kullan, gerçek test maskelerini hiç üretim için kullanma.
- Kuo verisindeki komponent kutularını, yalnızca **komponent/konum** gözetimi olarak kullan; kutu etiketi kusur etiketi değildir.
- “Dijital ikiz AOI doğruluğunu kanıtladık” iddiası kurma. Bu veriyle yapılabilecek sonuç, sentetikten gerçek kusur maskelerine aktarım ön çalışmasıdır.

### Güçlü makale ve gerçek fabrika iddiası için

Siemens benzeri bir iş birliğiyle CAD/Gerber/ODB++, BOM ve pick-and-place koordinatları; AOI görüntüleri ve aday kutuları; doğrulanmış gerçek hata/false-call etiketleri; kart/ürün varyantı, hat, kamera ve proses kimliği gerekir. Eğitim/kalibrasyon kartları ile son test kartları ürün/board bazında ayrılmalı. Dijital ikiz/sentetik örneklerin kaynağı ve kullanım lisansı da izlenmeli. Bunlar olmadan bu proje Siemens’in üretim sonuçlarını yeniden üretemez.

## Önerim

Mevcut makalenin ana sonucunu kontrollü az-referanslı sağlamlık çalışması olarak koruyalım; Siemens–NVIDIA fikrini ise **sonraki özgün yöntem programının** motivasyonu yapalım. RobustAD başlangıçlarını sabitleyip hata analizini tamamlayalım; ardından şu iki yoldan biri seçilebilir:

- **Daha küçük, yapılabilir çalışma:** VisA gerçek kusurlarında sentetik-kompozisyonun sınırlı katkısını ve başarısız olduğu kusur tiplerini ölçmek.
- **Daha güçlü, endüstriyel çalışma:** CAD/BOM ile koşullanan sanal altın kart ve AOI false-call azaltımını daha önce görülmemiş gerçek PCB varyantlarında doğrulamak.

İkinci yol daha özgün ve daha çok endüstri mühendisliği değeri taşıyor; fakat gerçek tasarım, üretim ve doğrulanmış alarm verisine erişim olmadan savunulabilir şekilde tamamlanamaz. Bu belge aday yönü tarif eder; yenilik literatür taraması ve gerçek veriyle kanıtlanmış değildir.
