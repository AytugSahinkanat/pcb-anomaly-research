# RobustAD-PCB kusur türü hata analizi

**Durum:** ResNet18 ve WideResNet50-2 PatchCore için tamamlandı; AnomalyDINO kusur türü alt analizi tamamlanmadı.

## Soru ve protokol

Toplam anomali skoru hangi kusur sınıflarını daha iyi sıralıyor? Her resmi kaymış çekim alanında, bir kusur sınıfı pozitif; normal görüntüler negatif alındı. Diğer kusur sınıfları o karşılaştırmadan çıkarıldı. Dört/bazen beş alanın AUROC ve AP değerleri, her referans seçimi içinde eşit ağırlıkla ortalandı. Raporlanan ± değerler, aynı görüntüleri tekrar kullanan beş referans seçiminin örnek standart sapmasıdır; veri örneklemesi güven aralığı değildir.

Her iki PatchCore omurgası aynı 224×224 ön işleme, 16 normal referans ve bellek ayarını kullandı. Metadata'daki üç kusur etiketi (`Missing Component`, `Soldering Melt`, `Scratch`) görüntü adlarından eşlendi. `test4`'te aynı piksel karesine bağlı, birbiriyle uyuşmayan iki kusur maskesi bulunduğu için bu tek belirsiz kare kusur türü analizinden çıkarıldı. Kaynak `test0` alanı, yalnız kaymış alan hedefini özetlemek için makrodan çıkarıldı. Eşik seçilmedi.

## Kaymış alanlarda görüntü düzeyi sonuç

Metrikler yüzde; **±**, beş referans seçimi arasındaki standart sapmadır.

| Yöntem | Kusur türü | Görüntü AUROC | Görüntü AP | Alan sayısı |
|---|---|---:|---:|---:|
| WideResNet50-2 PatchCore | Missing Component | 46,86 ± 1,85 | 30,55 ± 2,25 | 4 |
| ResNet18 PatchCore | Missing Component | 49,80 ± 3,21 | 33,77 ± 1,98 | 4 |
| WideResNet50-2 PatchCore | Soldering Melt | 40,72 ± 5,77 | 19,54 ± 2,83 | 5 |
| ResNet18 PatchCore | Soldering Melt | 30,33 ± 2,72 | 18,34 ± 1,44 | 5 |
| WideResNet50-2 PatchCore | Scratch | 45,75 ± 8,74 | 23,82 ± 6,50 | 5 |
| ResNet18 PatchCore | Scratch | 36,47 ± 3,35 | 20,89 ± 2,22 | 5 |

## Yorum

- Bu alt analizde WideResNet50-2, lehim erimesi ve çizik karelerini sıralamada daha yüksek ortalama AUROC verdi. AP farkı çok daha küçüktür; bu değerlerde kusur sınıfının alan içindeki oranı etkilidir.
- Eksik komponent sınıfında ResNet18'in ortalama AUROC ve AP'si daha yüksek çıktı. Dolayısıyla önceki genel PatchCore sıralaması, her kusur türünde aynı kazananı vermiyor.
- Tüm kusur sınıflarında ortalama AUROC %50 çevresinde veya altında. Bu veri ve kurulum, kaymış alanlarda güvenilir görüntü alarmı iddiasını desteklemiyor.
- Bu sonuçlar görüntü düzeyi sıralamadır; kutu/piksel yerelleştirme veya kusur türü sınıflandırma başarımı değildir. DINO dahil değildir; ana üç yöntemli alan kıyası [burada](robustad-pcb-method-comparison.tr.md).

## Sınırlar ve sıradaki adım

Birleşik 16-referans protokolü her sınıf için az sayıda kusurlu görüntü bırakıyor. Beş seçim aynı görüntüleri kullandığı için ± değerler yeni kartlara belirsizliği göstermez. Sonraki adım, DINO alt grubunu daha hızlı ve seed başına kaydedilen bir iş akışıyla tamamlamak; ardından en çok kaçırılan kareleri nitel olarak incelemek olmalı. Eşik ayarı kaymış test alanlarında yapılmamalı.

Makine-okunur ayrıntılar ve her alan/seed sonucu: [`robustad-pcb-defect-type-image-ranking-v1.json`](../reports/robustad-pcb-defect-type-image-ranking-v1.json).
