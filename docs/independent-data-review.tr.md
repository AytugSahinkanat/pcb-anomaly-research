# Bağımsız kusur verisi: kaynak incelemesi ve karar

26 Ekim 2026. Bu not, mevcut SolDef_AI/VisA deneylerini bağımsız verilerle genişletme seçeneklerini ve görev sınırlarını kaydeder. Bu kaynak taraması sistematik literatür taraması değildir.

## Karar özeti

Mevcut ResNet18/HOG lehim karşılaştırmasını bağımsız doğrulayacak, açıkça indirilebilir ve kaynak kart kimlikleriyle güvenilir bir ayrım kurmaya elverişli yeni bir SMD lehim veri kümesi henüz doğrulanmadı. Bu yüzden mevcut SolDef_AI lehim sonucu üç kaynak PCB üzerinde yapılan pilot karşılaştırma olarak kalmalı.

En yakın devam seçeneği PCB-SAID yazarlarından veriye erişim koşullarını ve görüntü başına fiziksel kart/kaynak kimliklerini istemektir. Makale 175 web kaynaklı görüntü ve lehim, kaymış/kalkmış/dönmüş, eksik komponent ve kısa devre sınıflarını bildiriyor; veri için “istek üzerine” erişim belirtiyor. Bağımsız kart dışarıda testi için yazarlar kart kimliklerini veya bunların güvenilir biçimde türetilebileceği kaynak bilgisini de sağlamalı. Bu bilgiler olmadan görüntüleri rastgele bölmek aynı kart ya da tasarımın eğitim ve testte bulunması riskini doğurabilir.

Erişilebilir ikinci bir yön, PCB-IND üzerinde **ayrı bir bare-board iz/yüzey kusuru** deneyi kurmaktır. Bu veri SolDef_AI lehim/komponent montaj iddialarını doğrulamaz; ana sonuç tablosuna birleştirilmemelidir. İstenirse yüzey kusuru için ayrı görev, protokol ve sonuç tablosu oluşturulabilir.

## Adaylar

| Kaynak | İçerik ve erişim | Projeye uygun kullanım | Sınırlama / karar |
|---|---|---|---|
| [PCB-SAID, ICCV Workshops 2025](https://doi.org/10.1109/ICCVW69036.2025.00145) | 175 web kaynaklı RGB görüntü; 66 ince sınıf; iyi lehim, yanlış montaj, eksik komponent ve kısa devre; kutu ve poligon anotasyonları. Makale veriyi istek üzerine paylaşacağını söylüyor. | En yakın dış SMD montaj/lehim karşılaştırması. | İndirme bağlantısı açıkça verilmemiş. Web görüntüsü kaynakları ve fiziksel kart grupları doğrulanmadan bağımsız board split kurulamıyor. Erişim ve grup metaverisi netleşmeden benchmark başlatılmamalı. |
| [PCBA Standard-to-Real Challenge 2026](https://huggingface.co/datasets/aimmifm/PCBA_Standard-to-Real_Challenge) | Hugging Face kartı 16.400 eğitim/test VQA örneği ve akademik kullanım için erişim koşulu bildiriyor; kusur varlığı/türü soruları da içeriyor. | Standarttan gerçek PCB görüntüsüne geçiş ve kusur sorgulama üzerine ayrı VQA/genelleme çalışması. | Erişim başvurusu/koşul kabulü gerekiyor. Veri görevi soru-cevap; mevcut ROI sınıflandırma ve piksel/kutu tespit ölçümleriyle doğrudan kıyaslanamaz. |
| [PCB-IND, Scientific Data 2026](https://doi.org/10.5281/zenodo.19723114) | Endüstriyel AOI hattından 4.789 görüntü, 8 bare-board yüzey sınıfı ve 5.932 kusur anotasyonu; Zenodo'da CC BY 4.0. | Ayrı yüzey/iz kusuru tespit veya lokalizasyon benchmarkı. | SMD komponent/lehim montajı değil, dış katman etching denetimi. Resmî split ve pHash kopya taraması var; bunlar tek başına fiziksel kart/tasarım ayrımını kanıtlamaz. Board/design kimlikleri denetlenmeden bağımsızlık iddiası kurulamaz. |
| [PCB-Defect, Data in Brief 2026](https://doi.org/10.1016/j.dib.2025.112296) | 230 yüksek çözünürlüklü, laboratuvarda kimyasal aşındırmayla üretilmiş tek katmanlı kart görüntüsü; makale 1.704 yüzey kusuru ve COCO kutuları bildiriyor. | Ayrı kontrollü bare-board yüzey kusuru tespit çalışması. | Montaj/lehim kusuru değil; kontrollü laboratuvar üretimi. Veri sürümünün ve lisansının indirilecek kayıt üzerinden tekrar doğrulanması gerekir. |
| [FPIC / FICS-PCB](https://physicaldb.ece.ufl.edu/index.php/fics-pcb-image-collection-fpic/) | Komponent konumları ve türleri için PCB görüntüleri/anotasyonları. | Komponent tespiti veya referans yerleşim bağlamı. | Gerçek kusur ground truth'u yok; kusur doğrulaması olarak kullanılamaz. |

## Önerilen sonraki adım

1. PCB-SAID için erişim başvurusu hazırlamadan önce makale ve yayınevi sayfasındaki erişim ifadesini kaydet; başvuru gönderilecekse kullanıcıdan açık yetki al. Veri gelirse lisans/izin, kaynak URL, kart kimliği, tekrar görüntüler, sınıf tanımları ve anotasyon kalitesi kayda alınmalı.
2. Aynı anda, proje kapsamı genişletilecekse PCB-IND'i **ayrı yüzey kusuru hattı** olarak değerlendirebiliriz. Önce veri arşivinin hash'i, lisans metni, resmi split ve yakın/birebir tekrarlar denetlenmeli; board/design düzeyinde grup bilgisi yoksa sonuç “resmî split üzerinde” diye etiketlenmeli, bağımsız kart testi denmemeli.
3. PCBA Standard-to-Real, ancak VQA sorularına uygun ayrı bir deney tasarımıyla ele alınmalı; erişim şartları ve test protokolü görülmeden indirip mevcut kıyaslamaya eklememeliyiz.
4. Yeni bir deney açmadan önce görev, birim (kart/görüntü/ROI), grup ayrımı, metrik ve eşik seçimi protokolünü sabitleyelim. Aynı SolDef fold'ları yeni özellik/yöntem seçmek için tekrar tekrar kullanmayalım.

Şu an yayınlanabilir ana iddia yerine geçecek yeni dış veri sonucu yok. Mevcut elle tutulur bulgu SolDef_AI üzerinde kart-dışarıda ROI sınıflandırmasında ResNet18'in lehim görevinde HOG'dan daha iyi olmasıdır; sınırlı üç kart grubu nedeniyle bu, bağımsız son doğrulama değil.
