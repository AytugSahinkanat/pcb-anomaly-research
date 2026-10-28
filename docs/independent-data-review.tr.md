# Bağımsız kusur verisi: kaynak incelemesi ve karar

29 Ekim 2026. Bu not, mevcut SolDef_AI/VisA deneylerini bağımsız verilerle genişletme seçeneklerini ve görev sınırlarını kaydeder. Bu kaynak taraması sistematik literatür taraması değildir.

## Karar özeti

PCB-AoI artık erişilebilir ve resmi bölmesi 173 eğitim / 60 test kartı olarak belgelenmiş; Kaggle metaverisi Apache 2.0 lisansı bildiriyor. Görüntü ve anotasyon denetimi tamamlandı, resmî dış kart testinde sabit ResNet18/HOG ROI kusur türü karşılaştırması yapıldı ([deney raporu](pcb-aoi-classifier.tr.md)). Bu, SolDef_AI'daki post-reflow lehim ROI sonucunun bağımsız tekrarı değil: PCB-AoI lehim pastası basımını inceliyor ve yalnızca kusurlu ROI'ler içeriyor.

SolDef_AI lehim sonucu üç kaynak PCB üzerinde pilot karşılaştırma olarak kalmalı. Post-reflow lehim/montaj kusurlarına daha yakın devam adayı PCB-SAID'dir. Makale 175 web kaynaklı görüntü ve lehim, kaymış/kalkmış/dönmüş, eksik komponent ve kısa devre sınıflarını bildiriyor; veri için “istek üzerine” erişim belirtiyor. Bağımsız kart dışarıda testi için kart kimlikleri veya güvenilir kaynak metaverisi de gerekir. Bu bilgiler olmadan rastgele görüntü bölmesi uygun olmaz.

Erişilebilir ikinci bir yön, PCB-IND üzerinde **ayrı bir bare-board iz/yüzey kusuru** deneyi kurmaktır. Bu veri SolDef_AI lehim/komponent montaj iddialarını doğrulamaz; ana sonuç tablosuna birleştirilmemelidir. İstenirse yüzey kusuru için ayrı görev, protokol ve sonuç tablosu oluşturulabilir.

## Adaylar

| Kaynak | İçerik ve erişim | Projeye uygun kullanım | Sınırlama / karar |
|---|---|---|---|
| [PCB-AoI, KubeEdge-Ianvs](https://ianvs.readthedocs.io/en/latest/proposals/scenarios/industrial-defect-detection/pcb-aoi.html) | Kaggle v5, 173 eğitim ve 60 test kartı; ham JPEG ve Pascal VOC kutuları, eğitim artırmaları; Kaggle API lisansı Apache 2.0. Denetim: 173/60 ham görüntü eşleşti; 60 test görüntüsünde 332 kusur ROI'si. | Harici kart testinde kusur türü ROI sınıflandırması. Sabit ResNet18 %95,8 dengeli doğruluk; HOG %63,0. | Yalnız iki kusur etiketi ve sadece kusurlu test ROI'leri var. PatchCore/normal-kusurlu ayrımı, yanlış alarm, tam görüntü tespiti değil. Lehim pastası (SPI), post-reflow lehim bağlantısı değil. [Rapor](pcb-aoi-classifier.tr.md). |
| [PCB-SAID, ICCV Workshops 2025](https://doi.org/10.1109/ICCVW69036.2025.00145) | 175 web kaynaklı RGB görüntü; 66 ince sınıf; iyi lehim, yanlış montaj, eksik komponent ve kısa devre; kutu ve poligon anotasyonları. Makale veriyi istek üzerine paylaşacağını söylüyor. | En yakın dış SMD montaj/lehim karşılaştırması. | İndirme bağlantısı açıkça verilmemiş. Web görüntüsü kaynakları ve fiziksel kart grupları doğrulanmadan bağımsız board split kurulamıyor. Erişim ve grup metaverisi netleşmeden benchmark başlatılmamalı. |
| [PCBA Standard-to-Real Challenge 2026](https://huggingface.co/datasets/aimmifm/PCBA_Standard-to-Real_Challenge) | Hugging Face kartı 16.400 eğitim/test VQA örneği ve akademik kullanım için erişim koşulu bildiriyor; kusur varlığı/türü soruları da içeriyor. | Standarttan gerçek PCB görüntüsüne geçiş ve kusur sorgulama üzerine ayrı VQA/genelleme çalışması. | Erişim başvurusu/koşul kabulü gerekiyor. Veri görevi soru-cevap; mevcut ROI sınıflandırma ve piksel/kutu tespit ölçümleriyle doğrudan kıyaslanamaz. |
| [PCB-IND, Scientific Data 2026](https://doi.org/10.5281/zenodo.19723114) | Endüstriyel AOI hattından 4.789 görüntü, 8 bare-board yüzey sınıfı ve 5.932 kusur anotasyonu; Zenodo'da CC BY 4.0. | Ayrı yüzey/iz kusuru tespit veya lokalizasyon benchmarkı. | SMD komponent/lehim montajı değil, dış katman etching denetimi. Resmî split ve pHash kopya taraması var; bunlar tek başına fiziksel kart/tasarım ayrımını kanıtlamaz. Board/design kimlikleri denetlenmeden bağımsızlık iddiası kurulamaz. |
| [PCB-Defect, Data in Brief 2026](https://doi.org/10.1016/j.dib.2025.112296) | 230 yüksek çözünürlüklü, laboratuvarda kimyasal aşındırmayla üretilmiş tek katmanlı kart görüntüsü; makale 1.704 yüzey kusuru ve COCO kutuları bildiriyor. | Ayrı kontrollü bare-board yüzey kusuru tespit çalışması. | Montaj/lehim kusuru değil; kontrollü laboratuvar üretimi. Veri sürümünün ve lisansının indirilecek kayıt üzerinden tekrar doğrulanması gerekir. |
| [FPIC / FICS-PCB](https://physicaldb.ece.ufl.edu/index.php/fics-pcb-image-collection-fpic/) | Komponent konumları ve türleri için PCB görüntüleri/anotasyonları. | Komponent tespiti veya referans yerleşim bağlamı. | Gerçek kusur ground truth'u yok; kusur doğrulaması olarak kullanılamaz. |

## Önerilen sonraki adım

1. PCB-AoI'de tam nesne tespit veya kutu lokalizasyonu iddiası hedeflenirse, aynı board split üzerinde tek bir önceden sabitlenmiş dedektör karşılaştırması eklenmeli. Normal görüntü olmadığı açıkça belirtilmeli; sonuç yanlış alarm/anomali metriği gibi sunulmamalı.
2. Post-reflow lehim kusurlarında dış doğrulama için PCB-SAID erişimi ve kart kaynak metaverisi değerlendirilmeli. Başvuru gönderilecekse kullanıcıdan açık yetki alınmalı; veri gelirse lisans/izin, kaynak URL, kart kimliği, tekrar görüntüler, sınıf tanımları ve anotasyon kalitesi kayda alınmalı.
3. PCB-IND yalnızca **ayrı bare-board yüzey kusuru hattı** için düşünülmeli. Board/design düzeyi grup bilgisi yoksa sonuç “resmî split üzerinde” diye etiketlenmeli, bağımsız kart testi denmemeli.
4. PCBA Standard-to-Real ancak VQA'ya özgü ayrı bir deney tasarımıyla ele alınmalı. Yeni yöntem veya hiperparametre seçmeden önce görev, birim (kart/görüntü/ROI), grup ayrımı ve metrik sabitlenmeli; SolDef fold'ları yeniden ayarlama için kullanılmamalı.

Yeni bir harici sonuç artık var: PCB-AoI test kartlarında ROI kusur türü sınıflandırması. Fakat veri normal örnek içermediği ve görev SolDef/VisA'dan farklı olduğu için PatchCore yanlış alarmı veya post-reflow lehim genellemesini kanıtlamıyor. Makalenin ana kusur/anomali iddiası için bu ayrım korunmalı.
