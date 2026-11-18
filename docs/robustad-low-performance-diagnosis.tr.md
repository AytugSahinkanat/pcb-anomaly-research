# RobustAD-PCB'de düşük başarımın olası nedenleri

**Tarih: 18 Kasım 2026**

## Ana bulgu

Kaynak eğitim ve testinde görüntü çözünürlüğü etiketle tamamen çakışıyor:

| Bölüm | Normal görüntüler | Kusurlu görüntüler |
|---|---:|---:|
| Train | 180 / 180 adet 2560×2560 | 75 / 75 adet 2048×2048 |
| Source test | 120 / 120 adet 2560×2560 | 75 / 75 adet 2048×2048 |
| Kaymış test1–test5 | normal ve kusurluların tamamı 2048×2048 | aynı boyut |

Böylece source testte görüntü boyutunu okuyup “2048 ise kusurlu” diyen basit bir karar kuralı etiketleri %100 ayırabilir. Dolayısıyla kaynak test AUROC'larının yüksek olması (%90,12–%96,35) gerçek kusur görünümünü öğrenmenin tek başına kanıtı değildir; çözünürlük/görüş alanı farkından faydalanmış olabilir.

> Bu kusursuz ayrım görüntü boyutlarının etiket dağılımından çıkarılmıştır; eğitilmiş bir model sonucu değildir. Doğrudan sebep-sonuç iddiası için çözünürlük ve görüş alanı kontrolüyle yeni deney gerekir.

## Neden hedef testte düşüyor?

1. **Referans ve hedef ölçekleri uyuşmuyor olabilir.** 16 normal referansın tamamı kaynak train'deki 2560×2560 görüntülerden seçiliyor. Kaymış testlerde normal ve kusurlu görüntüler 2048×2048. Kareleri aynı 224 veya 448 boyutuna yeniden ölçeklemek tensör boyutunu eşitler; ama PCB'nin görüntüde kapladığı alanı veya görüş alanını eşitlediğini garanti etmez.
2. **Kamera koşulları değişiyor.** Hedef bölümler aydınlatma, beyaz dengesi, dönüş, konum ve gölge/arka plan olarak ayrılmış. Örneğin aydınlatma testinde görüntü AUROC'u WideResNet50-2 için %40,1, ResNet18 için %27,8 ve AnomalyDINO için %49,7. Gölge/arka plan testinde ise ResNet18 %65,5'e çıkarken diğerleri yaklaşık %45–48'de kalıyor. Bu, tek bir model sıralamasının tüm koşullarda geçerli olmadığını gösteriyor.
3. **Kusur, tam kart görüntüsünde küçük bir sinyal.** Yerel bir çizik veya lehim kusuru bütün PCB karesine göre az piksel kaplıyor. Tam-kare görüntü skorunun en yüksek yama uzaklığıyla alınması aydınlatma, gölge, kenar ve kart hizası gibi normal değişikliklere de tepki verebilir.
4. **Normal referans bütçesi dar.** Yalnızca 16 normal kaynak görüntüsü kullanılıyor; hedef kamera koşullarını temsil eden normal örnek yok. Bu nedenle normal görünümdeki alan değişimini model için kusurdan ayırmak zorlaşıyor.
5. **Veri, hangi değişkenin etkili olduğunu ayırmaya izin vermiyor.** Metadata'da fiziksel kart kimliği, kamera oturumu veya görüş alanı bilgisi yok. Bu nedenle düşük skorun ne kadarının çözünürlük, aydınlatma, kart örneği veya başka bir faktörden kaynaklandığını kesin paylara bölemiyoruz.

## Sayıların anlattığı

Üç yöntemin kaynak test görüntü AUROC'u %90,12–%96,35 iken, beş kaymış alanın eşit ağırlıklı makrosu %37,35–%44,84. Hedef alanlarda görüntü AP'si yaklaşık %39–%43; birleşik hedef örneklerde anomali payı kabaca %41. Bu, kartı kusurlu/normal diye sıralama başarısının zayıf olduğuna işaret ediyor.

Yerelleştirme metrikleri farklı bir tablo gösteriyor: AnomalyDINO'nun piksel AP'si %7,55 ve AUPRO'su %64,07 ile daha yüksek. Bu, kusurlu bölgeleri sıralamada sinyal bulunduğunu; fakat bu sinyalin tam kartı alarm vermeye yetecek biçimde özetlenmediğini düşündürüyor. Piksel AUROC'ları pozitif piksel oranı çok düşük olduğundan tek başına yeterli değil.

## Sonraki doğrulama adımları

1. **Boyut/görüş alanı karışıklığını ayır:** fiziksel alanı veya kart sınırlarını eşleyerek normal ve anormal görüntüler için ortak görüş alanı oluştur; aynı modelleri, referansları ve hedef kareleri bu kontrollü ön işlemeyle yeniden değerlendir. Sadece yeniden boyutlandırmayı fiziksel ölçek eşitliği olarak kabul etme.
2. **Kısa bir veri kontrolü ekle:** her bölüm ve etiket için görüntü boyutu dağılımını denetimde raporla; sınıfla tam çakışma varsa kaynak test sonucunu “karışık/konfounded” diye işaretle.
3. **Alan başına örnek skorları sakla:** normal ve kusurlu puan dağılımlarını, en yüksek yanlış alarm ve kaçırılan kareleri incele. Yeni eşik veya model seçimini test alanlarında yapma.
4. **Bağımsız doğrulama edin:** fiziksel kart/oturum ID'si olan, normal ve kusurlu örnekleri benzer çözünürlük ve çekim koşullarında içeren bir test seti kur.

Bugünkü kanıt, “modeller eski olduğu için düşük” sonucunu tek başına desteklemiyor. Daha doğrudan açıklama, kaynak veri ile hedef alanların farklı dağılımları ve kaynak bölümde görüntü boyutunun etiketle tam çakışması. Bu açıklamanın büyüklüğünü ölçmek için ilk sırada kontrollü görüş alanı/ölçek deneyi gerekiyor.

Kaynak sonuç tablosu: [üç yöntem raporu](robustad-pcb-method-comparison.tr.md). Veri boyutları: [denetim raporu](robustad-pcb-audit.tr.md).
