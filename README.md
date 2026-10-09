# NewsLetter — Çok Kiracılı (Multi-Tenant) SaaS Haber Bülteni

Herkesin kendi hesabını açıp, kendi RSS kaynaklarını tanımlayıp,
kendi abonelerine kişiselleştirilmiş bir haber bülteni gönderebildiği
abonelik bazlı bir ürün.

## Mimari

```
  Kullanıcı /signup ile hesap açar
              │
              ▼
       Organization (kiracı)
        ├── Category / Source (RSS kaynakları)
        ├── NewsItem (merkezi haber havuzu — SADECE bu org'a ait)
        ├── Subscriber (kategori + opsiyonel kişisel zamanlama seçebilir)
        └── NewsletterSchedule (genel gün/saat)
              │
   ┌──────────┴──────────┐
   ▼                      ▼
Panel (web)          Zamanlanmış işler
                       - genel iş: topla + genel zamanlamalı abonelere gönder
                       - kişisel iş: her özel zamanlamalı abone için ayrı
```

**Veri izolasyonu:** Her sorgu `organization_id` ile filtrelenir
(bkz. `app/routers/panel.py` içindeki `_guard` fonksiyonu ve her route).
Bir organizasyonun verisi asla başka bir organizasyona görünmez.

## Kurulum

```bash
python -m venv venv
source venv/bin/activate  # Windows Git Bash: source venv/Scripts/activate
pip install -r requirements.txt

cp .env.example .env
# .env dosyasını doldurun: SECRET_KEY, SMTP_*, SHOPIER_* alanları
```

### Mevcut Sefine IT verisi olan kurulumlar için (ÖNEMLİ)

Daha önce tek-kiracılı sürümü kullandıysanız, uygulamayı yeniden
başlatmadan önce **mutlaka** şu migrasyonu çalıştırın (verinizi yeni
şemaya taşır, kaybetmez):

```bash
cp data/haberbotu.db data/haberbotu.db.backup   # önce yedek alın
python migrate_to_multitenant.py
```

Migrasyon size geçici bir giriş e-postası (`...@migrated.local`)
verecektir; şifreniz değişmez. Gerçek e-postanızı ayarlamak için:
```bash
python set_admin_email.py yenieposta@sirketiniz.com
```

Sıfırdan kuruyorsanız bu adımı atlayabilirsiniz — `/signup` sayfasından
doğrudan hesap açabilirsiniz.

## Çalıştırma

```bash
uvicorn app.main:app --reload
```

`http://localhost:8000/signup` üzerinden yeni bir hesap (organizasyon)
oluşturun. 14 gün ücretsiz deneme (Free plan limitleriyle) başlar.

## Shopier Kurulumu

**Önemli dürüstlük notu:** Aşağıdaki alan adları/sabitleri Shopier'in
herkese açık PHP SDK'sı ve topluluk örneklerinden derledim; hesabınıza
özel resmi API dokümantasyon sayfasına erişimim yok. Canlıya almadan
önce panelinizdeki **Entegrasyonlar > API** sayfasıyla karşılaştırın ve
**Test Modu**nu açarak uçtan uca bir deneme yapın.

1. [shopier.com](https://www.shopier.com) üzerinden şahıs hesabı açın
   (şirket/vergi levhası gerekmez, TC kimlik yeterlidir).
2. Panel → Entegrasyonlar → API → `SHOPIER_API_KEY` ve
   `SHOPIER_API_SECRET` değerlerini `.env`'e yazın.
3. Panel → Entegrasyonlar → Otomatik Sipariş Bildirimi (OSB) → Bildirim
   URL'si olarak şunu tanımlayın:
   ```
   {APP_BASE_URL}/billing/webhook/shopier
   ```
4. Fiyatları `app/plan_limits.py` içindeki `monthly_price_try`
   alanlarından ayarlayın.

**Mimari fark (Stripe'tan farklı olarak):** Shopier'de otomatik
tekrarlayan ödeme/müşteri portalı yoktur. Her ödeme tek seferliktir;
başarılı ödeme organizasyona `SUBSCRIPTION_DAYS` (varsayılan 30) gün
erişim tanır. Süre dolmadan `RENEWAL_REMINDER_DAYS_BEFORE` gün önce
hatırlatma e-postası gider; süre dolunca organizasyon otomatik olarak
Free plana düşer (bkz. `app/scheduler.py` → `check_subscriptions`,
her gün 06:00'da çalışır).

Panelde **Faturalandırma** sekmesinden plan seçip Shopier'in barındırdığı
ödeme sayfasına yönlendirilir; ödeme sonrası Shopier'in sunucu-sunucu
gönderdiği bildirim (`/billing/webhook/shopier`) planı otomatik günceller.

## Plan Limitleri

`app/plan_limits.py` içinde tanımlıdır — kaynak/abone sayısı ve kişisel
zamanlama özelliği plana göre değişir. Yeni bir plan eklemek/limit
değiştirmek için sadece bu dosyayı düzenlemeniz yeterli.

## Güvenlik Notları (SaaS için kritik)

- **SSRF koruması:** Kullanıcılar "site linki gir, RSS bul" özelliğiyle
  keyfi bir URL girebildiği için, `app/collector.py` içindeki
  `discover_feed_url` hedef adresin özel/yerel IP aralıklarına
  (localhost, iç ağ) çözümlenmediğini doğrular. Mükemmel değildir
  (DNS rebinding gibi ileri teknikler için ek bir ters proxy/allow-list
  katmanı düşünülebilir) ama temel saldırı yüzeyini kapatır.
- **API anahtarı:** `/api/*` uçları artık `X-API-Key` header'ı ister
  (panelin Faturalandırma sayfasında görünür). Kimliksiz istek reddedilir.
- **Kiracı izolasyonu:** Her route, kaynak/kategori/abone ID'sinin
  gerçekten oturumdaki organizasyona ait olduğunu sorguda doğrular.

## Docker ile Çalıştırma

```bash
cp .env.example .env   # düzenleyin
docker compose up -d --build
```

Üretimde SQLite yerine Postgres kullanmanızı öneririm (`docker-compose.yml`
içinde hazır, yorumu kaldırmanız yeterli) — çoklu kiracı ve büyüme için
daha sağlıklı.

## Ticarileştirmeden Önce Gözden Geçirin (hukuki/iş — bu bir hukuki tavsiye değildir)

- Kullanım Şartları + Gizlilik Politikası (KVKK/GDPR uyumlu)
- Fatura kesme yükümlülüğünüz (şahıs/şirket statünüze göre bir mali
  müşavire danışın)
- Kaynak sitelerin başlık/link içeriğini ücretli bir üründe kaynak
  göstermeden sunmanın telif/haksız rekabet riski — bir hukuk
  danışmanına sorulması önerilir

## Dosya Yapısı

```
app/
  main.py            FastAPI giriş noktası, migrasyon, webhook route'u
  config.py          Tüm ayarlar (.env)
  models.py          Organization, Category, Source, NewsItem, Subscriber,
                      AdminUser, NewsletterSchedule, NewsletterLog
  plan_limits.py     Free/Starter/Pro limitleri
  billing.py         Shopier ödeme formu üretimi + OSB imza doğrulama
  collector.py        RSS toplama + SSRF korumalı otomatik keşif
  newsletter.py       Organizasyon+abone bazlı kişiselleştirilmiş bülten
  scheduler.py         Organizasyon başına + abone başına zamanlama
  auth.py              E-posta ile giriş, organizasyon bağlamı
  templates_env.py     Ortak Jinja2 (marka adı global'i)
  routers/
    auth_routes.py     /login, /signup, /logout
    panel.py            Dashboard, kaynaklar, aboneler, zamanlama
    billing.py          /panel/billing, checkout, portal
    api.py              X-API-Key korumalı salt-okunur REST API
  templates/            Jinja2 + Bootstrap arayüzü

migrate_to_multitenant.py   Eski tek-kiracılı veriyi taşıyan tek seferlik script
set_admin_email.py          Migrasyon sonrası placeholder e-postayı güncelleme aracı
```
