# Görsel inceleme ve komponent özellikleri

İnceleme tarihi: 15 Ekim 2026. Kaynak: `docs/data-audit.tr.md` içindeki SHA256 ile tanımlanan arşiv.

## İncelemenin kapsamı

47 kaynak görüntünün tamamı dört temas sayfasında incelendi. Her görüntüde kutu alanına göre sıralanan komponentlerden en küçük, ortanca ve en büyük örnek seçildi: toplam 141 kutu, altı temas sayfası. Bu amaçlı örnekleme küçük ve büyük kutu sorunlarını görünür kılar; rastgele doğruluk örneklemesi değildir. **8.016 kutunun tamamı elle doğrulanmış değildir.** Küçük önizlemeler üzerinden fiziksel kart kimliği kesinleştirilemez.

Görseller ve kırpmalar yerel tutulur. İnceleme sayfalarını üretmek için `python -m pcb_anomaly.review` komutunu kullanın. Kutular kırmızı çizgiyle, çevresindeki bağlamla gösterilir; çıktıdaki `sampled-boxes.json` inceleme örneklerini tanımlar.

## Bulgular ve kararlar

- ML450 Top1/Top2 ve Bottom1/Bottom2 görünümleri büyük kartın farklı bölümlerini gösteriyor. XLVDSproSupply Bottom1/Bottom2 için de bölüm görüntüleri söz konusu. Mevcut ortak kart grupları korunur.
- ACM-109 ve XCM-307A özellikle arka yüz yerleşiminde benzerlik gösteriyor. Aynı fiziksel kart oldukları iddia edilmez. İkisi mevcut bölmede de reference içindedir. Yeni bir bölme oluşturulacaksa aynı yerleşim ailesinde tutma konusu ayrıca değerlendirilmelidir.
- Spartan6 ve Spartan6Redux görsel olarak farklı yerleşimlerdir; ad benzerliği nedeniyle birleştirilmez.
- İncelenen örneklerde kutular genel olarak ilgili komponent bölgelerine oturuyor. Bazıları sadece gövdeyi, bazıları lehim/pin gruplarını, bazıları geniş modülleri kapsıyor. Bu durum kategori içi görünüm çeşitliliği yaratır.
- `ML450_Bottom2:00167` gibi pin gruplarında geniş arka plan bulunabilir. `Spartan6Redux_Bottom:00107` ve `XLVDSproSupply_Bottom2:00010` gibi uzun ince kutularda kareye doğrudan esnetme şekli bozar; merkezden kesme de komponenti keser.
- `RPI3B_Bottom:00289` gibi çok küçük örneklerde büyütme kayıp ayrıntıyı geri getirmez. `unknown` kategorisi otomatik olarak kusurlu ya da normal sayılmaz.

Bu aşamada kutular değiştirilmedi ve fiziksel kimlik doğrulaması yapılmış gibi `group_status` güncellenmedi. Mevcut 29 aday grup korunur; yerleşim ailesi sızıntısı tamamen dışlanmış değildir.

## Kırpma sözleşmesi ve gerçek veri sonucu

VOC koordinatlarının önceki denetimde dönüştürüldüğü sıfır tabanlı, sağ/alt sınırı hariç kutular kullanılır. Kaynak çözünürlükte RGB PNG kaydedilir; kırpmada ölçekleme veya ek bağlam yoktur. Dosya adı örnek kimliğinin SHA256 özetidir; tekrar eden referans isimleri dosya üzerine yazmaz. Kaynak manifest sırası, kategori, kart grubu, bölme ve bilinmeyen kusur etiketi korunur. Geçersiz kutular sessizce düzeltilmez.

| Ölçüm | Sonuç |
|---|---:|
| Komponent kırpması | 8.016 |
| Reference / calibration / test | 5.921 / 1.156 / 939 |
| Kısa kenar <16 piksel | 1.321 |
| Uzun/kısa kenar oranı >5 | 115 |
| Tam aynı boyut ve RGB piksel içeriği olan kırpma grubu | 0 |

Kalite işaretleri filtre değildir; tüm örnekler korunur. İşaretler kesişebilir. Piksel eşitliği testi, yakın kopyaları ya da örtüşen fotoğraflardaki aynı fiziksel komponenti tespit etmez.

## Özellik çıkarımı

Başlangıç modeli ImageNet `ResNet18_Weights.IMAGENET1K_V1` ağırlıklarıyla ResNet18'dir. Sınıflandırma katmanı kaldırılır; global ortalama havuzlama sonrası 512 boyutlu çıktı L2 normalize edilir. Model eval/inference modundadır; veriyle eğitilmez, BatchNorm istatistikleri güncellenmez.

Komponent, RGB (124,116,104) dolgu ile merkeze yerleştirilerek kare yapılır; bilinear ile 224×224'e ölçeklenir ve ImageNet ortalama/standart sapmasıyla normalize edilir. Bu, torchvision ağırlıklarının standart merkez kırpma dönüşümünden **bilinçli olarak farklıdır**: uzun komponentin tamamını korur. Kare dolgunun etkisi ileride kontrollü bir karşılaştırmayla ölçülmelidir.

`features.npy` satırları `samples.jsonl` içindeki `feature_index` ile birebir eşleşir. `run.json` kaynak ve ağırlık özetlerini, sürümleri, dönüşümü ve çalışma parametrelerini kaydeder. Bir çıktı ancak `run.json` içinde `status=complete` varsa tamamlanmış sayılır; yarım kalan dizin yeni bir çıktı adıyla yeniden çalıştırılmalıdır.

Gerçek veri çalışması tamamlandı: **8.016 × 512 float32** özellik matrisi. Python 3.12.14, PyTorch 2.10.0+cpu, torchvision 0.25.0+cpu, NumPy 2.5.2 ve Pillow 12.3.0 kullanıldı. CPU'da dört thread ve batch=32 ile çıkarım/kayıt süresi 234 saniyeydi; bu süre ağırlık indirme ve ön doğrulamayı içermez.

Tüm satırların manifest sırası, sonlu değerler ve birim normları kontrol edildi; en büyük norm hatası `1.19e-7`. Dört farklı satır batch=1 ile yeniden çıkarıldığında bu ortamda en büyük mutlak fark `0.0` oldu. Bu kontrol farklı donanımlarda bit düzeyinde eşitlik garantisi değildir. 17 birim test geçti; veri ve ağırlık gerektiren bu gerçek veri kontrolleri CI birim testlerinin dışındadır.

Özellik dosyası SHA256: `24c03deb829b9e1a37f181589b2b905fbd13e4e507a3f3db5729b7513f5885f7`.

Bu özellikler bir başlangıç temsilidir; gerçek kusur etiketleri olmadığı için model başarısı, AUROC veya kalibre edilmiş kusur eşiği raporlanamaz. Sonraki adım kategori bazlı komşuluk incelemesi ve bağımsız etiketli deney tasarımıdır.
