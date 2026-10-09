from fastapi import Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import AdminUser, Organization

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def authenticate(db: Session, email: str, password: str) -> AdminUser | None:
    """Giriş artık e-posta ile yapılır (organizasyon otomatik bulunur, e-posta global benzersiz)."""
    user = db.query(AdminUser).filter(AdminUser.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def current_user_email(request: Request) -> str | None:
    return request.session.get("email")


def current_org_id(request: Request) -> int | None:
    return request.session.get("organization_id")


def log_in_session(request: Request, user: AdminUser):
    request.session["email"] = user.email
    request.session["admin_user_id"] = user.id
    request.session["organization_id"] = user.organization_id


def require_login(request: Request):
    """Panel route'larında dependency olarak kullanılır; girişi olmayanı /login'e yollar."""
    if not current_user_email(request):
        return RedirectResponse(url="/login", status_code=302)
    return None


def get_current_org(request: Request, db: Session) -> Organization | None:
    org_id = current_org_id(request)
    if not org_id:
        return None
    return db.get(Organization, org_id)
