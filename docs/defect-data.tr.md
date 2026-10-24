# Kusur verilerinin edinimi ve değerlendirme protokolü

17 Ekim 2026. Amaç, Kuo komponent benzerliği deneylerinden bağımsız olarak gerçek kusur anotasyonlarıyla değerlendirme kurmak. Veri hazırlama, model başarısı anlamına gelmez.

## SolDef_AI: indirildi ve arşiv denetlendi

Kaynak: [yazarların Kaggle yayını](https://www.kaggle.com/datasets/mauriziocalabrese/soldef-ai-pcb-dataset-for-defect-detection), [özgün makale](https://doi.org/10.3390/jmmp8030117). Kaggle API metadata'sı sürüm 1 ve `GPL 3` lisans etiketi bildiriyor. Kaynak arşiv ve metadata yerel `data/soldef-ai/` altında; Git'e eklenmiyor.

Arşiv: 1.178.779.597 bayt, SHA256 `4712db2e90f2b1541f40d61cfe5d170fd7ec3b6759a0804561b657563d41c7d0`.

| Kontrol | Yerel arşivde ölçülen |
|---|---:|
| JPG dosyası | 2.064 |
| Dosya SHA256'sına göre tekil görüntü | 1.626 |
| Görüntüyle eşleşen JSON anotasyonu | 428 |
| Tekil anotasyonlu görüntü | 428 |
| Anotasyonu bulunmayan tekil görüntü | 1.198 |
| Toplam poligon | 671 |
| Boyut / poligon koordinatı kontrolünde sorun | 0 |

Makaledeki 1.150 görüntü ifadesi, indirilen arşivin bu envanteriyle aynı sayı değildir. Arşiv sürümü ve etiketli alt küme açıkça raporlanmalı; toplam dosya sayısı bağımsız örnek sayısı olarak kullanılmamalı.

| Ham poligon etiketi | Poligon sayısı |
|---|---:|
| `good` | 186 |
| `no_good` | 116 |
| `exc_solder` | 182 |
| `poor_solder` | 57 |
| `spike` | 130 |

Bu sayılar görüntü veya bağımsız komponent sayısı değildir. Bir görüntüde birden fazla poligon ve hem `good` hem kusur etiketi bulunabilir. 117 görüntü yalnızca `good` poligonları içeriyor; bunun tüm sahnenin kusursuzluğu anlamına geldiği varsayılmadı. Etiketsiz görüntüler normal sınıfına atanmadı.

428 anotasyonlu görüntünün her biri aynı dosya içeriğine sahip tek bir `Dataset/CS*/komponent/V*/Setup*` kaynak yoluna eşleşiyor. `Labeled/` kopyalarını bağımsız örnek saymak veri sızıntısına yol açar. Makale altı ayrı PCB bildiriyor; kaynak arşivde bunlar `CS1`–`CS6` klasörleriyle temsil ediliyor. Bu kimlikleri koruyan görev bazlı leave-one-board-out planı artık [ayrı raporda](soldef-board-splits.tr.md) kayıtlı. Plan, model performansı veya bütün açılarda eşleşen aynı fiziksel komponentlerin kesin izlenmesi anlamına gelmez.

Her etiketin dosya sırasındaki ilk örneği görsel olarak incelendi: poligonlar komponent veya lehim bölgelerine oturuyor. Etiketlerin kapsamı aynı değil: `good`/`no_good` komponent gövdesini, lehim etiketleri daha küçük bölgeleri çevreleyebiliyor. Bunları tek tip piksel kusur maskesine çevirmek ek semantik karar gerektirir. Örneklem kontrolü bütün anotasyonların uzman doğrulaması değildir.

Yerel çıktılar: `data/soldef-audit-v1/audit.json`, `annotations.jsonl`, `annotation-review.jpg`.

## VisA PCB: indirildi; protokol

Kaynak: [VisA / SPot-the-Difference resmî deposu](https://github.com/amazon-science/spot-diff). Veri lisansı CC BY 4.0; kaynak makale Zou ve diğerleri, ECCV 2022. PCB1–PCB4, Kuo'daki komponent veri kümesinden ayrı bir kart düzeyi anomali görevidir.

Resmî arşiv 1.929.840.640 bayt; SHA256 `2eb8690c803ab37de0324772964100169ec8ba1fa3f7e94291c9ca673f40f362`. Dört PCB kategorisinden 4.820 dosya ayıklandı (görüntüler, maskeler ve kategori metadata'sı). Bölme dosyasının SHA256'sı `a48557e6033318cb90556f706196bc9d247a776a23ea51aecee5a80dd0332995`. Kaynak veriler `data/visa-pcb-v2/`, arşiv `data/downloads/VisA_20220922.tar` altında. İlk tek bağlantılı girişimin `data/visa-pcb/` klasörü eksiktir ve kullanılmamalıdır.

Resmî `split_csv/1cls.csv` dosyası kullanılır. Test bölümü değiştirilmez. Her kategorinin normal eğitim bölümünden, `SHA256("42:görüntü_yolu")` sırasına göre ilk 100 görüntü eşik kalibrasyonuna ayrılır; kalanlar referans havuzudur. Bu, resmî testle birlikte kullanılan **özel normal eğitim/kalibrasyon ayrımıdır**; tüm eğitim görüntülerini kullanan yayınlarla örnek bütçesi farkı belirtilmelidir.

| Kategori | Normal referans | Normal kalibrasyon | Test normal | Test kusurlu |
|---|---:|---:|---:|---:|
| PCB1 | 804 | 100 | 100 | 100 |
| PCB2 | 801 | 100 | 100 | 100 |
| PCB3 | 805 | 100 | 101 | 100 |
| PCB4 | 804 | 100 | 101 | 100 |
| Toplam | 3.214 | 400 | 402 | 400 |

Ham çok sınıflı maskeler korunur; ikili kusur maskesi `değer > 0` olarak okunur. Normal görüntüler için sıfır maske örtüktür. Denetim görüntü/maskenin açılmasını, boyut eşleşmesini, kusur maskesinin boş olmamasını ve bölümler arası birebir RGB kopyalarını kontrol eder. Fiziksel kart kimlikleri bilinmediği için fiziksel örnek bağımsızlığı iddia edilmez; yakın kopya taraması ayrıca gereklidir.

Anotasyon QA görselleri yalnızca önceden belirlenmiş ilk örnekleri gösterir; test performansına bakarak yöntem veya hiperparametre seçmek için kullanılmaz.

Yerel denetim tamamlandı: **4.416 görüntü, 400 dolu kusur maskesi; boyut uyuşmazlığı ve birebir RGB kopyası yok**. PCB1–PCB4 için ilk normal/kusurlu örnekler, maske bindirmesi ve kusur yakın planı görsel olarak kontrol edildi. PCB1–PCB3 örneklerinde pin bölgeleri, PCB4 örneğinde konektör ve komponent üzerindeki işaretli bölgeler görüntüyle hizalı görünüyor. Bu örneklem incelemesi bütün maskelerin uzman onayı değildir.

Çıktılar: `data/visa-audit-v1/manifest.jsonl`, `audit.json`, `mask-review.jpg`. Veri edinimi, güvenli yollar, kalibrasyon izolasyonu, hatalı/boş maskeler, kopya sızıntısı, HTTP aralık doğrulaması ve SolDef etiketsiz örnek politikası dahil toplam **37 birim test geçti**.

## Tekrar çalıştırma

Yeni çıktı klasörleri gereklidir; eksik veya mevcut sonuçlar sessizce üzerine yazılmaz.

```console
python -m pcb_anomaly.visa acquire --root data/visa-pcb-v2 --archive data/downloads/VisA_20220922.tar
python -m pcb_anomaly.visa audit --root data/visa-pcb-v2 --output data/visa-audit-v1
python -m pcb_anomaly.soldef acquire --root data/soldef-ai
python -m pcb_anomaly.soldef audit --root data/soldef-ai --output data/soldef-audit-v1
```

`--archive` VisA için ETag ile sabitlenmiş ve bayt aralıkları doğrulanan paralel indirme yapar. Atlanırsa tek bağlantıda akıştan yalnızca PCB dosyaları tutulur. Kesilmiş indirme veya yarım denetim tamamlanmış sonuç sayılmaz. Kaynak arşiv hash'i kaydedilir; resmî dağıtıcıdan bağımsız imzalı bir checksum doğrulaması değildir.

## Sonraki deney

Güncelleme: aşağıda tarif edilen ilk görüntü düzeyi karşılaştırması [tamamlandı ve raporlandı](visa-benchmark.tr.md). 64 referans/kategori, global ResNet18 ve PatchCore–ResNet18 varyantı kullanıldı; lokalizasyon ve daha güçlü omurga karşılaştırması bekliyor.

SolDef_AI anotasyonları için konum görevi altı, lehim görevi üç kaynak-PCB-dışarıda fold ile [bölme taslağı](soldef-board-splits.tr.md) hazırlandı. Bu bölmelerle henüz model eğitilmedi; anotasyonsuz görüntüler normal sayılmadı.

Önce VisA'da sabit bir ResNet18 başlangıç sonucu ve yama tabanlı PatchCore karşılaştırması kurulmalı. Referans bütçesi, giriş çözünürlüğü ve dönüşümler test skorları görülmeden sabitlenmeli. Kalibrasyon yalnızca normal veride eşik belirler; testte görüntü AUROC/AP, eşikte duyarlılık ve gerçekleşen yanlış alarm oranı raporlanır. Yüz normal kalibrasyon örneğiyle %1 yanlış alarm hedefi çok kaba ve belirsizdir; garanti olarak sunulmaz. Lokalizasyon için piksel değerlendirmesi ayrıca gerekir.

SolDef_AI, komponent/lehim odaklı ikinci değerlendirme için uygundur; ancak fiziksel örnek/açı grupları ve etiket semantiği çözülmeden rastgele görüntü bölmesiyle sonuç üretilmemeli. Dört yönelim ve çok çözünürlüklü referans yaklaşımının kusurları da benzerleştirerek gizleyip gizlemediği bu bağımsız etiketlerle sınanmalı.

Özellikle kartın kameraya göre dönmesiyle, komponentin karta göre yanlış yönde monte edilmesi aynı durum değildir. Komponent kırpmasını yönelimden bağımsız yapmak ikinci kusurun sinyalini silebilir. Bu nedenle yönelim kararlılığı tek başına kalite ölçütü olmamalı; kart bağlamı ve kusur türüne göre duyarlılık ayrıca incelenmeli.
