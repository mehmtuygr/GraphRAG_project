# Yerel GraphRAG değerlendirmesi

Bu pilot, kitaba dayalı cevap kalitesini karşılaştırır. 12 İngilizce soru dört yöntemle çalıştırılır: Basic, Local, Global (tam raporlar, düzey 0) ve DRIFT (düzey 0). Soru başına tek deneme vardır. Bu küçük ve elle seçilmiş set genel bir doğruluk yüzdesi veya istatistiksel üstünlük kanıtı değildir.

## Çalıştırma

```powershell
.\.venv\Scripts\python.exe -B tests/run_eval.py
.\.venv\Scripts\python.exe -B tests/summarize_eval.py
```

İlk komut yerel Ollama modellerini kullanır; ikinci komut yalnızca kayıtlı cevapları ve indeksi okur. Sonuçlar `eval/results/pilot-v1/` içindedir. Her tamamlanan sorgu ayrı kaydedilir; yeniden çalıştırma mevcut sonuçları atlar. Başarısız/zaman aşımına uğramış kayıtlar da saklanır ve otomatik yeniden çalıştırılmaz. Yeni bir deney için farklı `--out` kullanılır. Tam kitap indekslenmez.

Soru seti: `tests/eval_questions.json`. Beklenen cevap noktaları ve kaynak dosyaları sonuçlar görülmeden hazırlanmıştır. Referanslar PDF'den çıkarılmış sayfa işaretli metne dayanır; PDF sayfası ile basılı sayfa numarası farklı olabilir. İki cevaplanamaz soru sentetik negatif kontroldür.

## Değerlendirme kuralları

- **Doğruluk (0–2):** 0 = yanlış/cevap yok; 1 = önemli hata veya aşırı genelleme içeren kısmen doğru cevap; 2 = esaslı teknik hata olmadan doğru cevap. Cevaplanamaz sorularda açık ve uydurmasız çekimserlik 2 alır.
- **Tamlık (0–2):** 0 = beklenen noktaların hiçbiri; 1 = bazıları; 2 = tüm temel noktalar. Eş anlamlı ifadeler kabul edilir; kelime eşleşmesiyle puan verilmez.
- **Kaynak desteği (0–2):** 0 = temel iddialar desteksiz/yanlış kaynaklı; 1 = kısmi destek veya eksik atıflar; 2 = temel iddialar gösterilen kaynaklarla destekli. Cevaplanamaz soruda iddia üretmeyen doğru çekimserlik için uygulanmaz (null).
- Bir ID'nin indekste bulunması, o ID'nin iddiayı desteklediği veya gerçekten sorguya getirildiği anlamına gelmez. Otomatik ID denetimi ile anlamsal kaynak kontrolü ayrıdır.
- İşlemin başarıyla bitmesi cevap kalitesini kanıtlamaz. Hata ve süre aşımı ayrı raporlanır.

Puanlar `review.json` içinde gerekçeleriyle tutulur. Değerlendirme Codex'in kitap metni ve cevaplar üzerindeki incelemesidir; bağımsız uzman/human değerlendirmesi veya kör değerlendirme değildir. Yerel model kendi cevaplarını puanlamaz. Kaynak raporlarının kendileri de model tarafından üretilmiştir; kitapla çelişkileri ayrıca dikkate alınır.

## Tekrarlanabilirlik sınırları

48 sorgu sırayla, aynı mevcut ayarlarla çalışır. İstek başına 900 saniye sınırı vardır. Modellerin sıcak/soğuk yüklenmesi, mevcut önbellek, arka plan yükü ve DRIFT araştırma değişkenliği kontrol edilmez. Süreler bu çalıştırmanın gözlemleridir; gecikme garantisi değildir. İngilizce sonuçlar Türkçe soru başarısını ölçmez. Soruya eklenen ortak kısa cevap/kaynak talimatı günlük arayüz kullanımından farklı olabilir. Çalışma yapılandırması, paket sürümü ve soru seti çıktı klasörüne kaydedilir.
