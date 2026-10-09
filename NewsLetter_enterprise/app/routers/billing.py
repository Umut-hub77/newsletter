from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import current_user_email, get_current_org
from app.config import settings
from app.database import get_db
from app.models import AdminUser, PaymentOrder, Subscriber
from app.plan_limits import DURATIONS, PLAN_LIMITS, get_duration, get_plan, get_price
from app.templates_env import templates

router = APIRouter(prefix="/panel/billing")

# plan_key + "_" + duration_key -> .env'deki sabit Shopier ürün linki
PAYMENT_URLS = {
    "starter_30": settings.SHOPIER_STARTER_30_URL,
    "starter_90": settings.SHOPIER_STARTER_90_URL,
    "starter_180": settings.SHOPIER_STARTER_180_URL,
    "starter_365": settings.SHOPIER_STARTER_365_URL,
    "pro_30": settings.SHOPIER_PRO_30_URL,
    "pro_90": settings.SHOPIER_PRO_90_URL,
    "pro_180": settings.SHOPIER_PRO_180_URL,
    "pro_365": settings.SHOPIER_PRO_365_URL,
}


def _guard(request: Request, db: Session):
    if not current_user_email(request):
        return RedirectResponse(url="/login", status_code=302), None
    org = get_current_org(request, db)
    if not org:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302), None
    return None, org


@router.get("")
def billing_page(request: Request, db: Session = Depends(get_db), success: int | None = None,
                  error: str | None = None):
    guard, org = _guard(request, db)
    if guard:
        return guard
    plan = get_plan(org.plan, org.account_type)
    abone_sayisi = db.query(Subscriber).filter(Subscriber.organization_id == org.id).count()

    # Her plan için her sürenin fiyatını önceden hesapla (şablonda kullanmak için)
    fiyat_tablosu = {}
    for plan_key in PLAN_LIMITS:
        if plan_key == "free":
            continue
        fiyat_tablosu[plan_key] = {
            duration_key: get_price(plan_key, duration_key) for duration_key in DURATIONS
        }

    plan_overrides = {key: get_plan(key, org.account_type) for key in PLAN_LIMITS if key != "free"}
    return templates.TemplateResponse("billing.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "plan": plan, "abone_sayisi": abone_sayisi, "plans": PLAN_LIMITS,
        "plan_overrides": plan_overrides, "durations": DURATIONS, "fiyat_tablosu": fiyat_tablosu,
        "success": success, "error": error,
    })


@router.post("/checkout/{plan_key}/{duration_key}")
def checkout(request: Request, plan_key: str, duration_key: str, db: Session = Depends(get_db)):
    """
    ŞU ANKİ AKIŞ (manuel onaylı): Shopier'in PAT tabanlı yeni REST API'si
    için ödeme linki oluşturmanın doğrulanmış bir dokümantasyonu
    bulunamadığı için, burada imza üretip form göndermiyoruz. Bunun yerine
    Shopier panelinizde her plan+süre kombinasyonu için elle oluşturduğunuz
    sabit ürün linkine yönlendiriyoruz. Ödeme sonrası plan, siz (/owner
    panelinden) manuel onaylayana kadar aktifleşmez.
    """
    guard, org = _guard(request, db)
    if guard:
        return guard
    if plan_key not in ("starter", "pro") or duration_key not in DURATIONS:
        return RedirectResponse(url="/panel/billing", status_code=302)

    admin = db.query(AdminUser).filter(AdminUser.email == current_user_email(request)).first()
    if admin and not admin.email_verified:
        return RedirectResponse(url="/panel/billing?error=verify_email_first", status_code=302)

    odeme_linki = PAYMENT_URLS.get(f"{plan_key}_{duration_key}")
    if not odeme_linki:
        return RedirectResponse(url="/panel/billing?error=shopier_not_configured", status_code=302)

    fiyat = get_price(plan_key, duration_key)
    db.add(PaymentOrder(
        organization_id=org.id,
        platform_order_id=f"org{org.id}-{plan_key}-{duration_key}-{int(datetime.utcnow().timestamp())}",
        plan=plan_key, amount_try=fiyat, status="pending",
    ))
    db.commit()

    return RedirectResponse(url=odeme_linki, status_code=303)