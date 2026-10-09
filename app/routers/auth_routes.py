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


def _dogrulama_maili_gonder(admin: AdminUser, request: Request | None = None):
    if request:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.url.netloc)
        base = f"{proto}://{host}".rstrip("/")
    else:
        base = settings.APP_BASE_URL.rstrip("/")
    link = f"{base}/verify-email?token={admin.email_verification_token}"
    subject = f"{settings.APP_BRAND_NAME} - E-posta adresinizi doğrulayın"
    body_text = (
        f"Merhaba,\n\n"
        f"{settings.APP_BRAND_NAME} hesabınızı doğrulamak için aşağıdaki bağlantıya tıklayın:\n{link}\n\n"
        f"Bu isteği siz yapmadıysanız bu e-postayı yok sayabilirsiniz."
    )
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h2 style="color: #1e293b; margin-top: 0;">Hoş Geldiniz!</h2>
        <p style="color: #475569; font-size: 15px; line-height: 1.6;">
            <strong>{settings.APP_BRAND_NAME}</strong> hesabınızı aktif hale getirmek için lütfen aşağıdaki butona tıklayarak e-posta adresinizi doğrulayın:
        </p>
        <div style="margin: 30px 0; text-align: center;">
            <a href="{link}" style="background-color: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                E-postamı Doğrula
            </a>
        </div>
        <p style="color: #94a3b8; font-size: 13px; line-height: 1.5;">
            Butona tıklayamıyorsanız bu bağlantıyı tarayıcınıza kopyalayabilirsiniz:<br>
            <a href="{link}" style="color: #2563eb; word-break: break-all;">{link}</a>
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
        <p style="color: #94a3b8; font-size: 12px; margin: 0;">
            Bu hesabı siz oluşturmadıysanız bu e-postayı dikkate almayınız.
        </p>
    </div>
    """
    sonuc = send_simple_email(
        admin.email,
        subject,
        body_text,
        body_html=body_html,
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

    is_owner = bool(settings.PLATFORM_OWNER_EMAIL and email == settings.PLATFORM_OWNER_EMAIL.strip().lower())
    admin = AdminUser(
        organization_id=org.id,
        email=email,
        password_hash=hash_password(password),
        email_verified=is_owner,
        email_verification_token=None if is_owner else secrets.token_urlsafe(32),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    if account_type == "individual":
        # Bireysel kullanıcı hem panel yöneticisi hem de bültenin TEK
        # alıcısıdır — kendi kategorilerini "Kategorilerim" sayfasından seçer.
        db.add(Subscriber(organization_id=org.id, email=email, name=organization_name.strip(), active=True))
        db.commit()

    if not is_owner:
        _dogrulama_maili_gonder(admin, request)

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
        _dogrulama_maili_gonder(admin, request)
    return RedirectResponse(url="/panel?verification_sent=1", status_code=302)