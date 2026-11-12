# RobustAD-PCB veri denetimi

**Denetim tarihi:** 12 Kasım 2026  
**Kaynak:** [AmazonScience/RobustAD](https://huggingface.co/datasets/AmazonScience/RobustAD)  
**Sabitlenen depo sürümü:** `82c642b2d18be60f2dab104f8dd4dea1f4ccfacb`  
**Lisans:** depo kartında CC BY 4.0  
**Yerel veri:** `data/robustad-pcb-v1/PCB/` (yaklaşık 6,18 GB)

## Denetim özeti

RobustAD’ın yalnızca PCB alt kümesi yedi split olarak indirildi. Manifestteki bütün 1.260 JPEG açıldı; 480 anomalilik örneğin tamamında maske referansı bulundu ve tüm maskeler açıldı. Maskeler tek kanallı ve ikili (`0/255`); maske ile ilişkili görüntü boyutları eşleşiyor. Manifestteki `file_name`, `label` ve `mask` alanları dosya sistemiyle tutarlı. Split dışı görsel veya eksik dosya referansı bulunmadı.

| Split | Koşul | Görüntü | Normal | Kusurlu | Kusur dağılımı |
|---|---|---:|---:|---:|---|
| train | kaynak eğitim | 255 | 180 | 75 | 25’er eksik komponent, lehim erimesi, çizik |
| test0 | kaynak koşul kontrolü | 195 | 120 | 75 | 25’er üç kusur türü |
| test1 | aydınlatma | 210 | 120 | 90 | 30’ar üç kusur türü |
| test2 | beyaz dengesi (AWB) | 180 | 120 | 60 | 30 lehim erimesi, 30 çizik; eksik komponent yok |
| test3 | dönüş | 140 | 80 | 60 | 20’şer üç kusur türü |
| test4 | konum | 140 | 80 | 60 | 20’şer üç kusur türü |
| test5 | gölge / arka plan | 140 | 80 | 60 | 20’şer üç kusur türü |
| **Toplam** |  | **1.260** | **780** | **480** |  |

Test split’lerinin toplamı 1.005 görüntü: 600 normal ve 405 kusurlu. Eğitim split’inde ayrıca 75 etiketli kusurlu görüntü bulunuyor. Normalle öğrenen PatchCore/AnomalyDINO deneylerinde bu 75 görüntü normal referans belleğine alınmamalı. Kaynak eğitimde 180 normal görüntü mevcut.

## Dikkat gerektiren bulgular

1. **Bir piksel düzeyinde aynı JPEG iki ayrı kusur örneği olarak yer alıyor.** `test4` içinde `...Soldering Melt_3.jpg` ve `...Scratch_3.jpg` SHA-256 olarak birebir aynı görüntü. Dosya adları/etiketleri farklı, maskeleri farklı ve kısmen örtüşüyor: maskelerin IoU’su 0,078; küçük çizik maskesinin yaklaşık %90’ı geniş lehim maskesinin içinde. Görsel inceleme, aynı karede farklı bölgelerde işaretlenmiş kusur izleri olduğunu düşündürüyor; fakat bu çoklu kusur/etiketleme yorumu kaynak metadatada açıklanmıyor. Anomali değerlendirmesinde aynı kare iki kez sayılmasın diye, ana metrikten önce tek-kare birleştirme ve maskeleri birleştirme politikası belirlenmeli; mevcut kayıt biçimiyle sonuç duyarlılığı ayrıca raporlanmalı.
2. **Kaynak train ve test0’da görüntü boyutu sınıfla tamamen çakışıyor.** Normal karelerin tümü 2560×2560, kusurlu karelerin tümü 2048×2048. Bu nedenle ham boyut/ön işleme farkı etiketle ilişkili. Test1–test5’te normal ve kusurlu kareler 2048×2048. Kaynak alanda model karşılaştırması için tüm karelere aynı, önceden belirlenmiş tam-görüntü ölçeklemesi uygulanmalı; ayrıca çözünürlük dağılımı sınır olarak yazılmalı.
3. **Test2’de bir kusur sınıfı yok.** AWB alanında eksik komponent örneği bulunmuyor. O alan için üç-sınıflı makro ortalama hesaplanamaz; her kusur türü ve her alan ayrı tablolanmalı.
4. **Fiziksel kart/tasarım kimliği açıkça verilmemiş.** Metadata alanları yalnızca `file_name`, `label`, `mask`. Dosya adlarında çekim koşulu ve sıra numarası olsa da sıra numarasının fiziksel kartı mı, kareyi mi gösterdiğine dair kaynak eşlemesi yok. Bu split, gerçek çekim koşulları altındaki domain-shift değerlendirmesini destekler; **yeni PCB tasarımına genelleme veya board-held-out doğrulama** iddiasını desteklemez.

## Bu projede kullanılabilir mi?

**Evet, koşullu olarak:** RobustAD-PCB, VisA’da geliştirdiğimiz az referanslı anomali yöntemlerinin aydınlatma, AWB, dönüş, konum ve gölge değişimlerinde ne kadar bozulduğunu ölçmek için iyi bir dış veri kaynağı. Aynı testte örnek sayıları ve maskeler mevcut; test0 kaynak koşulu tabanı, test1–test5 ayrı hedef koşullar olabilir. Bu, model sıralamasını farklı gerçek çekim şartlarında yeniden ölçer.

**Ancak şu iddia için uygun değil:** fiziksel olarak yeni bir kart tasarımına geçiş. Board kimliği yok; ayrıca yalnız sınırlı sayıda kart görünümü/ürün örüntüsü olabilir. Sonuçları “domain-shift dayanıklılığı” olarak konumlandırmalıyız.

Önerilen sabit protokol: 180 kaynak normal görüntüden 16-shot referans seç; kalan kaynak normal görüntülerden, test alanlarını görmeden, eşik kalibrasyonu için önceden ayrılmış bir bölüm kullan. `test0` kaynak koşulu sonucu, `test1–test5` ise ayrı alan sonuçları olsun. Ön işlem tüm kareyi koruyan tek bir kare yeniden boyutlandırması olsun; VisA’daki merkez kırpımı burada aynen kullanmak PCB kenarlarını atabilir. `test4`teki aynı kare/çift maske durumu için, sonuçları açmadan tekilleştirme ve piksel-maskesi birleştirme kuralını belirle. Aynı 16-shot listesi ve eşik kararı daha sonra değiştirilmeyen hedef test koşullarında kullanılsın.

## Üretim çıktıları

- Denetim kodu: [`audit_robustad_pcb.py`](../src/pcb_anomaly/audit_robustad_pcb.py)
- Ayrıntılı makine-okunur sonuç: [`robustad-pcb-audit-v1.json`](../reports/robustad-pcb-audit-v1.json)
- Yerel, git dışı veri: `data/robustad-pcb-v1/PCB/`
