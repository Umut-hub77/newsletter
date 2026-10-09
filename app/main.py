import logging
from datetime import datetime, timedelta
from tempfile import template

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.billing import verify_notification_signature
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Organization, PaymentOrder, Sector
from app.routers import account, api, auth_routes, billing, owner, panel, team
from app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

from app.templates_env import templates

app = FastAPI(title=settings.APP_BRAND_NAME)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_routes.router)
app.include_router(panel.router)
app.include_router(account.router)
app.include_router(billing.router)
app.include_router(team.router)
app.include_router(owner.router)
app.include_router(api.router)


@app.post("/billing/webhook/shopier")
async def shopier_webhook(request: Request):
    """
    Shopier'in "Otomatik Sipariş Bildirimi" (OSB) için çağırdığı genel
    (girişsiz) uç. Shopier panelinizde bu URL'yi (APP_BASE_URL +
    /billing/webhook/shopier) "Bildirim URL'si" olarak tanımlamanız gerekir.
    Form-encoded POST gönderir (JSON değil).
    """
    form = await request.form()
    veri = dict(form)

    if not verify_notification_signature(veri):
        logger.warning("Shopier webhook: geçersiz imza - %s", veri.get("platform_order_id"))
        return PlainTextResponse("invalid signature", status_code=400)

    order_id = veri.get("platform_order_id", "")
    durum = veri.get("status", "")

    db = SessionLocal()
    try:
        siparis = db.query(PaymentOrder).filter(PaymentOrder.platform_order_id == order_id).first()
        if not siparis:
            logger.warning("Shopier webhook: bilinmeyen sipariş - %s", order_id)
            return PlainTextResponse("unknown order", status_code=400)

        if durum == "success":
            siparis.status = "success"
            siparis.shopier_payment_id = veri.get("payment_id")
            siparis.completed_at = datetime.utcnow()

            org = db.get(Organization, siparis.organization_id)
            if org:
                org.plan = siparis.plan
                org.subscription_status = "active"
                org.subscription_expires_at = datetime.utcnow() + timedelta(days=settings.SUBSCRIPTION_DAYS)
                org.renewal_reminder_sent_at = None
                logger.info("Org #%s planı '%s' olarak aktifleşti (Shopier)", org.id, siparis.plan)
        else:
            siparis.status = "failed"

        db.commit()
    finally:
        db.close()

    return PlainTextResponse("ok")


def migrate_schema():
    """
    Önceden oluşturulmuş (çok-kiracılı olmayan) bir SQLite veritabanı
    varsa, mevcut verinizi kaybetmeden yeni yapıya geçirmek için ayrıca
    migrate_to_multitenant.py script'ini çalıştırmanız gerekir (README'ye
    bakın). Bu fonksiyon, sürüm sürüm eklenen küçük sütunları tamamlar.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    tablo_sutunlari = {
        "subscribers": {
            "use_custom_schedule": "BOOLEAN DEFAULT 0 NOT NULL",
            "custom_days_of_week": "VARCHAR(50)",
            "custom_hour": "INTEGER",
            "custom_minute": "INTEGER",
            "detected_city": "VARCHAR(100)",
        },
        "admin_users": {
            "email_verified": "BOOLEAN DEFAULT 1 NOT NULL",
            "email_verification_token": "VARCHAR(64)",
        },
        "organizations": {
            "subscription_expires_at": "DATETIME",
            "renewal_reminder_sent_at": "DATETIME",
            "current_duration_days": "INTEGER",
            "account_type": "VARCHAR(20) DEFAULT 'company' NOT NULL",
            "sector_id": "INTEGER",
            "mail_theme": "VARCHAR(20) DEFAULT 'klasik' NOT NULL",
            "mail_accent": "VARCHAR(20) DEFAULT '#111111' NOT NULL",
        },
        "categories": {
            "sector_id": "INTEGER",
            "city": "VARCHAR(100)",
        },
    }

    try:
        with engine.connect() as conn:
            for tablo, sutunlar in tablo_sutunlari.items():
                mevcut = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({tablo})").fetchall()]
                if not mevcut:
                    continue
                for kolon, tip in sutunlar.items():
                    if kolon not in mevcut:
                        conn.exec_driver_sql(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tip}")
                        logger.info("Veritabanı güncellendi: %s.%s eklendi", tablo, kolon)
            conn.commit()
    except Exception as exc:
        logger.debug("Migrasyon atlandı: %s", exc)


def seed_default_sectors():
    """İlk açılışta, hiç sektör yoksa yaygın birkaç sektörü tohumlar (siz /owner'dan düzenleyebilirsiniz)."""
    db = SessionLocal()
    try:
        if db.query(Sector).count() == 0:
            varsayilanlar = [
                "Yazılım & Teknoloji", "Finans & Yatırım", "Emlak", "Sağlık",
                "Perakende & E-ticaret", "Üretim & Sanayi", "Eğitim", "Diğer",
            ]
            for isim in varsayilanlar:
                db.add(Sector(name=isim, slug=isim.lower().replace(" & ", "-").replace(" ", "-")))
            db.commit()
            logger.info("Varsayılan sektörler oluşturuldu (%d adet)", len(varsayilanlar))
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    migrate_schema()
    Base.metadata.create_all(bind=engine)
    seed_default_sectors()
    start_scheduler()


@app.get("/")
async def index(request: Request):
    # Artık yönlendirme yapma, hazırladığımız o harika ana sayfayı göster
    return templates.TemplateResponse("index.html", {"request": request}) 
