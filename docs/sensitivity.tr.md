# Yönelim ve çözünürlük duyarlılığı

15 Ekim 2026. Bu deney, komponent değişmeden görüntü koşulu değiştiğinde ResNet18 komşuluklarının ne kadar korunduğunu ölçer. Kusur tespit doğruluğu veya elektriksel parça kimliği ölçülmez.

## Deney düzeni

- Aynı 1.156 calibration komponenti her koşulda kullanıldı. 5.921 özgün reference özelliği sabit tutuldu. Aynı aday kart grubu dışlandı; test kümesi sorgu/referans yapılmadı.
- Döndürmeler: özgün kırpmaya saat yönünün tersine 90°, 180°, 270° kayıpsız piksel transpozisyonu. Kırpma/dolgu dışında piksel kaybı veya rotasyon interpolasyonu yok.
- Çözünürlük: özgün kırpmanın **her iki kenarı** %50 veya %25 boyuta BOX filtresiyle indirildi; en yakın tamsayı ve en az 1 piksel. Bunlar yaklaşık dörtte bir ve on altıda bir piksel sayısıdır. Sonrasında önceki kare dolgu, bilinear 224×224 ve ImageNet normalizasyonu aynen uygulandı. Küçük boyutlardaki yuvarlama en-boy oranını biraz değiştirebilir; ölçüm bütün bu ön işleme zincirinin etkisidir.
- Model ve ağırlıklar değişmedi; eğitim, eşik ayarlama ve kusur etiketi üretimi yapılmadı. Kimlik dönüşümü aynı sorguları yeniden çıkararak sayısal kontrol sağlar.
- Özellik-kosinüsü: dönüştürülmüş sorgu ile kendi özgün özelliğinin cosine benzerliği.
- Top-1 korunumu: en yakın **aynı örnek kimliğinin** korunma oranı. Aynı kategori/paket anlamına gelmez.
- Top-5 örtüşmesi: eski ve yeni ilk k komşu kümesinin kesişimi / k; k=min(5, reference sayısı). Jaccard değildir. Eşit skorlarda sabit sıra kullanılır.
- En yakın skor farkı: yeni en yakın komşunun cosine skoru eksi özgün en yakın skor. Eski komşunun yeni skoru değildir.

Kategori içi ölçümlerde 1.153 sorgu vardır. Üç `diode zener array` sorgusunun reference karşılığı yoktur. Bir `resistor jumper` sorgusunun sadece bir reference'ı vardır; bu sorguda komşu korunumu zorunlu olarak %100'dür. Kategori filtresiz ölçümlerde 1.156 sorgu vardır. Genel sonuçlar sorgu sayısıyla ağırlıklıdır; nadir kategoriler eşit ağırlıkta değildir.

## Sonuçlar

Tam çalışma tamamlandı. Kimlik dönüşümünün önceki özelliklere göre en büyük mutlak hatası **0,0**; top-1/top-5 korunumu **%100**. Altı koşulun çıkarım ve ölçüm süresi yaklaşık 308 saniye.

**Aynı kategori içinde, farklı karttan komşular:**

| Koşul | Özelliğin özgün haliyle ortalama cosine | Top-1 korunumu | Top-5 örtüşmesi | En yakın cosine skor farkı |
|---|---:|---:|---:|---:|
| Özgün kontrol | 1,000 | %100 | %100 | 0,0000 |
| 90° | 0,796 | %7,1 | %11,9 | −0,0038 |
| 180° | 0,943 | %47,9 | %61,9 | −0,0007 |
| 270° | 0,797 | %7,3 | %12,0 | −0,0048 |
| Kenarlar %50 | 0,923 | %30,3 | %43,7 | −0,0044 |
| Kenarlar %25 | 0,802 | %10,8 | %22,1 | −0,0305 |

**Kategori filtresiz arama:**

| Koşul | Top-1 korunumu | Top-5 örtüşmesi | Sorguyla aynı kategoriye düşme |
|---|---:|---:|---:|
| Özgün kontrol | %100 | %100 | %58,8 |
| 90° | %4,4 | %6,9 | %54,5 |
| 180° | %36,3 | %49,8 | %56,1 |
| 270° | %4,6 | %7,2 | %56,5 |
| Kenarlar %50 | %23,0 | %30,7 | %48,4 |
| Kenarlar %25 | %6,5 | %8,4 | %34,5 |

En yakın skorun benzer kalması, komşu kimliklerinin korunduğu anlamına gelmiyor. 90° dönüşte top-5 örtüşmesi %11,9'a inerken skor farkı yalnızca −0,0038. Özellikle yoğun reference bankalarında benzer görünümlü çok sayıda alternatif bulunması bu sonucu açıklayabilecek etkenlerden biridir; bunun katkısı ayrıca ayrıştırılmadı.

**Kategori içi top-5 örtüşmesi:**

| Kategori | 90° | Kenarlar %50 | Kenarlar %25 |
|---|---:|---:|---:|
| capacitor | %1,5 | %14,6 | %1,4 |
| resistor | %0,4 | %21,9 | %3,1 |
| ic | %23,4 | %57,1 | %29,7 |
| connector | %13,7 | %82,7 | %50,2 |
| resistor network | %20,0 | %64,3 | %50,0 |
| unknown | %4,5 | %50,9 | %25,1 |

Özgün kısa kenarı <16 piksel olan 280 sorguda, %50/%25 küçültme sonrası kategori içi top-5 örtüşmesi **%30,3/%12,0**. Diğer 876 sorguda **%47,9/%25,4**. Grupların kategori ve kart bileşimleri farklıdır; bu fark sadece çözünürlüğe atfedilemez. Aynı sorgular üzerindeki eşleştirilmiş dönüşüm etkileri ise yukarıdaki ana tablolarda doğrudan ölçülmüştür.

## Yorum ve sonraki deney

Mevcut temsil **rotasyondan bağımsız değil**. 90°/270° dönüşleri, 180° dönüşten belirgin biçimde daha fazla komşuluk değiştiriyor. Çözünürlük azaltma da özellikle direnç/kapasitör gibi küçük pasiflerde komşu kimliklerini değiştiriyor. Kategori filtresiz etiket uyumu %58,8'den %25 kenar boyutunda %34,5'e düşüyor; bu bulgu, değişimin yalnızca aynı kategoride eşdeğer parçalar arasında olmadığını gösteriyor.

ResNet18 başlangıç modeli korunmalı, fakat görüntü yönelimi/çözünürlüğü kontrol edilmeden mesafe skorlarını kusura bağlamamalıyız. Sonraki kontrollü karşılaştırma: aynı modelin özgün temsili ile dört yönelimden özellik birleştirme veya döndürülmüş reference bankası. Bu yöntemlerin daha iyi olduğu henüz ölçülmedi. Yönelim/polarite hatasını tespit etmeyi hedefleyen deneylerde yönelim bilgisini tamamen silmek istenen sinyali de yok edebilir; bu hedef ayrıca tanımlanmalı.

## Yeniden üretim ve sınırlamalar

```console
python -m pcb_anomaly.sensitivity --features data/features-resnet18-v1 --crops data/crops-v1 --output data/sensitivity-v2
```

CPU çalışmasında `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=4` ortam ayarları kullanıldı; PyTorch thread sayısı 4, batch boyutu 32 ve seed 42. İlk çalışma hesaplama hızını iyileştirmek için durduruldu; `data/sensitivity-v1` tamamlanmış sonuç değildir. Sonuç kaynağı `data/sensitivity-v2/run.json` içindeki `status=complete` çalışmasıdır.

`summary.json` kategori, kart ve özgün kısa kenarı <16 piksel olan/olmayan grupların özetlerini içerir. `records.jsonl` eşleştirilmiş örnek ölçümlerini; dönüşüm adlı NPY dosyaları özellikleri; `queries.jsonl` sıralı sorgu kimliklerini içerir. Komşu indeksleri özgün `samples.jsonl` satırlarına karşılık gelir.

Bir görüntüyü dijital olarak küçültmek, gerçek kamerayla daha uzaktan çekmenin tüm optik etkilerini taklit etmez. Rotasyon/dolgu birlikte değerlendirilir; kare dolgu etkisi ayrıca ayrıştırılmadı. Referans bankası sabit olduğundan bu sonuçlar rotasyonla zenginleştirilmiş bankanın performansını göstermez. Aday kart grupları fiziksel/yerleşim ailesi bağımsızlığını garanti etmez. Komponentler aynı karttan geldiği için bağımsız örnekler gibi güven aralığı hesaplanmadı.

Dört yeni test: kayıpsız rotasyon ve kapsam, çözünürlük yuvarlama, sıralama/örtüşme hesabı, kimlik dönüşümü/eşit skorlar. Toplam 23 birim test geçti. Tam veri kimlik kontrolü ayrıca gerçek ağırlıklarla çalıştırıldı.
