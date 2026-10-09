"""
Hesap kendi kendine silme. Bir organizasyondaki herhangi bir admin,
kendi şifresini doğrulayarak TÜM organizasyonu (aboneler, ekip üyeleri,
zamanlama, ödeme kayıtları dahil) kalıcı olarak silebilir.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import current_user_email, get_current_org, verify_password
from app.database import get_db
from app.models import AdminUser
from app.templates_env import templates

router = APIRouter(prefix="/panel")


def _guard(request: Request, db: Session):
    if not current_user_email(request):
        return RedirectResponse(url="/login", status_code=302), None
    org = get_current_org(request, db)
    if not org:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302), None
    return None, org


@router.get("/delete-account")
def delete_account_page(request: Request, db: Session = Depends(get_db), error: str | None = None):
    guard, org = _guard(request, db)
    if guard:
        return guard
    return templates.TemplateResponse("delete_account.html", {
        "request": request, "user": current_user_email(request), "org": org, "error": error,
    })


@router.post("/delete-account")
def delete_account_submit(request: Request, password: str = Form(...), db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard

    email = current_user_email(request)
    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not admin or not verify_password(password, admin.password_hash):
        return RedirectResponse(url="/panel/delete-account?error=wrong_password", status_code=302)


    db.delete(admin)
    db.commit()
    request.session.clear()
    return RedirectResponse(url="/login?account_deleted=1", status_code=302)