# Makale hazırlık değerlendirmesi

Son değerlendirme: 12 Kasım 2026

## Kısa karar

**Makale taslağı sürdürülebilir.** RobustAD-PCB'de üç başlangıç yöntemi aynı beş referans seçimiyle karşılaştırıldı: eşit-bellekli WideResNet50-2 ve ResNet18 PatchCore ile farklı, daha büyük bellek kullanan AnomalyDINO tam hattı. Kaymış alan makro görüntü AUROC'ları %44,84/%37,35/%43,52; DINO piksel AP ve AUPRO'da daha yüksek, fakat hiçbir model görüntü tespitinde hedef alan ortalaması %50'yi aşmadı. Bu, domain-shift ve yerelleştirme/görüntü tespiti ayrışması kanıtıdır; güçlü, doğrulanmış kusur tespit çözümü değildir. **Gönderime hazır değil:** özgün yöntem katkısı ve yeni kart/oturumlarda board-held-out test henüz yok. RobustAD fiziksel kart kimliği sağlamadığı için board-held-out test sayılamaz.

En uygun ilk kapsam, yeni bir model önerdiğini söyleyen yöntem makalesi değil; PCB1–PCB4 üzerindeki az referanslı anomalide ön işleme ve yama belleği eşitliğinin omurga karşılaştırmalarına etkisini, işletim noktasını ve sınırlarını inceleyen kontrollü deney makalesidir. Yayın şansı hedef dergi/konferansın katkı ölçütlerine ve eksik kanıtların tamamlanmasına bağlıdır.

## Şu anda yazılabilir kanıt

| Bölüm | Hazır içerik | Durum |
|---|---|---|
| Problem ve kapsam | PCB'de normal örneklerle kusur adayı sıralama; görüntü düzeyi anomali tespiti ile ROI kusur türü sınıflandırmasını ayırma | Yazılabilir |
| Veri ve protokol | VisA PCB1–PCB4 resmi ayrımı; normal eğitimden ayrılan kalibrasyon; beş referans seçimi; veri/maske denetimi | Büyük ölçüde yazılabilir; bağımsız fiziksel kart kimliği bilinmiyor |
| Kontrollü PatchCore karşılaştırması | 2 omurga × 2 ön işleme × 2 yama belleği × 5 referans seçimi; 160 değerlendirme; aynı 802 test görüntüsü | Ana sonuç olarak yazılabilir; betimsel ve test kümesine özgü olduğu açıkça belirtilmeli |
| Piksel düzeyi kusur yerelleştirme | Eşit 19,598 MiB yama bankası, ortak merkez kırpma, 4 kategori × 5 referans seçimi; piksel AUROC/AP ve AUPRO | Tamamlandı; test görüntüleri önceki çalışmalarda kullanılmış olduğundan doğrulayıcı yeni test değildir |
| AnomalyDINO ve eşlenmiş referans sayılı PatchCore | VisA PCB1–PCB4 ve RobustAD-PCB'de görüntü/piksel kıyası, bellek ve domain-split sonuçları | Tamamlandı; tam yöntem adımları farklı, bağımsız kart testi değil |
| RobustAD kusur türü hata analizi | İki eşit-bellekli PatchCore hattında `Missing Component`, `Soldering Melt`, `Scratch` görüntü sıralaması | Keşifsel olarak tamamlandı; DINO alt grubu ve görsel hata incelemesi eksik |
| İşletim noktası ve hata analizi | Kalibrasyon normal örneklerinden eşik; ölçülen test yanlış alarmı ve kusur yakalama; sık kaçan kusurlar | Yazılabilir; yeni bağımsız sonuç gibi sunulmamalı |
| Ek PCB verileri | PCB-AoI ROI tür sınıflandırması ve zayıf tam-kutu tespit pilotu; SolDef_AI kart grubu ROI sonuçları | Ayrı görev ve sınırlı kanıt olarak ek/bağlam bölümünde kullanılabilir |
| Yönelim/çözünürlük | Komponent komşuluğu ve özellik tutarlılığı ölçümleri; dört-yön ortalaması çözünürlük kararlılığını genel olarak artırmadı | Yalnızca temsil sağlamlığı ön çalışması; gerçek kusur başarımı iddiası değildir |

Mevcut büyük yama bankası ve ortak merkez kırpmada makro görüntü AUROC'u ResNet18 için %94,84, WideResNet50-2 için %95,73. Beş referans seçimi arasındaki eşlenmiş fark 0,89 ± 0,28 yüzde puanıdır. Küçük bankada fark 3,31 ± 1,13 puandır. Bu, omurga kazancının bellek ve ön işleme ayarlarına bağlı olduğunu gösteren ana bulgudur; model ağırlıklarının toplam RAM'i eşitlenmemiştir.

Aynı merkez-kırpma ve büyük-bank koşulunda makro piksel AUROC'u %97,86 ± 0,08 ve %98,52 ± 0,04; piksel AP'si %44,65 ± 0,33 ve %49,52 ± 0,45; AUPRO'su (FPR≤0,30) %83,16 ± 0,41 ve %86,62 ± 0,25'tir (ResNet18 / WideResNet50-2). Piksel AP PCB2'de sırasıyla yalnızca %15,90 ve %18,53; dolayısıyla yüksek AUROC her kusur bölgesini iyi bulduğumuzu göstermez. Protokol ve kategori sonuçları [yerelleştirme raporunda](visa-localization.tr.md), seed başına sayılar [JSON çıktısında](../reports/visa-localization-v1.json).

AnomalyDINO ve aynı 16 referans görüntüsüyle WideResNet50 PatchCore tam-pipeline karşılaştırması tamamlandı. Makroda DINO'nun görüntü AUROC/AP'si %95,18/%95,85, piksel AUROC/AP'si %96,25/%53,76, AUPRO'su %88,56; PatchCore'un değerleri sırasıyla %91,92/%92,06, %98,01/%47,30 ve %82,92'dir. DINO bankası yaklaşık 94,5–108,9 MiB; PatchCore bankası 4,90 MiB. Beş eşlenmiş referans seçimiyle aynı test kümesi tekrar kullanıldığı için sonuçlar yeni kartlarda belirsizlik aralığı değildir. Ayrıntı: [karşılaştırma raporu](visa-16shot-comparison.tr.md).

## Gönderimden önce gerekli işler

1. **Dış domain-shift kıyası:** RobustAD'da üç yöntem ve yinelenen test4 karesi duyarlılığı tamamlandı. Alan ve kusur türü bazında hataları analiz et; eşikli çalışma noktası gerekirse yalnızca önceden ayrılmış kaynak-normal kalibrasyonuyla hesapla. Test alanlarını yöntem veya eşik seçmek için kullanma. Bu veri yeni PCB tasarımına genelleme değerlendirmesi değildir.
2. **Test kullanım sınırı:** VisA testinde bugüne kadar yapılan keşif ve ayar kararlarını deney günlüğünde listele. Sonuçların tamamını mevcut benchmark betimlemesi olarak sabitle. Yeni katkı veya yöntem seçimi için testte yeniden ayar yapma; bu iddialar için kart/oturum bazında ayrılmış yeni veri gerekir.
3. **Bağımsız lehim doğrulaması:** en iyi aday LightJoint-D makalesi 93 PCB görüntüsü ve 1.804 lehim ROI'si bildiriyor; veri yalnız yazardan istek üzerine. Tam kartlar, ROI-kart eşlemesi ve lisans bilgisi gelmeden grup dışarıda test kurulamaz. Hazır İngilizce talep taslağı: [LightJoint-D veri isteği](lightjoint-data-request-draft.en.md). Mesaj gönderilmedi.
4. **Maliyet ve yeniden üretim:** görüntü başına çıkarım süresi, tepe RAM/VRAM ve yama bankası belleğini ayrı ölç; ortam, ağırlık sürümü/hash'i, seed'ler, eşik seçimi, metrik sürümleri ve analiz komutlarını yaz. Aynı testteki beş referans seçiminin standart sapmasını yeni görüntülere genelleme güven aralığı diye adlandırma.
5. **Literatür ve iddia:** makale taramasını sistematikleştir, AnomalyDINO ve 2025–2026 denetim/değerlendirme çalışmalarını kapsa; yalnız ölçülen iddiaları bırak. Yeni yöntem katkısı çıkmazsa makaleyi tekrarlanabilir kontrollü deney ve hata analizi olarak konumlandır.

RobustAD kusur türü alt analizi, kusura göre model sıralamasının değiştiğini gösteriyor: eksik komponentte ResNet18 daha yüksek makro görüntü AUROC verirken, lehim erimesi ve çizikte WideResNet50-2 öne çıktı. Bu, iki PatchCore omurgası için sınırlı ve eşiksiz bir alt analizdir; DINO tür alt analizi tamamlanmadan üç yöntem için kusur bazında karşılaştırma yazılmamalı. Ayrıntı [RobustAD kusur türü raporunda](robustad-pcb-defect-type-error-analysis.tr.md).

## Yazım kararı

Giriş, problem tanımı, veri, yöntem ve VisA deney sonuçları şimdi taslaklanabilir. Sonuçlar için şimdiki makale iddiası şu sınırda tutulmalı: **Bu çalışma, VisA'nın PCB alt kümelerinde beş referans seçimi üzerinde PatchCore omurgası, ön işleme ve yama belleği etkileşimlerini ölçüyor; elde edilen sıralama sabit test kümesine ve kullanılan kalibrasyona bağlı.** Bu iddia üretim hattı genellemesi veya yeni kusur tespit yöntemi anlamına gelmez.

Piksel ölçümleri ve aynı 16 referanslı AnomalyDINO–PatchCore karşılaştırması taslağa eklendi. En önemli eksik, daha önce incelenmemiş ve kart/oturum bazında ayrılmış bağımsız kusur verisidir. LightJoint-D verisi için yazara henüz ulaşılmadı; bu sırada mevcut bulgular ve sınırlılıklar taslakta yazılabilir.

İlk İngilizce makale metni [ayrı taslakta](paper-draft.en.md) açıldı. Bu dosya çalışma taslağıdır; gönderim öncesi işaretli deneyler ve literatür taraması tamamlanmalıdır.
