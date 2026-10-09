from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import current_user_email, get_current_org, hash_password
from app.database import get_db
from app.models import AdminUser
from app.templates_env import templates

router = APIRouter(prefix="/panel/team")


def _guard(request: Request, db: Session):
    if not current_user_email(request):
        return RedirectResponse(url="/login", status_code=302), None
    org = get_current_org(request, db)
    if not org:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302), None
    return None, org


@router.get("")
def team_page(request: Request, db: Session = Depends(get_db), error: str | None = None):
    guard, org = _guard(request, db)
    if guard:
        return guard
    if org.account_type == "individual":
        return RedirectResponse(url="/panel", status_code=302)
    admins = db.query(AdminUser).filter(AdminUser.organization_id == org.id).all()
    return templates.TemplateResponse("team.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "admins": admins, "error": error,
    })


@router.post("/add")
def add_teammate(request: Request, email: str = Form(...), password: str = Form(...),
                  db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    email = email.strip().lower()

    plan = get_plan(org.plan, org.account_type)
    if not plan.get("team_management_allowed"):
        return RedirectResponse(url="/panel?error=team_not_allowed", status_code=302)
    toplam = db.query(AdminUser).filter(AdminUser.organization_id == org.id).count()
    if toplam >= plan.get("max_team_members", 0):
        return RedirectResponse(url=f"/panel/team?error={quote('Planınızın izin verdiği maksimum ekip üyesine ulaşıldı')}", status_code=302)

    if len(password) < 8:
        return RedirectResponse(url=f"/panel/team?error={quote('Şifre en az 8 karakter olmalı')}", status_code=302)
    if db.query(AdminUser).filter(AdminUser.email == email).first():
        return RedirectResponse(url=f"/panel/team?error={quote('Bu e-posta zaten kullanımda')}", status_code=302)

    # Ekibe davet edilen üye, ekleyen admin tarafından zaten doğrulanmış
    # sayılır (e-posta doğrulama akışına gerek yok).
    db.add(AdminUser(
        organization_id=org.id, email=email, password_hash=hash_password(password),
        email_verified=True,
    ))
    db.commit()
    return RedirectResponse(url="/panel/team", status_code=302)


@router.post("/{admin_id}/delete")
def delete_teammate(request: Request, admin_id: int, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    toplam = db.query(AdminUser).filter(AdminUser.organization_id == org.id).count()
    if toplam <= 1:
        return RedirectResponse(url=f"/panel/team?error={quote('Son admin silinemez')}", status_code=302)
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.organization_id == org.id).first()
    if admin:
        db.delete(admin)
        db.commit()
    return RedirectResponse(url="/panel/team", status_code=302)