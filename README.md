# Otomatik Shorts Yükleyici 🎬

Uzun bir videoyu **≤58 saniyelik** parçalara böler ve **4 saatte bir** (günde 6)
sıradaki parçayı otomatik olarak YouTube'a yükler. Başlık + açıklama + etiketleri
kendisi üretir. Sen sadece bir kez kurarsın, gerisi **GitHub'ın ücretsiz bulutunda**
(bilgisayarın kapalıyken bile) döner.

> **Yasal not:** Bu araç yalnızca **kendine ait / yükleme hakkına sahip olduğun**
> videolar içindir. Başkasının videosunu bölüp yeniden yüklemek telif ihlali ve
> YouTube "tekrar kullanılan içerik" ihlalidir — kanalın kapanabilir.

---

## ⚠️ Önce şunu bil: API kotası

YouTube Data API'de **1 video yüklemek = 1600 birim**, günlük ücretsiz kota
**10.000 birim** → pratikte **günde ~6 yükleme**.

- **Varsayılan ayar: 4 saatte bir = günde 6 yükleme** → kotaya TAM sığar, hata almazsın. ✅
- Daha sık istersen `.github/workflows/upload.yml` içinde cron'u `0 */3 * * *`
  yaparsın (günde 8) ama günde 2 yükleme kota aşımıyla atlanır (veri kaybı olmaz,
  sonraki çalışmada aynı parça tekrar denenir).
- İstersen Google Cloud'dan [kota artışı](https://support.google.com/youtube/contact/yt_api_form)
  isteyip 3 saate düşebilirsin (ücretsiz ama onay birkaç gün sürebilir).

---

## Kurulum — 5 adım

### 1) Google Cloud + YouTube API (tek seferlik)

1. [console.cloud.google.com](https://console.cloud.google.com) → yeni proje oluştur.
2. **APIs & Services → Library** → "YouTube Data API v3" → **Enable**.
3. **APIs & Services → OAuth consent screen** → "External" seç → uygulama adı gir →
   **Test users** kısmına **kendi Gmail adresini** ekle.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID** →
   tür: **Desktop app** → oluştur → **JSON indir**.
5. İndirdiğin dosyayı bu klasöre **`client_secret.json`** adıyla koy.

### 2) Refresh token üret (tek seferlik, kendi bilgisayarında)

```bash
pip install -r requirements.txt
python scripts/get_token.py
```

Tarayıcı açılır, Google hesabınla giriş yaparsın. Ekrana 3 değer yazılır:
`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Bunları bir yere kopyala.

### 3) Videonu parçalara böl (her yeni video için)

Uzun videonu `source/` klasörüne koy, sonra:

```bash
python scripts/split.py source/video.mp4
```

`parts/` klasörü `part_000.mp4`, `part_001.mp4`, ... ile dolar. Her parça ≤58 sn.

> **Neden parçaları push ediyoruz da videoyu değil?** GitHub tek dosya için
> **100MB** sınırı koyar; 40 dk'lık video bunu aşar ama 58 sn'lik parçalar aşmaz.

### 4) GitHub'a yükle

1. [github.com/new](https://github.com/new) → yeni repo (public olması Actions'ı
   ücretsiz sınırsız yapar).
2. Bu klasörü push et:
   ```bash
   git init
   git add .
   git commit -m "İlk kurulum"
   git branch -M main
   git remote add origin https://github.com/KULLANICI/REPO.git
   git push -u origin main
   ```
   > `client_secret.json` ve `source/*.mp4` `.gitignore`'da — **push edilmez**, doğru.
3. Repo → **Settings → Secrets and variables → Actions → New repository secret**
   ile 3 secret'ı ekle:
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`

### 5) Başlat

- Repo → **Actions** sekmesi → workflow'u **enable** et.
- **"Shorts Otomatik Yükle" → Run workflow** ile ilk yüklemeyi elle test et.
- Çalıştıysa artık **3 saatte bir** otomatik yükler. Sen hiçbir şey yapmazsın.

---

## Ayarlar — `config.json`

| Alan | Ne işe yarar |
|------|--------------|
| `segment_seconds` | Parça uzunluğu (max 59; varsayılan 58) |
| `reencode_vertical` | `true` yaparsan yatay videoyu 9:16 dikey Shorts formatına çevirir (bulanık arka plan) |
| `base_title` | Her başlıkta geçecek ana ifade |
| `series_name` | Doluysa başlığa "Seri Bölüm 1/2/3..." ekler |
| `tags` | Etiket listesi |
| `privacyStatus` | `public` / `unlisted` / `private` |
| `categoryId` | 24 = Eğlence, 22 = İnsanlar/Blog, 10 = Müzik |

Başlıklar `scripts/metadata.py` içindeki **hook** ve **hashtag** havuzlarından
rotasyonla üretilir — buradan kendi viral kalıplarını ekleyebilirsin.

---

## Sık sorulanlar

**Yeni bir video eklemek istersem?**
`split.py`'yi yeni videoyla çalıştır, `state/progress.json` içindeki `next_index`'i
`0` yap, commit + push et.

**Video "Short" olarak mı görünecek?**
Süre ≤60 sn olduğu ve başlıkta `#shorts` bulunduğu için evet. Dikey (9:16) olması
erişimi artırır → `reencode_vertical: true` önerilir.

**Filigran var mı?**
Hayır. Kendi videonu kesip yüklüyoruz, hiçbir yere filigran eklenmiyor.

**Bir parça yüklenemezse?**
`next_index` ilerlemez; bir sonraki çalışmada aynı parça tekrar denenir. Kayıp olmaz.

---

## Dosya yapısı

```
config.json              # tüm ayarlar
requirements.txt
scripts/
  split.py               # videoyu parçalara böler (yerelde, tek sefer)
  get_token.py           # refresh token üretir (yerelde, tek sefer)
  metadata.py            # başlık/açıklama/etiket üretir
  upload.py              # sıradaki parçayı yükler (Actions çalıştırır)
state/progress.json      # kaldığı yeri tutar
parts/                   # kesilmiş parçalar (buraya push edilir)
source/                  # uzun kaynak video (push EDİLMEZ)
.github/workflows/upload.yml   # 3 saatte bir tetikleyen zamanlayıcı
```
