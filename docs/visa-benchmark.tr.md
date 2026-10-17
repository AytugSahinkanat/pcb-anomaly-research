# VisA: global ResNet18 ve PatchCore–ResNet18 karşılaştırması

17 Ekim 2026. Tamamlanmış ilk gerçek-kusur deneyi: `data/visa-benchmark-v1/run.json`, `status=complete`. Bu çalışma, aynı omurga ve az sayıda normal referansla görüntü düzeyindeki temsilleri karşılaştırır; özgün WideResNet50 PatchCore sonucunun yeniden üretimi değildir.

## Sabit deney düzeni

- VisA PCB1–PCB4. Resmî test bölümü: 402 normal, 400 kusurlu görüntü; hiçbir test örneği çıkarılmadı.
- Önceki denetimdeki 3.214 normal referans adayından kategori başına 64 görüntü seçildi (toplam 256). Seçim `SHA256("42:reference:görüntü_yolu")` sırasıyladır. İki yöntem aynı görüntüleri kullanır.
- Kategori başına 100 ayrı normal kalibrasyon görüntüsü. Referans ve kalibrasyon resmî normal eğitim bölümünden gelir; test değişmez. Fiziksel kart kimlikleri bilinmediğinden fiziksel örnek bağımsızlığı iddia edilmiyor.
- Donmuş ImageNet-1K ResNet18 V1, RGB ortalama renk dolgusu ile kareye tamamlama, 224×224 bilinear yeniden boyutlandırma, ImageNet normalizasyonu. Augmentasyon ve optimizasyon yok; seed 42.
- Global yöntem: son katmandan 512 boyutlu global ortalama, L2 normalizasyonu, referanstaki en yakın 3 görüntünün ortalama Öklid mesafesi.
- PatchCore varyantı: layer2/layer3 üzerinde 3×3 yerel ortalama; layer3 bilinear olarak 28×28'e hizalanır; 384 boyutlu birleştirilmiş yama özellikleri L2 normalize edilmez. 64×784 = 50.176 aday yamadan %1, yani 501 yama seçilir. Seçimde 64 boyutlu Gauss projeksiyonu ve başlangıcı seed ile belirlenen greedy farthest-first coreset kullanılır. Aramada özgün 384 boyutlu özellikler korunur. Tam Öklid 1NN yama mesafelerinin maksimumu görüntü skorudur; yeniden ağırlıklandırma yoktur.
- Her yöntem/kategori için normal kalibrasyon skorlarının %95 yüzdeliği (`higher`) eşiktir; `skor > eşik` kusur kararıdır. Bu sonlu örneklemde iki yöntemin de kalibrasyon alarm oranı 16/400 = %4 çıktı; testte %5 garanti edilmez.
- Referans kimlikleri ve tüm ayarlar test skorları üretilmeden `protocol.json` dosyasına yazıldı. Sonuçlara bakarak eşik, referans, çözünürlük veya coreset değiştirilmedi.

Yöntem kaynağı: [PatchCore resmî deposu](https://github.com/amazon-science/patchcore-inspection), [makale](https://arxiv.org/abs/2106.08265). Resmî kod farklı omurgaları ve katman ayarlarını destekler; burada daha küçük omurga, yerel ortalama/birleştirme, farklı coreset başlatma/projeksiyon ve kare dolgu kullanıldı. FAISS yerine bloklu tam NumPy mesafesi hesaplandı. Dolayısıyla sonuçlar genel olarak “PatchCore'un VisA performansı” şeklinde sunulmamalı; **PatchCore–ResNet18, 64 referans, 224 giriş, %1 coreset** olarak adlandırılmalı.

## Sonuçlar

AUROC ve AP dört kategorinin aritmetik ortalamasıdır; farklı kategorilerin ham skorları ortak bir sıralamada birleştirilmedi. Duyarlılık ve yanlış alarm oranları kategoriye özgü eşiklerdeki toplam kararlardan hesaplandı. AP burada eşik gruplarını dikkate alan, interpolasyonsuz average precision'dır; genel doğruluk yüzdesi değildir.

| Ölçüt | Global ResNet18 + 3NN | PatchCore–ResNet18 |
|---|---:|---:|
| Makro görüntü AUROC | %85,52 | %86,16 |
| Makro görüntü AP | %86,10 | %86,71 |
| Yakalanan kusur | 205 / 400 | 238 / 400 |
| Kusur yakalama oranı | %51,25 | %59,50 |
| Kaçırılan kusur | 195 | 162 |
| Normalde yanlış alarm | 28 / 402 | 22 / 402 |
| Gerçekleşen yanlış alarm oranı | %6,97 | %5,47 |

Bu eşik düzeninde PatchCore 33 ek kusur yakaladı ve 6 daha az yanlış alarm verdi. Ancak eşit gerçekleşen yanlış alarm oranında karşılaştırma yapılmadı; aynı kalibrasyon kuralı kullanıldı.

| Kategori | ResNet18 AUROC | PatchCore AUROC | ResNet18 duyarlılık | PatchCore duyarlılık | ResNet18 FPR | PatchCore FPR |
|---|---:|---:|---:|---:|---:|---:|
| PCB1 | %86,68 | %80,11 | %64 | %37 | %12 | %5 |
| PCB2 | %84,10 | %84,55 | %42 | %61 | %5 | %7 |
| PCB3 | %78,15 | %82,38 | %43 | %45 | %6,93 | %2,97 |
| PCB4 | %93,14 | %97,61 | %56 | %95 | %3,96 | %6,93 |

En güçlü kazanç PCB4'te; PCB1'de hem sıralama hem duyarlılık geriledi. “Yerel özellikler her kartta daha iyi” sonucu çıkarılamaz. Ayrıca en iyi toplam yöntemin hâlâ 162/400 kusuru kaçırması üretim kabul sistemi için ciddi bir eksikliktir.

## Belirsizlik ve görsel inceleme

Kategori ve sınıf içinde 1.000 eşleştirilmiş bootstrap örneklemesi (seed 2026), PatchCore eksi global yöntem makro AUROC farkı için %95 percentile aralığı **−2,29 ile +3,57 yüzde puan**, AP farkı için **−2,33 ile +3,51 yüzde puan** verdi. İki aralık da sıfırı içeriyor; küçük ortalama farkı kesin üstünlük olarak yorumlamıyoruz. Bunlar tek bir sabit referans bankasına koşullu görüntü örnekleme aralıklarıdır; seed değişimini veya bilinmeyen fiziksel kart bağımlılığını kapsamaz.

Her kategoride PatchCore'un en düşük skorlu kaçırdığı kusur ve en yüksek skorlu yanlış alarmı seçilerek sekiz örnek incelendi. Küçük anotasyonlu bölgeler bazı örneklerde zayıf ayrışıyor; arka plan ve dolgu sınırlarında da aktivasyon görülüyor. Bu, hata nedeninin kanıtı değil, sonraki önceden tanımlı deneyler için hipotezdir. Isı haritaları örnek başına min–max ölçeklidir; farklı görüntüler arasında renk yoğunluğu karşılaştırılamaz. Skor ve eşik ayrıca yazılmıştır. Piksel AUROC/AP veya lokalizasyon başarısı bu turda ölçülmedi.

Yerel görsel: `data/visa-benchmark-v1/failure-review.jpg`; seçilen dosyalar `review-selection.json` içinde. Görseller test sonrası hata analizi içindir; mevcut sonuçların ayarları değiştirilmedi.

## Hesaplama ve doğrulama

Deney CPU'da, PyTorch için 4 thread, NumPy BLAS için 1 thread ile yaklaşık **91,49 saniye** sürdü. Bu tek yerel çalışmanın duvar süresidir; bağımsız yöntem başına üretim gecikmesi ölçümü değildir. İki yöntemin omurga hesabı paylaşılmıştır. Kategori başına global referans belleği 128 KiB, PatchCore belleği 751,5 KiB'dir; model ağırlıkları, geçici özellikler ve süreç belleği bu sayılara dahil değildir.

42 birim test geçti. Ayrıca tüm 1.202 kalibrasyon/test global skoru doğrudan float64 vektör çıkarımıyla yeniden hesaplandı: en büyük mutlak fark 2,11×10⁻¹⁵. Dört görüntüde standart ResNet18 ileri geçişiyle global özellik farkı sıfır; 16 yama mesafesinin bağımsız tam mesafe hesabındaki en büyük fark 4,15×10⁻⁶. Sonuçlar `verification.json` içinde.

Protokol SHA256: `6f49941feeda5b4085d3d529872aa10489ce3f9758b7d4d4cda21287c7a595e1`.
Omurga ağırlığı SHA256: `f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec`.

```console
python -m pcb_anomaly.visa_benchmark --output data/visa-benchmark-v1
python -m pcb_anomaly.benchmark_review --benchmark data/visa-benchmark-v1
```

Yeni çalıştırmada yeni çıktı klasörü kullanılmalı. Windows PowerShell'de `$env:PYTHONPATH='src'`, `$env:OPENBLAS_NUM_THREADS='1'`, `$env:OMP_NUM_THREADS='4'` ayarlanabilir. Her kategori için coreset indeksleri, referans bankaları, sorgu özellikleri, ham yama haritaları, süreler ve skorlar saklanır. Ham çıktılar Git dışındadır.

## Araştırma açısından sonraki adım

Bu sonuç, gerçek kusur etiketleriyle çalışan bir başlangıç çizgisidir; yeni bir yöntem veya genel üstünlük kanıtı değildir. Sonraki tablo önceden tanımlanmış birden fazla referans seed'i ve sabit bütçeler içermeli; bütün sonuçlar raporlanmalı. Tam referans havuzu ve resmî WideResNet50 PatchCore ayrı karşılaştırmalardır. Çözünürlük, dolgu/arka plan ve yerel özellik ayarlarının etkisi geliştirme verisinde seçilmeli; bu test artık görülmüş olduğu için buradan seçilen yeni yöntemin bağımsız değerlendirmeye ihtiyacı vardır. Yönelim birleştirme ve çok çözünürlüklü banka, kusuru gizleme riskiyle birlikte ayrı ablasyonlar olarak ölçülmelidir.
