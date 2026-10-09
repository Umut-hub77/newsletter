import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import authenticate, current_user_email, hash_password, log_in_session
from app.config import settings
from app.database import get_db
from app.models import AdminUser, Organization, Sector, Subscriber
from app.scheduler import get_or_create_schedule, reschedule_newsletter_job
from app.templates_env import templates
from app.transactional_mail import send_simple_email

logger = logging.getLogger("auth_routes")
router = APIRouter()


def _slug_uret(ad: str, db: Session) -> str:
    taban = "".join(c.lower() if c.isalnum() else "-" for c in ad).strip("-") or "organizasyon"
    slug = taban
    sayac = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        sayac += 1
        slug = f"{taban}-{sayac}"
    return slug


def _dogrulama_maili_gonder(admin: AdminUser):
    link = f"{settings.APP_BASE_URL}/verify-email?token={admin.email_verification_token}"
    sonuc = send_simple_email(
        admin.email,
        f"{settings.APP_BRAND_NAME} - E-posta adresinizi doğrulayın",
        f"Merhaba,\n\nHesabınızı doğrulamak için aşağıdaki bağlantıya tıklayın:\n{link}\n\n"
        f"Bu isteği siz yapmadıysanız bu e-postayı yok sayabilirsiniz.",
    )
    logger.info("Doğrulama maili gönderim sonucu (%s): %s", admin.email, sonuc)
    return sonuc


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...),
                  db: Session = Depends(get_db)):
    user = authenticate(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "E-posta veya şifre hatalı"}, status_code=401
        )
    log_in_session(request, user)
    return RedirectResponse(url="/panel", status_code=302)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/signup")
def signup_page(request: Request, db: Session = Depends(get_db)):
    sektorler = db.query(Sector).order_by(Sector.name).all()
    return templates.TemplateResponse("signup.html", {"request": request, "error": None, "sektorler": sektorler})


@router.post("/signup")
def signup_submit(
    request: Request,
    organization_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    account_type: str = Form("individual"),
    sector_id: str = Form(""),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    account_type = account_type if account_type in ("individual", "company") else "individual"
    sektorler = db.query(Sector).order_by(Sector.name).all()

    if len(password) < 8:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Şifre en az 8 karakter olmalı", "sektorler": sektorler},
            status_code=400,
        )
    if db.query(AdminUser).filter(AdminUser.email == email).first():
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Bu e-posta ile zaten bir hesap var", "sektorler": sektorler},
            status_code=400,
        )

    org = Organization(
        name=organization_name.strip(),
        slug=_slug_uret(organization_name, db),
        brand_name=organization_name.strip(),
        owner_email=email,
        account_type=account_type,
        sector_id=int(sector_id) if sector_id else None,
        plan="free",
        subscription_status="trialing",
        trial_ends_at=datetime.utcnow() + timedelta(days=settings.TRIAL_DAYS),
        api_key=secrets.token_hex(24),
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    admin = AdminUser(
        organization_id=org.id,
        email=email,
        password_hash=hash_password(password),
        email_verified=False,
        email_verification_token=secrets.token_urlsafe(32),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    if account_type == "individual":
        # Bireysel kullanıcı hem panel yöneticisi hem de bültenin TEK
        # alıcısıdır — kendi kategorilerini "Kategorilerim" sayfasından seçer.
        db.add(Subscriber(organization_id=org.id, email=email, name=organization_name.strip(), active=True))
        db.commit()

    _dogrulama_maili_gonder(admin)

    schedule = get_or_create_schedule(db, org.id)
    reschedule_newsletter_job(schedule)

    log_in_session(request, admin)
    return RedirectResponse(url="/panel", status_code=302)


@router.get("/verify-email")
def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email_verification_token == token).first()
    basarili = False
    if admin:
        admin.email_verified = True
        admin.email_verification_token = None
        db.commit()
        basarili = True
    return templates.TemplateResponse("verify_result.html", {"request": request, "success": basarili})


@router.post("/resend-verification")
def resend_verification(request: Request, db: Session = Depends(get_db)):
    email = current_user_email(request)
    if not email:
        return RedirectResponse(url="/login", status_code=302)
    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if admin and not admin.email_verified:
        admin.email_verification_token = secrets.token_urlsafe(32)
        db.commit()
        _dogrulama_maili_gonder(admin)
    return RedirectResponse(url="/panel?verification_sent=1", status_code=302)