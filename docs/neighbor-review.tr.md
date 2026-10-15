# Komponent komşuluk incelemesi

15 Ekim 2026. ResNet18 özellikleri anlamlı **görünüş benzerliği** yakalıyor; elektriksel işlevi ve kusurları güvenilir biçimde ayırt ettiği gösterilmiş değil.

## Protokol

1.156 calibration sorgusu, 5.921 reference örneği içinde cosine benzerliğiyle arandı. Aynı `board_group` dışlandı. Test görüntüleri ve özellikleri komşu/sorgu olarak kullanılmadı; yalnızca metadata kategori sayımları raporda yer alır. Kart grupları henüz fiziksel kimlik/yerleşim ailesi doğrulaması değildir.

Her kategori için en yakın aynı-kategori komşunun benzerliğine göre düşük, ortanca ve yüksek örnekler seçildi. Yeterli örneği olmayan kategorilerde mevcut örnekler kullanıldı. 22 kategori, 61 sorgu ve 22 temas sayfası görsel olarak incelendi. Bu seçim rastgele değildir; görsel kabul oranı hesaplanmadı. Sayfalar sırayla sorgu, aynı kategoride ilk iki komşu (varsa), aynı kategoride en uzak örnek ve kategori filtresiz en yakın komşuyu gösterir. İlk iki komşu birbirleriyle aynı karttan olabilir; sorguyla aynı karttan olamaz.

Üç `diode zener array` sorgusunun reference karşılığı yoktur; 1.153 sorguya kategori içi eşleşme yapılabildi. 31 kategorinin sekizinde calibration sorgusu yoktur, birinde reference yoktur. Bunlar hakkında görsel genelleme yapılmadı. `resistor jumper` için sadece bir reference vardır; en yakın/en uzak aynı örnektir.

## Nicel ön kontrol

Kategori filtresiz en yakın komşunun sorguyla aynı etikete sahip olması: **680/1.156 = %58,8**. Reference bankasından eşit olasılıkla rastgele örnek çekilse, bu sorgu dağılımında beklenen etiket uyumu **%15,6** olurdu (analitik frekans hesabı; deneysel rastgele model değil). Sınıf dengesizliği ve `unknown` nedeniyle bu oranlar kusur doğruluğu olarak yorumlanamaz.

| Kategori | Sorgu | Kategori filtresiz top-1 etiket uyumu | Aynı kategoride medyan top-1 cosine |
|---|---:|---:|---:|
| capacitor | 279 | %76,7 | 0,918 |
| resistor | 227 | %69,6 | 0,910 |
| connector | 120 | %74,2 | 0,818 |
| ic | 76 | %67,1 | 0,856 |
| resistor network | 14 | %100 | 0,892 |
| electrolytic capacitor | 9 | %88,9 | 0,842 |
| diode | 14 | %0 | 0,828 |
| ferrite bead | 9 | %0 | 0,840 |
| unknown | 110 | %0,9 | 0,850 |

Az örnekli kategorilerde yüksek oran güçlü genelleme kanıtı değildir. Kart bazında uyum EDA-008'de 174/231, DuetWIFI'de 247/374, RPI3B'de 189/368, OlimexRed'de 47/104, Spartan6'da 23/79. Kategori bileşimleri farklı olduğundan bu fark yalnızca görüntü kalitesine bağlanamaz.

## Görsel bulgular

- **Kapasitör ve direnç:** gövde, metal uçlar ve yönelim sıklıkla eşleşiyor. `DuetWIFI_Top:00507` → `SystemAce_Top:00393` kapasitör çifti cosine 0,918. Bununla birlikte 51 direnç kapasitöre, 37 kapasitör dirence en yakın çıktı.
- **Direnç ağı ve IC:** pin dizilimi ve paket biçimi belirgin. `EDA-008_Top:00094` → `ACM-109_Top:00049` IC çifti 0,944. Küçük/karanlık `RPI3B_Top:00039` ise kategori filtresiz aramada dirence daha yakın (0,875); yalnızca kategori filtresi kullanmak bu hatayı gizlerdi.
- **Konnektör ve pinler:** sıra/delik geometrisi yakalanıyor. `EDA-008_Bottom:00208` uzun konektörü için 0,974 eşleşme var. Büyük dolgu alanı ve en-boy oranının benzerliği katkıda bulunabilir; yüksek cosine aynı ürün, aynı fiziksel kart veya aynı işlev kanıtı değildir.
- **Elektrolitik kapasitör, jumper, buton, clock:** benzer paket aileleri genellikle yakalanıyor. En uzak örnekler çoğunlukla aynı kategorinin başka paket/yönelim ailesi; bunları kusurlu saymak yanlış olur.
- **Diyot, ferrit boncuk, indüktör, transistor, LED:** kategori içi eşleşmelerin bir kısmı görsel olarak makul; kategori filtresiz aramada direnç/kapasitör gibi benzer gövdeler baskın çıkabiliyor. `RPI3B_Top:00112` ferrit boncuğun en yakın filtresiz komşusu bir direnç (0,913). Elektriksel tür tek görüntüden belirlenemeyebilir; anotasyon belirsizliği de ayrıca incelenmeli.
- **Pads, pins, test point:** metalik yüzeyler ve çevredeki baskı/devre dokusu eşleşmede rol oynuyor. `DuetWIFI_Top:00751` pads sorgusu kategori filtresiz aramada kapasitöre daha yakın; boş pad/komponent varlığı için bu temsil tek başına yeterli görülmemeli.
- **Unknown:** görsel olarak heterojen. Yuvarlak lehim/test noktası benzeri şekillerden küçük pasif gövdelere uzanıyor. Tek bir tutarlı kategori veya normal reference havuzu olarak kullanılmamalı.

Uzun ince parçalar ve bulanık küçük pasifler aynı yönelim/bulanıklıkta komşular buluyor. Bu, temsilin görüntü koşullarına duyarlı olduğuna dair nitel gözlemdir; nedensel ölçüm değildir. Döndürme, çözünürlük ve dolgu değişimlerini ayrı kontrollü deneylerle ölçmek gerekir.

## Karar

ResNet18'i karşılaştırma için başlangıç modeli olarak tutalım. Bu aşamada skor eşikleri veya kusur etiketleri üretmeyelim. Öncelik: kategori içi paket ailelerini incelemek, `unknown` örneklerini ayrı tutmak, küçük kırpmalarda çekim kalitesi etkisini ölçmek ve dönüşüm duyarlılığı deneyi yapmak. Daha sonra alternatif özellik çıkarıcıları aynı protokolde karşılaştırabiliriz. Calibration üzerinde yapılan bu inceleme geliştirme amaçlıdır; test kümesi son değerlendirmeye saklanmalıdır.

## Yeniden üretim

```console
python -m pcb_anomaly.neighbors --features data/features-resnet18-v1 --crops data/crops-v1 --output data/neighbors-v1
```

Yerel `index.html` tüm sayfaları açar; `summary.json` tüm kategori sonuçlarını, `neighbors.jsonl` sorgu ve komşu indekslerini içerir. İndeksler özellik çalışmasının `samples.jsonl` dosyasına karşılık gelir. Görseller ve türetilmiş veri Git'e eklenmez. İki yeni izolasyon/eksik-kategori testiyle toplam 19 test geçti.
