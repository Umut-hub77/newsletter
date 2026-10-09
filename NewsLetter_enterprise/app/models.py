from datetime import datetime
from sqlalchemy import Column, String
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    """
    Bir SaaS müşterisi (şirket/hesap). Tüm diğer veriler buna bağlıdır.
    Bir organizasyonun verisi başka bir organizasyondan asla görünmez;
    her sorgu organization_id ile filtrelenir.
    """
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    brand_name = Column(String(200), nullable=False)  # mail/panelde görünen marka adı
    owner_email = Column(String(255), nullable=False)
    account_type = Column(String(20), default="company", nullable=False)  # company | individual
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True)  # kayıt sırasında seçilen sektör
    mail_theme = Column(String(20), default="klasik", nullable=False)  # klasik | minimal
    mail_accent = Column(String(20), default="#111111", nullable=False)  # bültende kullanılan vurgu rengi (hex)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Abonelik / faturalandırma durumu ---
    plan = Column(String(30), default="free", nullable=False)  # free | starter | pro
    subscription_status = Column(String(30), default="trialing", nullable=False)
    # trialing | active | expired | canceled
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_expires_at = Column(DateTime, nullable=True)  # Shopier tekrarlayan ödeme yapmadığı için manuel takip edilir
    current_duration_days = Column(Integer, nullable=True)  # 30/90/180/365 - hangi süre paketi aktif, Faturalandırma sayfasında doğru kutuyu "Yenile" göstermek için
    renewal_reminder_sent_at = Column(DateTime, nullable=True)
    api_key = Column(String(64), unique=True, nullable=True)
    mail_theme = Column(String, default="klasik")
    mail_accent = Column(String, default="#000000")

class PaymentOrder(Base):
    """
    Shopier'a gönderilen her ödeme denemesinin kaydı. platform_order_id,
    Shopier'in ödeme formunda gönderdiğimiz ve OSB (webhook) bildiriminde
    geri aldığımız benzersiz sipariş numarasıdır; organizasyon+plan
    eşleşmesini buradan buluruz.
    """
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    platform_order_id = Column(String(64), unique=True, nullable=False)
    plan = Column(String(30), nullable=False)
    amount_try = Column(Float, nullable=False)
    status = Column(String(30), default="pending", nullable=False)  # pending | success | failed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    shopier_payment_id = Column(String(120), nullable=True)


# Kategori/Kaynak/Haber artık organizasyona değil PLATFORMA ait (global).
# Mevcut veritabanı şemasını bozmamak için organization_id sütunu duruyor
# ama artık filtrelemede KULLANILMIYOR; tüm kayıtlar sabit bir "platform"
# değeriyle (GLOBAL_ORG_ID) yazılır. Sorgular bu sütunu görmezden gelir;
# tüm organizasyonlar aynı ortak havuzu görür.
GLOBAL_ORG_ID = 0


class Sector(Base):
    """
    Sektör (örn. Yazılım, Emlak, Finans). Kayıt sırasında kullanıcı kendi
    sektörünü seçer; kategoriler sektöre göre gruplanarak gösterilir.
    Sadece siz (/owner) yönetirsiniz.
    """
    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    slug = Column(String(120), unique=True, nullable=False)


class Category(Base):
    """PLATFORM GENELİ (global) kategori. Sadece siz (/owner) yönetirsiniz."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, default=GLOBAL_ORG_ID, nullable=False)  # artık kullanılmıyor, bkz. yukarı
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True)  # hangi sektöre ait (boşsa "Genel")
    city = Column(String(100), nullable=True)  # örn. "İstanbul" — konum bazlı kategoriler için (boşsa şehirsiz/genel kategori)
    name = Column(String(120), unique=True, nullable=False)
    slug = Column(String(120), unique=True, nullable=False)

    sector = relationship("Sector")
    sources = relationship("Source", back_populates="category", cascade="all, delete-orphan")


class Source(Base):
    """PLATFORM GENELİ (global) RSS kaynağı. Sadece siz (/owner) yönetirsiniz."""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, default=GLOBAL_ORG_ID, nullable=False)  # artık kullanılmıyor
    name = Column(String(200), nullable=False)
    feed_url = Column(String(500), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    last_fetched_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)

    category = relationship("Category", back_populates="sources")
    news_items = relationship("NewsItem", back_populates="source")


class NewsItem(Base):
    """MERKEZİ, PLATFORM GENELİ HABER HAVUZU. Tüm organizasyonlar ortak okur."""
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("link", name="uq_news_link"),)

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, default=GLOBAL_ORG_ID, nullable=False)  # artık kullanılmıyor
    title = Column(String(500), nullable=False)
    link = Column(String(1000), nullable=False)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    source = relationship("Source", back_populates="news_items")
    category = relationship("Category")


subscriber_categories = Table(
    "subscriber_categories", Base.metadata,
    Column("subscriber_id", Integer, ForeignKey("subscribers.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True),
)


class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_subscriber_org_email"),)

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(200), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    detected_city = Column(String(100), nullable=True)  # "Konumumu Kullan" ile algılanan şehir

    categories = relationship("Category", secondary=subscriber_categories)

    use_custom_schedule = Column(Boolean, default=False, nullable=False)
    custom_days_of_week = Column(String(50), nullable=True)
    custom_hour = Column(Integer, nullable=True)
    custom_minute = Column(Integer, nullable=True)


class AdminUser(Base):
    """Bir organizasyona ait panel kullanıcısı. Giriş e-posta ile yapılır (global benzersiz)."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(64), nullable=True)


class NewsletterSchedule(Base):
    """Organizasyon başına tekil genel zamanlama kaydı."""
    __tablename__ = "newsletter_schedule"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_schedule_org"),)

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    days_of_week = Column(String(50), default="mon,tue,wed,thu,fri,sat,sun", nullable=False)
    hour = Column(Integer, default=8, nullable=False)
    minute = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)


class NewsletterLog(Base):
    __tablename__ = "newsletter_logs"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    recipient_count = Column(Integer, default=0)
    article_count = Column(Integer, default=0)
    success = Column(Boolean, default=False)
    note = Column(String(500), nullable=True)