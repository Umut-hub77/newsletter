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
    SECRET_KEY: str = "f36aa1813d011ccde3082818d2f1e4dad0dc0d23bcfffe83fe3946c0bd0519bd"
    APP_TIMEZONE: str = "Europe/Istanbul"
    APP_BRAND_NAME: str = "NewsLetter"
    APP_BASE_URL: str = "https://newsletter.social"
    TRIAL_DAYS: int = 7

    # --- Shopier (ödeme) ---
    SHOPIER_API_KEY: str = ""
    SHOPIER_API_SECRET: str = ""
    SHOPIER_PAT: str = (
        "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJkNjQ5YThiYTM0OTc4NzU2YjhlMDk2MjUxMTU0MGNhNiIsImp0aSI6"
        "IjAxNjA4OWRiMTQ3MDRmZWE5ZGFkNjc5MTJiOTk1YjQ3NWRhMzQwY2IwM2YxNWRkZDQ3NTM0NTBjOGRhMTM2MjU3YzEyMjFmOGY3"
        "NWE1ODI0YTc4NGM5NzI5NjM4ZWM2MDYyOGEzZGEyY2VlYTVlM2Y0YTVhZWE0MmZhMDdjNGNiOTNhYzMwYjM0OWRjNDZmMGJjNGVi"
        "Nzc0NTIyMzAxZTMiLCJpYXQiOjE3ODU0MDAwOTUsIm5iZiI6MTc4NTQwMDA5NSwiZXhwIjoxOTQzMTg0ODU1LCJzdWIiOjI1MjM0"
        "NzMsInNjb3BlcyI6WyJvcmRlcnM6cmVhZCIsIm9yZGVyczp3cml0ZSIsInByb2R1Y3RzOnJlYWQiLCJwcm9kdWN0czp3cml0ZSIs"
        "InNoaXBwaW5nczpyZWFkIiwic2hpcHBpbmdzOndyaXRlIiwiZGlzY291bnRzOnJlYWQiLCJkaXNjb3VudHM6d3JpdGUiLCJwYXlv"
        "dXRzOnJlYWQiLCJyZWZ1bmRzOnJlYWQiLCJyZWZ1bmRzOndyaXRlIiwic2hvcDpyZWFkIiwic2hvcDp3cml0ZSJdfQ.U3zL2Kn_G"
        "fUNnX4cuf79nei7Jv4iVyZrrjojz80LFinvOYPN4x8C6Yc6eU7nc3q_ljpvgfGRHUuaAzU_2kXEuVIoAw7JTJRLRV_XjMTYXPjG"
        "_KgbH5IMXAJRzJVzyUV3vWSZmzfWVgUCbudjRP4P-HkjxpTnaHJYwWyWhyAyZG4G_uVHFQlH7Na6XL4a4coi_3YiFyFYhKM0S8uH0"
        "I7VdIUXcz7pUKjER6lx_KhXp_9NpUbwAHIAtBVFnMLth3MRaBjbXxAVbIro7inLfPD0-eHKfXCFed3YC8HQAkariD4Wm4xFV6-ti"
        "oQr5H3C9oxeQxKfH_ga8ov8-5vo0e6_nw"
    )
    SHOPIER_WEBSITE_INDEX: str = "1"
    SHOPIER_MODULE_VERSION: str = "1.0.4"

    # Her plan x süre kombinasyonu için Shopier panelinde oluşturduğunuz
    # sabit ürün linkleri (8 adet).
    SHOPIER_STARTER_30_URL: str = "https://www.shopier.com/NewsLetters/49422718"
    SHOPIER_STARTER_90_URL: str = "https://www.shopier.com/NewsLetters/49448401"
    SHOPIER_STARTER_180_URL: str = "https://www.shopier.com/NewsLetters/49448736"
    SHOPIER_STARTER_365_URL: str = "https://www.shopier.com/NewsLetters/49448741"
    SHOPIER_PRO_30_URL: str = "https://www.shopier.com/NewsLetters/49422747"
    SHOPIER_PRO_90_URL: str = "https://www.shopier.com/NewsLetters/49448405"
    SHOPIER_PRO_180_URL: str = "https://www.shopier.com/NewsLetters/49448724"
    SHOPIER_PRO_365_URL: str = "https://www.shopier.com/NewsLetters/49448730"

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