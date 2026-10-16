# Çok çözünürlüklü referans bankası

17 Ekim 2026. Hipotez: düşük çözünürlüklü sorgular için reference parçaların küçültülmüş görünümlerini de sunmak, komşuluk kararlılığını artırabilir. Model, sorgular ve veri bölmesi değiştirilmez.

5.921 reference komponentinin özgün, her kenarda %50 ve %25 boyutlu görünümleri ayrı ResNet18 özellikleriyle temsil edilir. BOX küçültme, kare dolgu, bilinear 224×224, ImageNet normalizasyonu ve L2 normalize 512D çıktı önceki deneyle aynıdır. 1.156 calibration sorgusu için önceki özgün/%50/%25 özellikleri kullanılır; test kullanılmaz.

Her sorgu–reference komponent çifti için üç görünümün **en yüksek cosine skoru** alınır. Top-k, çoğaltılmış görünümler değil farklı komponent kimlikleri üzerinden hesaplanır. Komşular sorguyla aynı aday kart grubundan olamaz. Kalite ve etiket sınırları önceki deneylerdeki gibidir; üç sorgunun kategori içi reference karşılığı yoktur.

Kararlılık, her yöntemin kendi özgün sorgu komşularına göre ölçülür. Tek görünüm, dört yönelim ortalaması ve bu banka üç ayrı deneydir; yeni banka dört yönelim yöntemine eklenmiş değildir. Sorgu özelliği sabit kaldığından özgün özelliğe cosine benzerliği önceki tek görünümle aynıdır; yalnız reference eşleştirmesi değişir.

## Ölçülen sonuç

Çalışma tamamlandı: 5.921 reference ve üç koşulda 1.156 sorgu için 3.468 kayıt. Yeni özellik matrislerinin normları ve örnek sayıları doğrulandı; çalışma yaklaşık 266 saniye sürdü.

**Kategori filtresiz en yakın komşunun sorguyla aynı etikete sahip olma oranı:**

| Sorgu koşulu | Tek görünüm | Dört yönelim ortalaması | Üç çözünürlüklü banka |
|---|---:|---:|---:|
| Özgün | %58,8 | %56,3 | %60,0 |
| Kenarlar %50 | %48,4 | %44,1 | %54,8 |
| Kenarlar %25 | %34,5 | %34,5 | %51,1 |

Tek görünüme göre %50 boyutta **6,4 yüzde puan**, %25 boyutta **16,6 yüzde puan** artış var. Bu, düşük çözünürlüklü sorguların kategoriyle uyumlu reference bulmasında olumlu bir işaret; gerçek kusur başarısı olarak yorumlanamaz.

**Aynı kategoride ilk beş komşunun örtüşmesi:**

| Sorgu koşulu | Tek görünüm | Dört yönelim ortalaması | Üç çözünürlüklü banka |
|---|---:|---:|---:|
| Kenarlar %50 | %43,7 | %40,6 | %41,2 |
| Kenarlar %25 | %22,1 | %19,7 | %23,6 |

Kategori içi top-1 korunumu yeni bankada %50 için %28,4, %25 için %12,2 (tek görünüm: %30,3 ve %10,8). Aynı komponent kimliklerini korumada sonuç karışık: yarı boyutta gerileme, çeyrek boyutta küçük artış. Kategori filtresiz top-5 örtüşmesi %25 boyutta %8,4→%13,8.

Kategori uyumu artışı bütün kategorilere eşit dağılmıyor. %25 boyutta IC %27,6→%40,8, connector %54,2→%70,0, resistor %44,1→%55,5; capacitor %61,3→%62,0. `unknown` uyumu %5,5→%36,4; bu heterojen etiketin daha sık eşleşmesi güvenilir tür tanıma başarısı anlamına gelmez.

Yeni bankada küçültülmüş sorguların en yakın kategori-içi cosine skoru özgün sorguya göre %50 koşulunda ortalama +0,0173, %25 koşulunda +0,0340. Görüntü ayrıntısı azaldığında bile skor artabiliyor; skor doğrudan kalite veya kusursuzluk göstergesi değil.

**Karar:** düşük çözünürlükte kategoriyle uyumlu reference bulmak için aday olarak tut; genel komşuluk kararlılığı veya kusur tespiti iyileştirmesi olarak ilan etme. Kuo üstündeki temsil denemelerini genişletmek yerine bu adayın gerçek kusur verisindeki fayda/zararını ölç.

## Önemli yorum sınırı

Özgün reference görünümü bankada kaldığı için, en yüksek cosine seçimi her komponentin skorunu aynı bırakabilir veya artırabilir. Bu durum **tasarım gereğidir** ve anomali tespitinde iyileşme kanıtı değildir. Mesafe tabanlı anomali skorunu azaltabilir, gerçek kusuru da maskeleyebilir. Bu nedenle eski eşik doğrudan taşınmamalı; gerçek kusurlarda ayrı calibration ve değerlendirme gereklidir.

Reference özellik belleği ve kaba arama maliyeti yaklaşık üç katına çıkar; sorgu için hâlâ bir model geçişi yeterlidir. Aynı kategori içinde yakın görünen çok sayıda parça varsa tam örnek kimliğinin değişmesi tek başına başarısızlık da değildir. Top-k kararlılığı, kategori uyumu ve gerçek kusur başarısı ayrı ölçümlerdir.

## Yeniden üretim

```console
python -m pcb_anomaly.scale_bank --features data/features-resnet18-v1 --sensitivity data/sensitivity-v2 --crops data/crops-v1 --output data/scale-bank-v1
```

CPU ortamı: `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=4`; PyTorch 4 thread, batch 32, seed 42. Tamamlanma `run.json` içinde `status=complete` ile doğrulanır. `summary.json` kategori/kart kırılımlarını, `records.jsonl` örnek bazlı sonuçları içerir. Bu deneyde komşu indeksleri yerel `reference.jsonl` sırasına karşılık gelir; eski deneyin global manifest indeksleriyle karıştırılmamalıdır.

Üç yeni test, görünümlerin kimlik bazında birleştirilmesini, sınıf filtresi/boş banka/sıralama değişimini ve geçersiz girdileri kontrol eder. Toplam 30 birim test geçti.
