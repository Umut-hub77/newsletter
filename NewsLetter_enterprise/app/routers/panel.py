from datetime import datetime
from zoneinfo import ZoneInfo
from app.models import Organization
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import current_user_email, get_current_org
from app.config import settings
from app.database import get_db
from app.geocoding import resolve_region
from app.geocoding import fetch_local_news 
from app.models import AdminUser, Category, NewsItem, NewsletterLog, Sector, Subscriber
from app.newsletter import get_recent_news_by_category, html_bulten_olustur, send_newsletter
from app.plan_limits import get_plan
from app.scheduler import (
    get_or_create_schedule, reschedule_newsletter_job,
    reschedule_subscriber_job, remove_subscriber_job,
)
from app.templates_env import templates

router = APIRouter(prefix="/panel")


def _konum_isle(db: Session, sub: Subscriber, lat: float, lon: float) -> dict:
    """Konumu bölgeye çevirir, abonenin kaydına yazar, eşleşen kategorileri döner."""
    bolge = resolve_region(lat, lon)
    if not bolge:
        return {"city": None, "matched": []}
    sub.detected_city = bolge
    db.commit()
    bolge_kelimeleri = [kelime for kelime in bolge.lower().split() if kelime]
    if not bolge_kelimeleri:
        eslesenler = []
    else:
        eslesenler = []
        for kategori in db.query(Category).all():
            if not kategori.city:
                continue
            kategori_city = kategori.city.lower()
            if any(kelime in kategori_city for kelime in bolge_kelimeleri):
                eslesenler.append(kategori)
    return {
        "city": bolge,
        "matched": [{"id": c.id, "name": c.name} for c in eslesenler],
    }


def _guard(request: Request, db: Session):
    """
    Girişi olmayanı /login'e döndürür. Aksi halde (redirect, org) döner;
    org None ise oturum bozuk demektir, yine login'e yönlendirilir.
    """
    if not current_user_email(request):
        return RedirectResponse(url="/login", status_code=302), None
    org = get_current_org(request, db)
    if not org:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=302), None
    return None, org


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    kategorize = get_recent_news_by_category(db)
    son_gonderim = db.query(NewsletterLog).filter(
        NewsletterLog.organization_id == org.id
    ).order_by(NewsletterLog.sent_at.desc()).first()
    son_gonderim_yerel_saat = None
    if son_gonderim:
        son_gonderim_yerel_saat = (
            son_gonderim.sent_at.replace(tzinfo=ZoneInfo("UTC"))
            .astimezone(ZoneInfo(settings.APP_TIMEZONE))
        )
    toplam_haber = db.query(NewsItem).count()
    toplam_kategori = db.query(Category).count()
    toplam_abone = db.query(Subscriber).filter(
        Subscriber.organization_id == org.id, Subscriber.active.is_(True)
    ).count()
    plan = get_plan(org.plan, org.account_type)
    admin_id = request.session.get("admin_user_id")
    admin = db.get(AdminUser, admin_id) if admin_id else None
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "kategorize": kategorize, "son_gonderim": son_gonderim,
        "son_gonderim_yerel_saat": son_gonderim_yerel_saat,
        "toplam_haber": toplam_haber, "toplam_kategori": toplam_kategori, "toplam_abone": toplam_abone,
        "plan": plan, "email_verified": admin.email_verified if admin else True,
    })


@router.post("/send-now")
def send_now(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    send_newsletter(db, org.id)
    return RedirectResponse(url="/panel", status_code=302)


@router.get("/schedule")
def schedule_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    schedule = get_or_create_schedule(db, org.id)
    secili_gunler = set((schedule.days_of_week or "").split(","))
    return templates.TemplateResponse("schedule.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "schedule": schedule, "secili_gunler": secili_gunler,
    })


@router.post("/schedule/update")
def update_schedule(request: Request, gunler: list[str] = Form([]), zaman: str = Form(...),
                     aktif: str = Form(None), db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    saat, dakika = (int(p) for p in zaman.split(":"))
    schedule = get_or_create_schedule(db, org.id)
    schedule.days_of_week = ",".join(gunler) if gunler else "mon,tue,wed,thu,fri,sat,sun"
    schedule.hour = saat
    schedule.minute = dakika
    schedule.enabled = bool(aktif)
    db.commit()
    db.refresh(schedule)
    reschedule_newsletter_job(schedule)
    return RedirectResponse(url="/panel/schedule", status_code=302)


@router.get("/reports")
def reports_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    plan = get_plan(org.plan, org.account_type)
    if not plan.get("scheduled_reports"):
        return RedirectResponse(url="/panel?error=reports_not_allowed", status_code=302)
    report_data = {
        "open_rate": 62,
        "click_rate": 18,
        "top_category": "Teknoloji",
        "weekly_growth": 12,
        "schedule_status": "Haftalık gönderim planınız aktif.",
    }
    return templates.TemplateResponse("reports.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "plan": plan, "report_data": report_data,
    })


@router.get("/segments")
def segments_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    plan = get_plan(org.plan, org.account_type)
    if not plan.get("subscriber_segmentation"):
        return RedirectResponse(url="/panel?error=segments_not_allowed", status_code=302)

    segments_list = [
        {
            "slug": "inactive",
            "title": "Pasif Aboneler",
            "description": "Uzun süredir maillerinizi açmayan abonelere özel takip planı hazırlayın.",
            "example": "Onları yeniden kazanmak için hatırlatma gönderin.",
        },
        {
            "slug": "active",
            "title": "En Aktif Aboneler",
            "description": "En sık etkileşim gösteren aboneleri hedefleyerek dönüşümü artırın.",
            "example": "Onlara özel teklifler ve erken erişim sunun.",
        },
        {
            "slug": "region",
            "title": "Konuma Göre Segment",
            "description": "Abonelerinizi şehir ve bölgeye göre gruplandırarak yerel içerik gönderin.",
            "example": "Yerel duyurularla ilgiyi yükseltin.",
        },
    ]

    if org.account_type == "individual":
        segments_list.append({
            "slug": "personal_profile",
            "title": "Kişisel Profil Segmenti",
            "description": "Kişisel kullanıcı davranışına göre daha özel gönderimler yapın.",
            "example": "Her aboneye onun ilgilendiği konulardan bahsedin.",
            "personal": True,
        })

    selected_segment_slug = request.query_params.get("segment")
    selected_segment = None
    segment_subscribers = []
    segment_count = 0

    if selected_segment_slug:
        selected_segment = next((s for s in segments_list if s["slug"] == selected_segment_slug), None)
        if selected_segment:
            query = db.query(Subscriber).filter(Subscriber.organization_id == org.id)
            if selected_segment_slug == "inactive":
                query = query.filter(Subscriber.active.is_(False))
            elif selected_segment_slug == "active":
                query = query.filter(Subscriber.active.is_(True))
            elif selected_segment_slug == "region":
                query = query.filter(Subscriber.detected_city.isnot(None))
            elif selected_segment_slug == "personal_profile" and org.account_type == "individual":
                query = query.filter(Subscriber.active.is_(True))
            segment_subscribers = query.order_by(Subscriber.added_at.desc()).limit(8).all()
            segment_count = query.count()

    return templates.TemplateResponse("campaign_templates.html", {
        "request": request,
        "user": current_user_email(request),
        "org": org,
        "plan": plan,
        "segments_list": segments_list,
        "selected_segment": selected_segment,
        "segment_subscribers": segment_subscribers,
        "segment_count": segment_count,
    })


@router.get("/analysis")
def analysis_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    plan = get_plan(org.plan, org.account_type)
    if org.account_type == "individual":
        if not plan.get("location_insights"):
            return RedirectResponse(url="/panel?error=analysis_not_allowed", status_code=302)
        insight_data = {
            "focus_topic": "Yerel hayat ve kişisel ilgi alanları",
            "open_rate": 78,
            "click_rate": 24,
            "top_location": "İstanbul",
            "recommendation": "En yüksek açılma, öğleden sonra 15:00-17:00 aralığında. Bu saatlerde kişisel kampanyaları deneyin.",
        }
        template_type = "individual"
    else:
        if not plan.get("subscriber_segmentation"):
            return RedirectResponse(url="/panel?error=analysis_not_allowed", status_code=302)
        insight_data = {
            "focus_topic": "Abone dağılımı ve kategori performansı",
            "active_subscribers": db.query(Subscriber).filter(Subscriber.organization_id == org.id, Subscriber.active.is_(True)).count(),
            "inactive_subscribers": db.query(Subscriber).filter(Subscriber.organization_id == org.id, Subscriber.active.is_(False)).count(),
            "region_count": db.query(Subscriber).filter(Subscriber.organization_id == org.id, Subscriber.detected_city.isnot(None)).count(),
            "recommendation": "Pasif aboneleri yeniden hedefleyin ve konum bazlı segmentasyonla dönüşümü artırın.",
        }
        template_type = "company"

    return templates.TemplateResponse("analysis.html", {
        "request": request,
        "user": current_user_email(request),
        "org": org,
        "plan": plan,
        "template_type": template_type,
        "insight_data": insight_data,
    })


@router.get("/send-time")
def send_time_insights(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    plan = get_plan(org.plan, org.account_type)
    if not plan.get("send_time_insights"):
        return RedirectResponse(url="/panel?error=send_time_insights_not_allowed", status_code=302)
    insight_data = {
        "best_hour": 14,
        "open_rate_delta": 9,
        "recommended_window": "14:00 - 17:00",
        "note": "Bu saat aralığında gönderimleriniz daha yüksek açılma alıyor.",
    }
    return templates.TemplateResponse("send_time_insights.html", {
        "request": request,
        "user": current_user_email(request),
        "org": org,
        "plan": plan,
        "insight_data": insight_data,
    })


@router.get("/behavior-insights")
def behavior_insights(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    plan = get_plan(org.plan, org.account_type)
    if not plan.get("behavior_scores"):
        return RedirectResponse(url="/panel?error=behavior_scores_not_allowed", status_code=302)
    scores = [
        {"email": "ali@example.com", "score": 92, "status": "Çok yüksek"},
        {"email": "ayse@example.com", "score": 78, "status": "İyi"},
        {"email": "mehmet@example.com", "score": 54, "status": "Dikkat"},
    ]
    return templates.TemplateResponse("behavior_insights.html", {
        "request": request,
        "user": current_user_email(request),
        "org": org,
        "plan": plan,
        "scores": scores,
    })


@router.get("/subscribers")
def subscribers_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    if org.account_type == "individual":
        return RedirectResponse(url="/panel/my-categories", status_code=302)
    plan = get_plan(org.plan, org.account_type)
    return templates.TemplateResponse("subscribers.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "subscribers": db.query(Subscriber).filter(Subscriber.organization_id == org.id).all(),
        "plan": plan,
    })


@router.post("/subscribers/add")
def add_subscriber(request: Request, email: str = Form(...), name: str = Form(""),
                    db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard

    plan = get_plan(org.plan, org.account_type)
    mevcut_sayi = db.query(Subscriber).filter(Subscriber.organization_id == org.id).count()
    if mevcut_sayi >= plan["max_subscribers"]:
        return RedirectResponse(url="/panel/subscribers", status_code=302)

    var_mi = db.query(Subscriber).filter(
        Subscriber.organization_id == org.id, Subscriber.email == email.strip().lower()
    ).first()
    if not var_mi:
        db.add(Subscriber(organization_id=org.id, email=email.strip().lower(),
                           name=name.strip() or None, active=True))
        db.commit()
    return RedirectResponse(url="/panel/subscribers", status_code=302)


@router.post("/subscribers/{sub_id}/toggle")
def toggle_subscriber(request: Request, sub_id: int, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if sub:
        sub.active = not sub.active
        db.commit()
        db.refresh(sub)
        reschedule_subscriber_job(sub)
    return RedirectResponse(url="/panel/subscribers", status_code=302)


@router.post("/subscribers/{sub_id}/delete")
def delete_subscriber(request: Request, sub_id: int, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if sub:
        remove_subscriber_job(sub_id)
        db.delete(sub)
        db.commit()
    return RedirectResponse(url="/panel/subscribers", status_code=302)


@router.get("/subscribers/{sub_id}")
def subscriber_detail(request: Request, sub_id: int, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if not sub:
        return RedirectResponse(url="/panel/subscribers", status_code=302)
    plan = get_plan(org.plan, org.account_type)
    secili_kategori_idler = {k.id for k in sub.categories}
    secili_gunler = set((sub.custom_days_of_week or "").split(",")) if sub.custom_days_of_week else set()
    return templates.TemplateResponse("subscriber_detail.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "subscriber": sub,
        "categories": db.query(Category).order_by(Category.name).all(),
        "sectors": db.query(Sector).order_by(Sector.name).all(),
        "secili_kategori_idler": secili_kategori_idler, "secili_gunler": secili_gunler,
        "plan": plan,
    })


@router.post("/subscribers/{sub_id}/update-preferences")
def update_subscriber_preferences(
    request: Request, sub_id: int,
    kategoriler: list[int] = Form([]),
    kullan_ozel_zamanlama: str = Form(None),
    gunler: list[str] = Form([]),
    zaman: str = Form("08:00"),
    db: Session = Depends(get_db),
):
    guard, org = _guard(request, db)
    if guard:
        return guard
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if not sub:
        return RedirectResponse(url="/panel/subscribers", status_code=302)

    plan = get_plan(org.plan, org.account_type)
    if len(kategoriler) > plan.get("max_categories", 0):
        return RedirectResponse(url=f"/panel/subscribers/{sub_id}?error=max_categories", status_code=302)
    sub.categories = db.query(Category).filter(Category.id.in_(kategoriler)).all() if kategoriler else []

    kullan_ozel = bool(kullan_ozel_zamanlama) and plan["custom_schedule_allowed"]
    sub.use_custom_schedule = kullan_ozel
    if kullan_ozel:
        saat, dakika = (int(p) for p in zaman.split(":"))
        sub.custom_days_of_week = ",".join(gunler) if gunler else "mon,tue,wed,thu,fri,sat,sun"
        sub.custom_hour = saat
        sub.custom_minute = dakika

    db.commit()
    db.refresh(sub)
    reschedule_subscriber_job(sub)
    return RedirectResponse(url=f"/panel/subscribers/{sub_id}", status_code=302)


def _kendi_aboneligini_bul(db: Session, org_id: int) -> Subscriber | None:
    """Bireysel hesabın kendi (tek) abone kaydını bulur."""
    return db.query(Subscriber).filter(Subscriber.organization_id == org_id).first()


@router.get("/my-categories")
def my_categories_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    if org.account_type != "individual":
        return RedirectResponse(url="/panel/subscribers", status_code=302)

    sub = _kendi_aboneligini_bul(db, org.id)
    if not sub:
        # Beklenmedik durum (örn. eski hesap) - kendini abone olarak oluştur
        sub = Subscriber(organization_id=org.id, email=org.owner_email, name=org.name, active=True)
        db.add(sub)
        db.commit()
        db.refresh(sub)

    plan = get_plan(org.plan, org.account_type)
    secili_kategori_idler = {k.id for k in sub.categories}
    secili_gunler = set((sub.custom_days_of_week or "").split(",")) if sub.custom_days_of_week else set()
    return templates.TemplateResponse("my_categories.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "subscriber": sub,
        "categories": db.query(Category).order_by(Category.name).all(),
        "sectors": db.query(Sector).order_by(Sector.name).all(),
        "secili_kategori_idler": secili_kategori_idler, "secili_gunler": secili_gunler,
        "plan": plan,
    })


@router.post("/my-categories/update")
def update_my_categories(
    request: Request,
    kategoriler: list[int] = Form([]),
    kullan_ozel_zamanlama: str = Form(None),
    gunler: list[str] = Form([]),
    zaman: str = Form("08:00"),
    db: Session = Depends(get_db),
):
    guard, org = _guard(request, db)
    if guard:
        return guard
    if org.account_type != "individual":
        return RedirectResponse(url="/panel/subscribers", status_code=302)

    sub = _kendi_aboneligini_bul(db, org.id)
    if not sub:
        return RedirectResponse(url="/panel/my-categories", status_code=302)

    plan = get_plan(org.plan, org.account_type)
    if len(kategoriler) > plan.get("max_categories", 0):
        return RedirectResponse(url="/panel/my-categories?error=max_categories", status_code=302)
    sub.categories = db.query(Category).filter(Category.id.in_(kategoriler)).all() if kategoriler else []

    kullan_ozel = bool(kullan_ozel_zamanlama) and plan["custom_schedule_allowed"]
    sub.use_custom_schedule = kullan_ozel
    if kullan_ozel:
        saat, dakika = (int(p) for p in zaman.split(":"))
        sub.custom_days_of_week = ",".join(gunler) if gunler else "mon,tue,wed,thu,fri,sat,sun"
        sub.custom_hour = saat
        sub.custom_minute = dakika

    db.commit()
    db.refresh(sub)
    reschedule_subscriber_job(sub)
    return RedirectResponse(url="/panel/my-categories", status_code=302)


@router.post("/my-categories/detect-location")
def detect_location_individual(request: Request, lat: float = Form(...), lon: float = Form(...),
                                db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    plan = get_plan(org.plan, org.account_type)
    if org.account_type != "individual":
        return JSONResponse({"error": "not_applicable"}, status_code=400)
    if not plan.get("location_insights"):
        return JSONResponse({"error": "location_insights_not_allowed"}, status_code=403)
    sub = _kendi_aboneligini_bul(db, org.id)
    if not sub:
        return JSONResponse({"error": "no_subscriber"}, status_code=400)
    return JSONResponse(_konum_isle(db, sub, lat, lon))


@router.post("/subscribers/{sub_id}/detect-location")
def detect_location_subscriber(request: Request, sub_id: int, lat: float = Form(...), lon: float = Form(...),
                                db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if not sub:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(_konum_isle(db, sub, lat, lon))


@router.post("/subscribers/{sub_id}/suggest-subject")
def suggest_subject(request: Request, sub_id: int, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    plan = get_plan(org.plan, org.account_type)
    if not plan.get("ai_subject_suggestions"):
        return JSONResponse({"error": "not_allowed"}, status_code=403)
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if not sub:
        return JSONResponse({"error": "not_found"}, status_code=404)
    kategori_isimleri = [k.name for k in sub.categories][:3]
    ana_konu = kategori_isimleri[0] if kategori_isimleri else "gündem"
    yer = sub.detected_city or "seçtiğiniz şehir"
    basliklar = [
        {"type": "Kısa Başlık", "text": f"{org.brand_name} ile {ana_konu} haberlerinde bugün öne çıkanlar"},
        {"type": "Dikkat Çeken Giriş", "text": f"{yer} için seçkin {ana_konu} içeriklerini kaçırmayın"},
        {"type": "Eylem Çağrısı", "text": f"Hemen keşfedin: {ana_konu} haberlerinde yeni fırsatlar"},
    ]
    return JSONResponse({"suggestions": basliklar})


@router.post("/subscribers/{sub_id}/set-city")
def set_city_subscriber(request: Request, sub_id: int, city: str = Form(...), db: Session = Depends(get_db)):
    """Admin, bir abonenin bölgesini elle girer (tarayıcı konumu abonenin değil admin'in konumunu verir)."""
    guard, org = _guard(request, db)
    if guard:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.organization_id == org.id).first()
    if not sub:
        return JSONResponse({"error": "not_found"}, status_code=404)
    city = city.strip()
    sub.detected_city = city or None
    db.commit()
    if city:
        kelimeler = [k for k in city.lower().split() if k]
        eslesenler = []
        for kategori in db.query(Category).all():
            if not kategori.city:
                continue
            kategori_city = kategori.city.lower()
            if any(kelime in kategori_city for kelime in kelimeler):
                eslesenler.append(kategori)
    else:
        eslesenler = []
    return JSONResponse({"city": city or None, "matched": [{"id": c.id, "name": c.name} for c in eslesenler]})


# --- Mail teması / rengi ---

TEMA_RENK_SECENEKLERI = [
    ("#111111", "Siyah"),
    ("#1e3a5f", "Lacivert"),
    ("#0f766e", "Yeşil"),
    ("#c2410c", "Amber"),
    ("#7c2d12", "Bordo"),
]

TEMA_SECENEKLERI = [
    ("klasik", "Klasik", "Şık şehir manzarasıyla modern bir görünüm", "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80"),
    ("minimal", "Minimal", "Temiz ve sakin bir arka plan", "https://images.unsplash.com/photo-1517048676731-7d7df1d36cf1?auto=format&fit=crop&w=1200&q=80"),
    ("modern", "Modern", "Güncel ve çağdaş bir his", "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?auto=format&fit=crop&w=1200&q=80"),
    ("editorial", "Editorial", "Gazete dergisi havası", "https://images.unsplash.com/photo-1516979187457-637abb4f9353?auto=format&fit=crop&w=1200&q=80"),
    ("bold", "Bold", "Güçlü ve dikkat çekici bir görünüm", "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80"),
    ("fresh", "Fresh", "Yenileyici ve canlı bir atmosfer", "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?auto=format&fit=crop&w=1200&q=80"),
    ("dark", "Dark", "Koyu ve premium bir dokunuş", "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=1200&q=80"),
    ("aurora", "Aurora", "Parlak ve modern bir öne çıkış", "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1200&q=80"),
    ("ocean", "Ocean", "Serin deniz ve açık hava hissi", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80"),
    ("sunset", "Sunset", "Sıcak ve samimi bir ton", "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?auto=format&fit=crop&w=1200&q=80"),
    ("elegant", "Elegant", "Şık ve sofistike bir düzen", "https://images.unsplash.com/photo-1524758631624-e2822e304c36?auto=format&fit=crop&w=1200&q=80"),
    ("neon", "Neon", "Enerjik ve modern bir stil", "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"),
]


@router.get("/theme")
def theme_page(request: Request, db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    ornek_haberler = {
        "Örnek Kategori": [
            type("H", (), {"title": "Örnek haber başlığı burada görünür", "link": "#"})(),
            type("H", (), {"title": "İkinci bir örnek haber başlığı", "link": "#"})(),
        ]
    }
    onizleme_html = html_bulten_olustur(ornek_haberler, org.brand_name, org.mail_theme, org.mail_accent)
    plan = get_plan(org.plan, org.account_type)
    return templates.TemplateResponse("theme.html", {
        "request": request, "user": current_user_email(request), "org": org,
        "renkler": TEMA_RENK_SECENEKLERI, "tema_secenekleri": TEMA_SECENEKLERI,
        "onizleme_html": onizleme_html, "plan": plan,
    })


@router.post("/theme/update")
def theme_update(request: Request, mail_theme: str = Form(...), mail_accent: str = Form(...),
                  db: Session = Depends(get_db)):
    guard, org = _guard(request, db)
    if guard:
        return guard
    izinli_tema_degerleri = [tema[0] for tema in TEMA_SECENEKLERI]
    if mail_theme not in izinli_tema_degerleri:
        mail_theme = "klasik"
    plan = get_plan(org.plan, org.account_type)
    if not plan.get("custom_branding"):
        return RedirectResponse(url="/panel/theme?error=branding_not_allowed", status_code=302)
    izinli_renkler = [r[0] for r in TEMA_RENK_SECENEKLERI]
    if mail_accent not in izinli_renkler:
        mail_accent = "#111111"
    izinli_tema_degerleri = [tema[0] for tema in TEMA_SECENEKLERI]
    if mail_theme not in izinli_tema_degerleri:
        mail_theme = "klasik"
    org.mail_theme = mail_theme
    org.mail_accent = mail_accent
    db.commit()
    return RedirectResponse(url="/panel/theme", status_code=302)

