"""
Platform sahibi (siz) paneli. Sadece PLATFORM_OWNER_EMAIL ile giriş yapan
kişi görebilir. Shopier'den gelen ödemeleri (panelinizdeki sipariş
listesinden/e-posta bildiriminden takip ederek) burada manuel onaylayıp
ilgili organizasyonun planını aktifleştirirsiniz.
"""
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import current_user_email
from app.collector import collect_all, discover_feed_url
from app.config import settings
from app.database import get_db
from app.models import Category, Organization, PaymentOrder, Sector, Source
from app.plan_limits import PLAN_LIMITS
from app.templates_env import templates

router = APIRouter(prefix="/owner")


def _guard(request: Request):
    email = current_user_email(request)
    if not email:
        return RedirectResponse(url="/login", status_code=302)
    if not settings.PLATFORM_OWNER_EMAIL or email != settings.PLATFORM_OWNER_EMAIL.strip().lower():
        return RedirectResponse(url="/panel", status_code=302)
    return None


@router.get("")
def owner_dashboard(request: Request, db: Session = Depends(get_db), q: str | None = None):
    guard = _guard(request)
    if guard:
        return guard
    sorgu = db.query(Organization).order_by(Organization.created_at.desc())
    if q:
        sorgu = sorgu.filter(Organization.owner_email.contains(q.strip().lower()))
    organizasyonlar = sorgu.limit(200).all()
    bekleyen_odemeler = db.query(PaymentOrder).filter(
        PaymentOrder.status == "pending"
    ).order_by(PaymentOrder.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("owner_dashboard.html", {
        "request": request, "user": current_user_email(request),
        "organizasyonlar": organizasyonlar, "bekleyen_odemeler": bekleyen_odemeler,
        "plans": PLAN_LIMITS, "q": q or "",
    })


@router.post("/organizations/{org_id}/set-plan")
def set_plan(request: Request, org_id: int, plan: str = Form(...), gun: int = Form(30),
             db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    org = db.get(Organization, org_id)
    if org and plan in PLAN_LIMITS:
        org.plan = plan
        if plan == "free":
            org.subscription_status = "active"
            org.subscription_expires_at = None
            org.current_duration_days = None
        else:
            org.subscription_status = "active"
            org.subscription_expires_at = datetime.utcnow() + timedelta(days=gun)
            org.current_duration_days = gun
        org.renewal_reminder_sent_at = None
        db.commit()
    return RedirectResponse(url="/owner", status_code=302)


@router.post("/organizations/{org_id}/delete")
def delete_organization(request: Request, org_id: int, db: Session = Depends(get_db)):
    """Bir organizasyonu ve tüm verilerini (aboneler, ekip, ödeme kayıtları dahil) kalıcı olarak siler."""
    guard = _guard(request)
    if guard:
        return guard
    org = db.get(Organization, org_id)
    if org:
        db.delete(org)
        db.commit()
    return RedirectResponse(url="/owner", status_code=302)


@router.post("/payment-orders/{order_id}/mark-done")
def mark_payment_done(request: Request, order_id: int, db: Session = Depends(get_db)):
    """Bekleyen bir ödeme kaydını, ilgili organizasyonu güncellemeden sadece 'işlendi' olarak kapatır."""
    guard = _guard(request)
    if guard:
        return guard
    siparis = db.get(PaymentOrder, order_id)
    if siparis:
        siparis.status = "success"
        siparis.completed_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(url="/owner", status_code=302)


@router.get("/sources")
def sources_page(request: Request, db: Session = Depends(get_db), error: str | None = None):
    """Platform geneli kategori/kaynak yönetimi — tüm organizasyonlar bu ortak havuzu kullanır."""
    guard = _guard(request)
    if guard:
        return guard
    return templates.TemplateResponse("owner_sources.html", {
        "request": request, "user": current_user_email(request),
        "sources": db.query(Source).order_by(Source.category_id).all(),
        "categories": db.query(Category).order_by(Category.name).all(),
        "sectors": db.query(Sector).order_by(Sector.name).all(),
        "error": error,
    })


@router.post("/sources/collect-now")
def collect_now(request: Request, db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    collect_all(db)
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/sources/add")
def add_source(request: Request, name: str = Form(...), url: str = Form(...),
               category_id: int = Form(...), db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    try:
        feed_url = discover_feed_url(url)
    except ValueError as e:
        return RedirectResponse(url=f"/owner/sources?error={quote(str(e))}", status_code=302)
    db.add(Source(name=name, feed_url=feed_url, category_id=category_id, active=True))
    db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/sources/{source_id}/toggle")
def toggle_source(request: Request, source_id: int, db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    src = db.get(Source, source_id)
    if src:
        src.active = not src.active
        db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/sources/{source_id}/delete")
def delete_source(request: Request, source_id: int, db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    src = db.get(Source, source_id)
    if src:
        # Önce bu kaynağa ait haberleri sil - yoksa NewsItem.source_id NOT NULL
        # kısıtlaması nedeniyle silme işlemi hataya düşer.
        db.execute(text("DELETE FROM news_items WHERE source_id = :sid"), {"sid": source_id})
        db.delete(src)
        db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/categories/add")
def add_category(request: Request, name: str = Form(...), sector_id: str = Form(""), city: str = Form(""),
                  db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    slug = name.strip().lower().replace(" ", "-")
    db.add(Category(
        name=name.strip(), slug=slug,
        sector_id=int(sector_id) if sector_id else None,
        city=city.strip() or None,
    ))
    db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/categories/{category_id}/delete")
def delete_category(request: Request, category_id: int, db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    kategori = db.get(Category, category_id)
    if kategori:
        # Bu kategorideki kaynaklara ait haberleri de sil (aynı NOT NULL sorunu)
        db.execute(
            text("DELETE FROM news_items WHERE source_id IN "
                 "(SELECT id FROM sources WHERE category_id = :cid)"),
            {"cid": category_id},
        )
        db.delete(kategori)
        db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/sectors/add")
def add_sector(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    slug = name.strip().lower().replace(" ", "-")
    if not db.query(Sector).filter(Sector.name == name.strip()).first():
        db.add(Sector(name=name.strip(), slug=slug))
        db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)


@router.post("/sectors/{sector_id}/delete")
def delete_sector(request: Request, sector_id: int, db: Session = Depends(get_db)):
    guard = _guard(request)
    if guard:
        return guard
    sektor = db.get(Sector, sector_id)
    if sektor:
        # Bu sektöre bağlı kategoriler silinmez, sadece sektörsüz ("Genel") kalır
        db.query(Category).filter(Category.sector_id == sector_id).update({"sector_id": None})
        db.delete(sektor)
        db.commit()
    return RedirectResponse(url="/owner/sources", status_code=302)