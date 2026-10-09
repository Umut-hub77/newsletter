"""
Merkezi uygulama ayarları.
Tüm değerler ortam değişkenlerinden (.env) okunur; kod içine sabit
kimlik bilgisi ya da kaynak YAZILMAZ. Kaynaklar artık veritabanında
tutulur (bkz. models.Source) ve panelden yönetilir.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Veritabanı ---
    # Varsayılan: SQLite (kurulum gerektirmez). Kuruma göre değiştirin:
    # postgresql+psycopg2://kullanici:sifre@host:5432/haberbotu
    DATABASE_URL: str = "sqlite:///./data/haberbotu.db"

    # --- Uygulama / oturum ---
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    APP_TIMEZONE: str = "Europe/Istanbul"
    APP_BRAND_NAME: str = "NewsLetter"
    APP_BASE_URL: str = "https://newsletter-phqk.onrender.com"
    TRIAL_DAYS: int = 14

    # --- Shopier (ödeme) ---
    # PAT sisteminde otomatik ödeme linki oluşturmanın doğrulanmış bir REST
    # API dokümantasyonu bulunamadığı için (bkz. sohbet), şu anki akış:
    # panelde manuel oluşturduğunuz sabit ürün linklerine yönlendirme +
    # sizin (platform sahibi) manuel plan onayı. SHOPIER_API_KEY/SECRET
    # alanları ileride otomatik entegrasyon netleşirse kullanılmak üzere
    # dursun; şu an aktif akışta kullanılmıyor.
    SHOPIER_API_KEY: str = ""
    SHOPIER_API_SECRET: str = ""
    SHOPIER_WEBSITE_INDEX: str = "1"
    SHOPIER_MODULE_VERSION: str = "1.0.4"

    # Her plan x süre kombinasyonu için Shopier panelinde oluşturduğunuz
    # sabit ürün linkleri (8 adet). Süre eklemek/çıkarmak isterseniz
    # app/plan_limits.py'deki DURATIONS sözlüğünü de güncelleyin.
    SHOPIER_STARTER_30_URL: str = ""
    SHOPIER_STARTER_90_URL: str = ""
    SHOPIER_STARTER_180_URL: str = ""
    SHOPIER_STARTER_365_URL: str = ""
    SHOPIER_PRO_30_URL: str = ""
    SHOPIER_PRO_90_URL: str = ""
    SHOPIER_PRO_180_URL: str = ""
    SHOPIER_PRO_365_URL: str = ""

    RENEWAL_REMINDER_DAYS_BEFORE: int = 3

    # --- Platform sahibi (siz) ---
    # Bu e-postayla giriş yapan kişi /owner panelini görebilir: tüm
    # organizasyonları listeler, Shopier'den gelen ödemeyi manuel onaylar.
    PLATFORM_OWNER_EMAIL: str = "celebiumut97@gmail.com"

    # --- SMTP (Gmail veya kurumsal sağlayıcı) ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "newslettermedias@gmail.com"
    SMTP_PASSWORD: str = "qxkulcucjpjmclob"
    MAIL_FROM: str = "newslettermedias@gmail.com"
    MAIL_FROM_NAME: str = "NewsLetter"

    @property
    def clean_smtp_password(self) -> str:
        return (self.SMTP_PASSWORD or "").strip(' "\'')

    @property
    def clean_smtp_user(self) -> str:
        return (self.SMTP_USER or "").strip(' "\'')

    @property
    def clean_mail_from(self) -> str:
        return (self.MAIL_FROM or self.clean_smtp_user).strip(' "\'')

    # --- Bülten içeriği ---
    # Kaynak/kategori artık organizasyon değil, PLATFORM GENELİ (siz
    # /owner panelinden yönetirsiniz). Toplama bu periyotta bir kez çalışır,
    # tüm organizasyonlar aynı ortak havuzdan beslenir. Gönderim GÜNÜ ve
    # SAATİ ise her organizasyonun kendi panelindeki "Zamanlama"
    # sekmesinden veritabanında yönetiliyor.
    COLLECT_INTERVAL_MINUTES: int = 30
    NEWSLETTER_LOOKBACK_HOURS: int = 24
    ARTICLES_PER_CATEGORY: int = 6

    RSS_TIMEOUT_SECONDS: int = 10


settings = Settings()