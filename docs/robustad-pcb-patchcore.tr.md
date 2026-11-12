# RobustAD-PCB: eşlenmiş PatchCore karşılaştırması

**Durum:** ResNet18 ve WideResNet50-2 beş eşlenmiş referans seçimiyle, aynı ön işleme ve eşit yama belleğinde karşılaştırıldı. Bu sonuçlar yeni kart tasarımına genelleme iddiası değildir.

## Deney düzeni

Deney, [denetlenen RobustAD-PCB sürümünü](robustad-pcb-audit.tr.md) (`82c642b2d18be60f2dab104f8dd4dea1f4ccfacb`) kullandı. Referanslar yalnızca eğitim bölümündeki 180 normal görüntü arasından seçildi: beş sabit SHA-256 sıralaması, her birinde 16 normal görüntü. Eğitimdeki kusurlu örnekler belleğe alınmadı. Resmî `test0` kaynak çekim koşulunu, `test1`–`test5` ise farklı aydınlatma, beyaz dengesi, dönüş, konum ve gölge/arka plan koşullarını ölçüyor.

Yöntem, ImageNet-1K V1 ile önceden eğitilmiş WideResNet50-2 ve yukarı akış PatchCore uygulamasının yama özellikleri, yaklaşık %10 greedy coreset'i ve Öklid 1-en-yakın-komşu skorunu kullanıyor. Tam kareler kırpılmadan 224×224'e bilineer ölçeklendi; ikili maskeler aynı boyuta en yakın komşuyla ölçeklendi. Böylece model girdisinin piksel boyutu sabitlendi. Bu ortak ölçek, özgün 2048/2560 piksellik dosyalardaki olası görüş alanı veya fiziksel ölçek farklarını gidermez.

`test4` içindeki SHA-256 olarak aynı JPEG, ana analizde tek görüntü sayıldı; ona bağlı iki kusur maskesi birleştirildi. Bu tercih görüntünün iki kez sayılmasını önlüyor, fakat maske anotasyonunun neyi temsil ettiği kaynakta açıklanmıyor. Eşik seçilmedi; AUROC ve AP sıralama metrikleri, AUPRO ise piksel yanlış-pozitif oranı 0,30'a kadar hesaplandı. Buradaki ± değerler beş referans seçimi arasındaki örnek standart sapmadır; güven aralığı değildir.

## Sonuçlar

Metrikler yüzdeye çevrilmiştir; hücreler beş referans seçiminin ortalaması ± örnek standart sapmasıdır.

| Test alanı | Görüntü / kusurlu | Görüntü AUROC | Görüntü AP | Piksel AUROC | Piksel AP | AUPRO@FPR≤0,30 |
|---|---:|---:|---:|---:|---:|---:|
| test0: kaynak koşul | 195 / 75 | 96,35 ± 1,67 | 88,63 ± 5,85 | 96,20 ± 0,23 | 0,69 ± 0,12 | 87,15 ± 1,08 |
| test1: aydınlatma | 210 / 90 | 40,07 ± 4,28 | 43,55 ± 3,05 | 88,52 ± 0,79 | 8,66 ± 1,82 | 46,50 ± 2,29 |
| test2: beyaz dengesi | 180 / 60 | 53,64 ± 13,69 | 43,00 ± 12,14 | 88,48 ± 1,39 | 0,20 ± 0,03 | 55,07 ± 5,05 |
| test3: dönüş | 140 / 60 | 39,45 ± 4,00 | 41,52 ± 2,94 | 91,27 ± 0,59 | 6,86 ± 1,80 | 60,64 ± 3,35 |
| test4: konum | 139 / 59 | 43,11 ± 11,44 | 47,33 ± 6,56 | 83,14 ± 1,07 | 10,92 ± 1,22 | 46,72 ± 2,70 |
| test5: gölge/arka plan | 140 / 60 | 47,94 ± 0,74 | 40,44 ± 0,62 | 84,39 ± 0,19 | 0,46 ± 0,05 | 35,28 ± 1,65 |

test1–test5'in alan başına eşit ağırlıklı ortalaması görüntü AUROC için **44,84%**, görüntü AP için **43,17%**, piksel AUROC için **87,16%**, piksel AP için **5,42%** ve AUPRO için **48,84%** oldu.

## Eşlenmiş ResNet18 karşılaştırması

Aynı beş 16-kare referans seçimi, test örnekleri, 224×224 tam-kare ön işleme ve 1.024 boyutlu PatchCore belleği ResNet18'e de uygulandı. Her iki omurgada da bellek bankası 1.254 yama, yani 5.136.384 bayt (4,90 MiB) oldu. Tabloda test1–test5 ortalamaları ve alan bazında model değerleri yüzde cinsindendir.

| Test alanı | Görüntü AUROC WRN / RN18 | Görüntü AP WRN / RN18 | Piksel AP WRN / RN18 | AUPRO WRN / RN18 |
|---|---:|---:|---:|---:|
| Aydınlatma | 40,07 / 27,83 | 43,55 / 37,52 | 8,66 / 8,22 | 46,50 / 38,79 |
| Beyaz dengesi | 53,64 / 27,58 | 43,00 / 27,98 | 0,20 / 0,08 | 55,07 / 42,83 |
| Dönüş | 39,45 / 35,89 | 41,52 / 38,46 | 6,86 / 2,91 | 60,64 / 48,05 |
| Konum | 43,11 / 29,99 | 47,33 / 38,70 | 10,92 / 10,03 | 46,72 / 42,95 |
| Gölge / arka plan | 47,94 / 65,46 | 40,44 / 60,33 | 0,46 / 7,33 | 35,28 / 35,21 |
| **test1–test5 eşit ağırlıklı ortalama** | **44,84 / 37,35** | **43,17 / 40,60** | **5,42 / 5,71** | **48,84 / 41,57** |

Aynı seed'lerde hesaplanan hedef alan makro farkı WideResNet50 lehine görüntü AUROC'ta **+7,49 ± 4,55**, AUPRO'da **+7,27 ± 3,17 yüzde puanı** oldu. Görüntü AP farkı **+2,57 ± 4,77**, piksel AUROC farkı **+1,45 ± 0,77**, piksel AP farkı ise **−0,29 ± 1,02** puandı. ± değerleri beş eşlenmiş referans seçiminin farkları arasındaki örnek standart sapmadır. Gölge/arka plan alanında ResNet18'in görüntü AUROC ve piksel AP'si daha yüksek; bu nedenle her alan veya ölçü için tek kazanan yok. Her iki omurganın da ortalama hedef-alan görüntü AUROC'u %50'nin altında kaldı.

## Yinelenen test4 karesi: sayım duyarlılığı

Ana sonuçta aynı fotoğraf tek görüntü olarak sayıldı ve iki anotasyon maskesi birleştirildi. Kaynak metadatadaki iki satırı ayrı örnek sayıp her birinde kendi maskesini kullanınca, WideResNet50'nin test4 görüntü AUROC'u **43,11%'den 42,85%'e** değişti (−0,26 puan). Görüntü AP, piksel AUROC, piksel AP ve AUPRO değişimleri de ayrı ayrı 0,12 puandan küçüktü. Dolayısıyla bu kare için genel test4 sonucunun büyüklüğü sayım kuralına duyarlı görünmüyor; iki satırın anotasyon anlamı yine de kaynakça doğrulanmış değil.

## Yorum ve sınırlar

- Kaynak test ile alan değişimi arasında büyük bir düşüş var. Bu deney ayarlarında normal çekim koşullarında kuvvetli olan görüntü skoru, beş farklı çekim alanında güvenilir kusur sıralaması yapmadı; ortalama görüntü AUROC'u şans seviyesinin altındaydı. AWB ve konum sonuçlarında beş referans seçimi arasındaki oynama da belirgin.
- Piksel AUROC'u tek başına yanıltıcı olabilir. Yeniden boyutlandırılmış test maskelerinde kusur pikselleri alanın yaklaşık **%0,02–0,06**'sını oluşturuyor. Bu nedenle AP ve AUPRO daha anlamlı tamamlayıcı ölçüler. Yüksek piksel AUROC'u, kusur bölgesinin pratik olarak iyi bulunduğunu tek başına göstermez.
- Bu tek bir PatchCore yapılandırmasıdır; AnomalyDINO veya ResNet18 ile RobustAD üzerinde eşlenmiş kıyas henüz yok. Beş referans seçimi, bağımsız kart veya üretim partisi örneklemesi değildir.
- Kaynak train/test0'da normal örnekler 2560×2560, anomaliler 2048×2048. Girdiyi 224'e ölçeklemek tensör boyutu farkını kaldırır; çekim ölçeği ve görüş alanı farkını değil. Bu yüzden yüksek test0 sonucu salt kusur tespit başarısı olarak yorumlanmamalı.
- Kart/tasarım kimliği bulunmadığından sonuçlar yalnızca bu veri içindeki çekim alanlarına genellenebilir; yeni PCB tasarımına genelleme kanıtı değildir. Test alanları model ayarı veya eşik seçimi için kullanılmadı.

## Sonraki adım

Sonraki karşılaştırma adayı AnomalyDINO'dur; giriş, özellik ve skor üretimi farklı olduğu için tam-pipeline kıyası olarak etiketlenmeli. Ayrıca alan bazındaki skor dağılımlarını ve kusur türüne göre hataları incelemek; kaynak testteki çözünürlük-kusur ilişkisini değerlendirme sınırı olarak ele almak gerekir. Yöntem iyileştirmesi iddiası için değiştirilmemiş test alanlarında tutarlı kazanç gösterilmesi şart.

## Üretilebilirlik

- Koşucu: [`robustad_patchcore.py`](../src/pcb_anomaly/robustad_patchcore.py)
- Sabit referans kimlikleri, iki omurga ve eşlenmiş ölçümler: [`robustad-pcb-patchcore-comparison-v1.json`](../reports/robustad-pcb-patchcore-comparison-v1.json)
- Denetim: [`robustad-pcb-audit.tr.md`](robustad-pcb-audit.tr.md)
- Yerel özellik önbelleği yaklaşık 3,5 GiB'dir ve Git'e alınmaz. Önceden indirilen ImageNet ağırlıkları ve PatchCore satıcı kaynağı gereklidir.
