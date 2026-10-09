from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, NewsItem, Organization

router = APIRouter(prefix="/api", tags=["api"])


def require_api_key(
    x_api_key: str = Header(..., description="Panelden aldığınız organizasyon API anahtarı"),
    db: Session = Depends(get_db),
) -> Organization:
    org = db.query(Organization).filter(Organization.api_key == x_api_key).first()
    if not org:
        raise HTTPException(status_code=401, detail="Geçersiz API anahtarı")
    return org


@router.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@router.get("/categories")
def list_categories(db: Session = Depends(get_db), org: Organization = Depends(require_api_key)):
    kategoriler = db.query(Category).filter(Category.organization_id == org.id).all()
    return [{"id": c.id, "name": c.name, "slug": c.slug} for c in kategoriler]


@router.get("/news")
def list_news(
    category: str | None = Query(default=None, description="Kategori slug'ı"),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    org: Organization = Depends(require_api_key),
):
    """Kendi organizasyonunuzun merkezi haber havuzundan okur. X-API-Key header'ı zorunludur."""
    q = db.query(NewsItem).join(Category).filter(NewsItem.organization_id == org.id)
    if category:
        q = q.filter(Category.slug == category)
    items = q.order_by(NewsItem.fetched_at.desc()).limit(limit).all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "link": i.link,
            "category": i.category.name,
            "published_at": i.published_at.isoformat() if i.published_at else None,
            "fetched_at": i.fetched_at.isoformat(),
        }
        for i in items
    ]
