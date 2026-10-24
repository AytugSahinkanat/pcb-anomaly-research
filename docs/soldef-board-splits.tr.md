# SolDef_AI için kart ayrımlı değerlendirme planı

## Yeni bulgu

SolDef_AI makalesi veri kümesinin altı farklı PCB'den toplandığını; her komponentin üstten, 45 derece ve aksonometrik görünümlerinin çekildiğini bildiriyor. Resmî arşivde anotasyonlu kaynak yolları `CS1`–`CS6` PCB dizinlerini taşıyor. Bu kimlikleri koruyarak aynı PCB'deki tüm anotasyonlu görüntüleri tek grupta tutan bir değerlendirme taslağı hazırladık. Kaynak: [Fontana ve diğerleri, 2024](https://doi.org/10.3390/jmmp8030117).

Arşivdeki 428 anotasyonlu görüntüden 228'i `V1` üstten görünüş konum etiketlerinde; kalan 200 görüntü `V2`/`V2.1` lehim anotasyonlarında. Bu eşleşme, makaledeki görev ve görüntü sayılarıyla tutarlı. Çalışma klasörlerine göre yapılan bu eşleştirme kaynak makale sayımlarına dayanır; V2 ile V2.1'in kendi aralarındaki açı adları ayrıca doğrulanmış değildir.

## Görevler ve kart grupları

| Görev | Görünüş ve sınıflar | Kart grupları | Görüntü | Anotasyon poligonu |
|---|---|---|---:|---:|
| Komponent konumu | `V1`; `good`, `no_good` | CS1–CS6 | 228 | 228 |
| Lehim kalitesi | `V2`, `V2.1`; `good`, `exc_solder`, `poor_solder`, `spike` | CS1, CS2, CS6 | 200 | 443 |

Konum görevi altı kartın her birini sırayla dışarıda bırakan altı katlı bölme kullanır. Lehim görevi için anotasyonu bulunan üç kartla üç katlı leave-one-board-out planı kullanılır. Aynı kartın farklı görünümleri ve parçaları hiçbir katta train/test arasında bölünmez.

Kart başına etiketli görüntü ve poligon sayıları:

| Görev | PCB | Görüntü | Sınıf başına poligon |
|---|---|---:|---|
| Konum | CS1 | 30 | good 8, no_good 22 |
| Konum | CS2 | 40 | good 20, no_good 20 |
| Konum | CS3 | 30 | good 15, no_good 15 |
| Konum | CS4 | 40 | good 18, no_good 22 |
| Konum | CS5 | 40 | good 19, no_good 21 |
| Konum | CS6 | 48 | good 32, no_good 16 |
| Lehim | CS1 | 60 | good 30, exc_solder 40, poor_solder 37, spike 26 |
| Lehim | CS2 | 56 | good 12, exc_solder 36, poor_solder 6, spike 65 |
| Lehim | CS6 | 84 | good 32, exc_solder 106, poor_solder 14, spike 39 |

Lehim görevi özellikle küçük: yalnızca üç kaynak PCB ve bazı sınıflarda az sayıda poligon var. Sonuçlar pilot ve kartlar arası genelleme için belirsiz olacaktır. Altı PCB bağımsız üretim hattı veya farklı laboratuvarlar anlamına gelmez.

## Yeniden üretme

Önce veri edinim/denetim adımlarını çalıştırıp `annotations.jsonl` üretin. Ardından:

```console
python -m pcb_anomaly.soldef_split --manifest data/soldef-audit-v1/annotations.jsonl --output data/soldef-board-splits-v1
```

`plan.json` kart, görev ve fold özetlerini; `manifest.jsonl` her görüntünün görev, fold ve train/test atamasını içerir. Çıktı klasörü varsa üzerine yazılmaz. Plan girdisinin SHA256 özeti kaydedilir. Depodaki [özet JSON](../reports/soldef-board-splits-v1.json) bu yerel çıktının ölçülebilir sayımlarını tutar; görsellerin kendisi depoya eklenmez.

## Sınırlar ve sıradaki deney

Bu yalnızca sızıntıyı önleyen bir bölme planıdır; model eğitimi veya kusur başarısı sonucu değildir. Anotasyonlu alt küme görüntülerin tamamını kapsamaz; anotasyonsuz görüntüler normal kabul edilmez. Poligon etiketleri de doğrudan görüntü düzeyi PatchCore normal/anomali etiketine çevrilemez. Konum ve lehim görevleri ayrı değerlendirilmelidir.

Bir sonraki deneyde poligonlardan görev-uyumlu ROI/crop çıkarılmalı, basit ve sabit bir görsel sınıflandırma baseline'ı kurulmalı, hiperparametre seçimi yalnızca dışarıda bırakılan PCB dışındaki gruplarla yapılmalıdır. Dış test PCB'si model veya eşik seçmek için kullanılmamalıdır. Konum ve lehim için ayrı ölçütler ve sınıf bazlı sonuçlar raporlanmalı; bu pilot sonuçlar VisA'daki kart düzeyi anomali sonuçlarıyla tek tabloda birleştirilmemelidir.
