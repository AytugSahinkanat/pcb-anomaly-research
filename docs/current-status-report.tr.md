# Proje güncel durum raporu

**Tarih: 18 Kasım 2026**

## Kısa durum

PCB anomalisi üzerine tekrarlanabilir bir araştırma altyapısı ve birden çok veri kümesinde başlangıç sonuçları var. **Makalenin sonuçları yazılabilir; çalışma henüz gönderime hazır değil.** Şu an en güçlü bulgu, model başarısının çekim koşuluna ve kusur türüne göre değişmesi. Mevcut deneyler yeni PCB kartlarına genellemeyi kanıtlamıyor.

## Tamamlanan ana deney

RobustAD-PCB’de 16 normal referansla, aynı beş referans seçimi kullanılarak üç yöntem karşılaştırıldı. test1–test5'in eşit ağırlıklı makro ortalamaları:

| Yöntem | Görüntü AUROC | Görüntü AP | Piksel AUROC | Piksel AP | AUPRO |
|---|---:|---:|---:|---:|---:|
| WideResNet50-2 PatchCore | 44,84% | 43,17% | 87,16% | 5,42% | 48,84% |
| ResNet18 PatchCore | 37,35% | 40,60% | 85,71% | 5,71% | 41,57% |
| AnomalyDINO tam hattı | 43,52% | 39,04% | **91,97%** | **7,55%** | **64,07%** |

**Yorum:** DINO kusur bölgelerini sıralamada daha iyi sonuç verdi; fakat görüntü düzeyinde kusurlu kartları güvenilir biçimde ayıramadı. Üç yöntemin de kaymış alan görüntü AUROC ortalaması %50'nin altında. DINO sonucu yalnızca omurga kıyası değildir: daha yüksek çözünürlük, yönelim artırması ve daha büyük özellik belleği kullanır (yaklaşık 80 MiB; PatchCore 4,90 MiB).

## Kusur türü analizi

İki PatchCore yöntemi için kusurlu görüntüleri aynı alandaki normal görüntülere karşı ayrıca sıraladık. Sonuç, tek bir genel kazanan olmadığını destekliyor:

| Kusur | WideResNet50-2 AUROC / AP | ResNet18 AUROC / AP |
|---|---:|---:|
| Eksik komponent | 46,86% / 30,55% | **49,80% / 33,77%** |
| Lehim erimesi | **40,72%** / 19,54% | 30,33% / 18,34% |
| Çizik | **45,75% / 23,82%** | 36,47% / 20,89% |

Bu alt analiz keşifseldir ve DINO'yu kapsamıyor. Beş referans seçiminin sapması, yeni kartlardan gelen istatistiksel belirsizlik değildir. Piksel AP, kusur piksellerinin ve örneklerin azlığı nedeniyle düşük kalabilir.

## Henüz kanıtlanmayanlar

- AnomalyDINO'nun kusur türüne göre alt sonuçları tamamlanmadı; buna yönelik tekrar CPU çalışması kesildi.
- Bağımsız, fiziksel kart/üretim oturumu bazında ayrılmış bir test yok. RobustAD-PCB metadata'sında kart kimliği bulunmuyor.
- Bu kıyas için seçilmiş ve testten bağımsız sabit bir çalışma eşiği yok; otomatik kabul/red başarımı ölçülmüş değil.
- Bulgular üretim hattında yanlış alarm, çevrim süresi veya yeni tasarıma genelleme kanıtı değildir.
- Makale literatür taraması sistematik biçimde tamamlanmadı; özgün yöntem katkısı gösterilmedi.

## Başarım neden düşük olabilir?

Denetimde kaynak train/test normal karelerinin tamamının 2560×2560, kusurlu karelerin tamamının 2048×2048 olduğu görüldü. Bu nedenle kaynak testte çözünürlük tek başına etiketleri ayırabiliyor; yüksek kaynak AUROC'ları gerçek kusur öğrenmesini tek başına kanıtlamıyor. Kaymış test1–test5'te tüm görüntüler 2048×2048 ve kamera/çekim koşulları da değişiyor.

Bu şüpheyi sınamak için tüm kareleri eğitim-normal bir şablona hizalayıp sabit kart ROI'siyle iki PatchCore omurgasını tekrar çalıştırdım. Aynı beş referans seçiminde hedef alan görüntü AUROC'u WideResNet50-2'de %44,84'ten %62,79'a, ResNet18'de %37,35'ten %51,87'ye çıktı; piksel AP'si de yaklaşık 10–13 puan arttı. Bu, görünüm hizalamasının yardımcı olduğunu destekliyor; fakat hizalama, arka plan, kırpım ve ölçek katkılarını ayırmıyor. Hizalama için 16 puanlama görüntüsüne ek bir normal şablon kullandım. Sonuç keşifseldir. [Hizalama deneyi](robustad-registered-board-experiment.tr.md) ve [düşük başarım teşhisi](robustad-low-performance-diagnosis.tr.md).

## Şu anki konum ve plan

1. Hizalama, ROI crop ve ek eğitim-normal şablonunun katkılarını ayrı ablation'larla ayır; hata görsellerini karşılaştır.
2. Model/parametre seçimini test alanlarına göre yapma. Gerekirse eşik protokolünü eğitim verisinden ayrılmış normal kalibrasyon örnekleriyle önceden sabitle.
3. Bağımsız kart veya oturum kimliği olan kusurlu veri bul; mümkün değilse makale kapsamını açıkça tek veri kümesi üzerindeki kontrollü karşılaştırma ve sınır analiziyle sınırla.
4. İngilizce makale taslağında metriklerin yanında bellek, kusur yoğunluğu, örnek sayısı ve veri sınırlamalarını raporla. DINO hizalı kusur alt analizi hâlâ tamamlanmalı.

## GitHub durumu

Son bilinen başarılı gönderim `0bb921f` (`Explain RobustAD PCB domain-shift results`), 18 Kasım 2026'da `main` dalına yapıldı. Bu hizalama deneyi ve rapor henüz commit edilip gönderilmedi. Çalışma alanında ayrıca ilgisiz bir not defteri ve geçici sunum derleme klasörü bulunuyor.

## Ayrıntılı kaynaklar

- [RobustAD üç yöntemli karşılaştırma](robustad-pcb-method-comparison.tr.md)
- [Düşük başarım nedenleri ve doğrulama planı](robustad-low-performance-diagnosis.tr.md)
- [Kusur türü hata analizi](robustad-pcb-defect-type-error-analysis.tr.md)
- [Makale hazırlık değerlendirmesi](paper-readiness.tr.md)
- [İngilizce makale taslağı](paper-draft.en.md)
- [Birleşik makine-okunur sonuçlar](../reports/robustad-pcb-method-comparison-v1.json)
- [Kart hizalama karşılaştırma JSON'u](../reports/robustad-pcb-registered-board-comparison-v1.json)
