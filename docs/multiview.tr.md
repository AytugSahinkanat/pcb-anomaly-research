# Dört yönelimden özellik birleştirme

## Yöntem ve karşılaştırma

Her komponentin 0°, 90°, 180° ve 270° görünümleri, önceki ResNet18 modeliyle ayrı ayrı 512 boyutlu ve L2 normalize özelliklere dönüştürülür. Dört vektörün ortalaması alınır ve sonuç yeniden L2 normalize edilir. Boyut 512 kalır; birleştirme concatenation veya skor ortalaması değildir. Ortalama float64 ile biriktirilir, çıktı float32 olur.

5.921 reference ve 1.156 calibration komponenti için aynı işlem uygulanır. Dönüştürülmüş sorgular bu **sabit dört görünüm reference bankasında** aranır. Her yöntemin kararlılığı kendi özgün sorgu komşularına göre ölçülür; dört görünümün komşularının tek görünümle aynı olması beklenmez. Aynı aday kart grubu dışlanır, test kümesi kullanılmaz. Veri, kategoriler, görüntü ön işleme, cosine uzaklığı ve top-k tanımları önceki [duyarlılık deneyindeki](sensitivity.tr.md) gibidir.

Özgün tek görünüm özellikleri ve önceki deneyin sorgu özellikleri tekrar kullanılmaktadır. Eksik üç reference yönelimi ve küçültülmüş sorguların eksik üç yönelimi yeni çıkarılır. Kaynak dosya özetleri ve sıralı kimlikler çalışma kaydında korunur.

## Rotasyon kontrolünün anlamı

Kayıpsız 90°/180°/270° döndürmeler dört görünüm kümesini yalnızca döngüsel olarak yeniden sıralar. Ortalamanın bunlara değişmezliği yöntemin matematiksel özelliğidir; öğrenilmiş bir genelleme başarısı değildir. Tüm sorgular için önceden çıkarılmış dört görünüm bu sıralamalarla yeniden birleştirilir. Buna ek olarak veri sırasına eşit aralıkla yayılan sekiz sorgu 90° döndürülür ve dört görünümü **yeniden modelden geçirilerek** sonuç doğrulanır. Sürekli açılar (örneğin 15°), perspektif ve aynalama bu deney kapsamında değildir.

Çözünürlük koşullarında özgün kırpma önce BOX ile her kenarda %50/%25 boyuta düşürülür, ardından dört yönelimi çıkarılır. Bu koşullar sıranın değişmesinden ibaret değildir ve sonucu önceden garanti edilmez.

## Ölçülen sonuçlar

Çalışma 15 Ekim 2026 tarihinde tamamlandı. 5.921 reference, 1.156 calibration sorgusu ve altı koşulda 6.936 eşleştirilmiş kayıt doğrulandı. Kategori içi ölçümlerde reference karşılığı olmayan üç sorgu dışarıda kalır (n=1.153); önceki deneyle aynı kapsam. Sekiz sorgunun bağımsız dört-görünüm rotasyon kontrolünde en büyük mutlak özellik farkı **0,0**. Tüm çıkarılan özelliklerin sonluluğu ve birim normları kontrol edildi. Önbellek kullanan bu çalışma yaklaşık **728 saniye** sürdü.

**Aynı kategori içinde top-1 korunumu ve top-5 örtüşmesi:**

| Koşul | Tek görünüm top-1 | Dört görünüm top-1 | Tek görünüm top-5 | Dört görünüm top-5 |
|---|---:|---:|---:|---:|
| 90° | %7,1 | %100 | %11,9 | %100 |
| 180° | %47,9 | %100 | %61,9 | %100 |
| 270° | %7,3 | %100 | %12,0 | %100 |
| Kenarlar %50 | %30,3 | %28,9 | %43,7 | %40,6 |
| Kenarlar %25 | %10,8 | %11,3 | %22,1 | %19,7 |

Kontrol koşulunda her iki yöntemde de korunma %100. Dört görünümün rotasyon sonucu küme ortalamasının değişmezliğinden gelir; yalnızca 90°'nin tam katları için geçerlidir. Çözünürlükte top-5 örtüşmesi %50 boyutta **3,1 yüzde puan**, %25 boyutta **2,4 yüzde puan** geriledi. %25 koşulunda top-1'de küçük artış olsa da bu genel çözünürlük dayanıklılığı iyileşmesi sayılmaz.

**Kategori filtresiz en yakın komşunun sorguyla aynı kategoriye düşme oranı:**

| Koşul | Tek görünüm | Dört görünüm |
|---|---:|---:|
| Özgün | %58,8 | %56,3 |
| 90° | %54,5 | %56,3 |
| 180° | %56,1 | %56,3 |
| 270° | %56,5 | %56,3 |
| Kenarlar %50 | %48,4 | %44,1 |
| Kenarlar %25 | %34,5 | %34,5 |

Özgün görüntülerde 680/1.156 olan etiket uyumu 651/1.156'ya düştü (**−2,5 yüzde puan**). %50 boyutta gerileme **4,3 yüzde puan**. Bu bir kusur doğruluğu metriği değildir ve istatistiksel anlamlılık iddiası yapılmaz.

Kategori filtresiz top-5 örtüşmesi %50 boyutta %30,7→%31,3, %25 boyutta %8,4→%8,8: küçük artışlar var, ancak kategori içi komşuluk ve kategori uyumu birlikte değerlendirildiğinde tutarlı bir çözünürlük kazanımı yok.

**Kategori içi top-5 örtüşmesi, tek görünüm → dört görünüm:**

| Kategori | Kenarlar %50 | Kenarlar %25 |
|---|---:|---:|
| capacitor | %14,6 → %14,2 | %1,4 → %3,1 |
| resistor | %21,9 → %13,7 | %3,1 → %3,0 |
| ic | %57,1 → %62,1 | %29,7 → %26,6 |
| connector | %82,7 → %81,8 | %50,2 → %48,5 |
| resistor network | %64,3 → %77,1 | %50,0 → %45,7 |
| unknown | %50,9 → %44,0 | %25,1 → %20,9 |

IC ve direnç ağlarında %50 boyutta kazanım var; %25 boyutta korunmuyor. Dirençlerde %50 boyutta belirgin gerileme var. Nadir sınıfların sorgu sayıları az; tek başına güçlü genelleme kanıtı değiller.

Küçük sorgularda (özgün kısa kenar <16 piksel, n=280) kategori içi top-5 örtüşmesi %50 boyutta %30,3→%28,0; %25 boyutta %12,0→%13,9. Diğer sorgularda (n=876) sırasıyla %47,9→%44,6 ve %25,4→%21,6. Kategori/kart bileşimi gruplar arasında farklıdır.

Özelliğin kendi özgün haline cosine benzerliği %50 boyutta 0,923→0,944, %25 boyutta 0,802→0,837 yükseliyor. Buna rağmen komşuluk örtüşmesi genel olarak artmıyor: **özellik vektörünün daha az hareket etmesi tek başına daha kararlı sıralama anlamına gelmiyor.** Referans geometrisi de birleştirmeyle değişiyor.

## Karar

Dört görünüm ortalamasını **90° katlarında yönelimin önemsiz olduğu görevler için** ayrı bir karşılaştırma yöntemi olarak tutalım. Çözünürlük sorununa çözüm veya her durumda daha iyi varsayılan temsil olarak seçmeyelim. Tek görünüm başlangıç modeli korunmalı.

Sonraki hedef çözünürlük olduğunda, aynı protokolde birden fazla çözünürlükte temsil veya çözünürlüğe göre reference eşleştirme denenebilir. Bunların iyileştirme sağlayacağı henüz gösterilmedi. Kusur etiketi olmadan bu temsil karşılaştırmalarından kusur başarısı çıkarılmamalı.

## Yeniden üretim

```console
python -m pcb_anomaly.multiview --features data/features-resnet18-v1 --sensitivity data/sensitivity-v2 --crops data/crops-v1 --output data/multiview-v1
```

CPU ortamında `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=4`; PyTorch 4 thread, batch=32, seed=42. Önceki tamamlanmış özellik/duyarlılık çalışmaları ve doğrulanmış yerel model ağırlıkları gerekir. Çıktı dizini yeni olmalı; `run.json` içinde `status=complete` tamamlanmayı doğrular.

`comparison.json` tek/dört görünümü yan yana, `summary.json` kategori/kart/boyut kırılımlarını, `records.jsonl` örnek bazında ölçümleri içerir. `reference.npy` sırası `reference.jsonl` ile, sorgu NPY dosyaları `queries.jsonl` ile eşleşir. Komşu indeksleri özgün özellik manifestindeki satırlara karşılık gelir.

Dört görünüm ortalaması, döngüsel sıralama, tek/çift boyutlu görüntü rotasyonu ve geçersiz girdiler test edildi. Toplam 27 birim test geçti.

## Sınırlar

Kategori uyumu kusur doğruluğu değildir; eksik/belirsiz anotasyonlar ve az örnekli kategoriler devam eder. `unknown` tutarlı bir komponent sınıfı sayılmaz. Calibration üzerinde geliştirme yapılıyor; test son değerlendirmeye saklanmalıdır. Bu temsil yönelimi siler: ters yerleştirme veya polarite hatası aranacaksa yönelim bilgisi ayrı tutulmalıdır.

Dağıtımda her komponent için dört model geçişi gerekir; özellik depolaması yine 512 boyuttur. Bu çalışmadaki süre önbellek kullanımını içerdiğinden sıfırdan çıkarım için doğrudan dört kat hız karşılaştırması yapılamaz.
