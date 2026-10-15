# Kuo arşivinin veri denetimi

15 Ekim 2026 tarihinde kullanıcının Downloads klasöründeki `pcb_wacv_2019.zip` doğrudan okundu. Arşiv değiştirilmedi veya açılarak kaynak dosyaların üzerine yazılmadı. Bu denetim, görüntülerin normal veya kusurlu olduğunu doğrulamaz.

SHA256: `d24cf0e3688a5c7a4d827b2363a2a5d6e3c88c189203876a9e9ef3ab6f45b01a`

| Ölçüm | Sayı |
|---|---:|
| XML | 47 |
| Eşleşen görüntü | 47 |
| Tüm nesne anotasyonları | 18.201 |
| Metin anotasyonları | 10.185 |
| Komponent anotasyonları | 8.016 |
| Komponent sınıfları | 31 |
| Dosya adından çıkarılan aday kart grubu | 29 |
| Geçersiz kutu / boyut uyuşmazlığı | 0 / 0 |
| Eşleşen görüntülerde SHA256 tekrarı | 0 |

Arşivin README dosyası da yaklaşık 60 bin komponent bildiriyor; ancak bu arşivin XML sayımı bu sayıyı doğrulamıyor. 8.016 sayısı XML nesne kayıtlarıdır; bağımsız fiziksel komponent veya hatasız örnek sayısı değildir. SHA256 yalnız birebir dosya tekrarını denetler; aynı sahnenin farklı çekimlerini veya yakın kopyalarını bulmaz.

## Önceki kodda kayıp nedenleri

`ATTIOT_Top` ve `HackRF` görüntülerinin uzantısı `.JPG`. Eski Colab kodunun `glob('*.jpg')` seçimi bu ikisini atlıyor. Yeni eşleme büyük/küçük harf farkını tolere ediyor ve XML içindeki filename alanını kullanıyor. Hem JPG hem PNG olan klasörlerde ilk dosyayı rastgele seçmiyor. ArduinoMega_Top XML'i PNG'yi işaret ediyor; yeni eşleme bunu izliyor.

Tırnak içindeki `electrolytic capacitor`, `test point`, `emi filter`, `resistor network` gibi sınıflar birer tam sınıf adı. Etiket ayrıştırması tırnakları dikkate alıyor. `text` ve `component text` görüntü üstü yazılardır; komponent tablosundan ayrılıyor. RefDes kalan metin olarak korunuyor ve başka karttaki aynı adla özdeşleştirilmiyor.

Aynı görüntüde aynı ham etiketi tekrar taşıyan 1.718 ek komponent kaydı var. Bunları hatalı anotasyon varsayıp silmedik. Eski yöntemde `kart_etiket.png` dosyasına yazmak aynı adlı kayıtların üzerine yazıyor. Yeni manifestte her anotasyonun kimliği `görüntü_id:anotasyon_sırası`; isimleri aynı olsa da kayıtlar korunuyor.

Eski uzantı filtresi ve dosya adı üzerine yazma davranışının dosya üretmeden simülasyonu 7.489 komponent kaydından 6.154 benzersiz dosya adı kaldığını gösterdi. Notebooktaki 6.149 ile kalan 5 kayıt farkı bu denetimle açıklanmadı; eski çalışma klasöründeki kırpmalar olmadan birebir eşitlik iddia edilmiyor.

## Manifest ve bölme durumu

`data/audit-v1/manifest.jsonl` bütün nesneleri, kaynak XML/görüntüyü, ham etiketi, sınıfı, yüz bilgisini ve kutuları içeriyor. Orijinal VOC kutusu ayrıca korunuyor. NumPy/Pillow kırpma için kutular VOC'nin 1 tabanlı dahil sınırlarından 0 tabanlı yarı açık sınırlara dönüştürüldü. Geçersiz kutular sessizce kesilmiyor. Mevcut 8.016 komponentin tamamı bu geometrik kontrollerden geçti; görsel kutu kalitesi ayrıca örneklenerek incelenmeli.

Anomali `label` alanı `null`, `label_source` alanı `unlabeled`. Verinin tümünü normal varsayan etiket yazılmadı.

`splits.json` seed=42 ile tekrarlanabilir bir **taslak** bölme içeriyor. `_Top`, `_Bottom` ve numaralı yüz son ekleri aynı aday kart grubuna bağlanıyor. Bu isim kuralı fiziksel kart veya tasarım ailesi kimliğini kesinleştirmez. Üretim deneyi öncesi kaynak görüntülerde grup ve yakın kopya kontrolü yapılmalı; bu bölmelerle şimdiden başarı iddiası kurulamaz.

Sınıf kapsaması `audit.json` içindeki `class_split_counts` alanında raporlanıyor. Örneğin `battery` yalnız testte, `diode zener array` yalnız kalibrasyonda. Bu sınıflara referans bankası olmadan skor üretilemez. `resistor jumper` referansında yalnız bir örnek var; k=3 için yetersiz. Yeni çalışma nadir sınıfları sessizce düşürmek yerine desteklenen sınıfları ve abstention oranını raporlamalı.

## Yeniden üretme

Depoyu kurduktan sonra yeni bir çıktı klasörü seçerek:

```powershell
python -m pcb_anomaly.data 'C:/Users/User/Downloads/pcb_wacv_2019.zip' --output data/audit-v2
python -m unittest discover -s tests -v
```

Komut mevcut çıktı klasörünün üzerine yazmaz. `audit.json`, `images.json`, `manifest.jsonl`, `splits.json` üretir. Ham veri ve yerel manifestler `.gitignore` altında; bu özet ve kod depoya dahil edilebilir.

Doğrulama: 13 birim test geçti. Testler tırnaklı sınıfları, `.JPG` eşlemesini, belirsiz eşleşmenin reddini, VOC sınırlarını, aynı adlı komponentlerin korunmasını, deterministik bölmeleri ve değerlendirme kontrollerini kapsıyor. Bu testler kusur tespit başarısı ölçmez.

Sonraki aşama, aday kart gruplarının görsel kontrolü ve manifestten benzersiz kimlikle crop/özellik üretimidir. Gerçek kusur benchmarkı için VisA hattı ayrı kurulmalı.
