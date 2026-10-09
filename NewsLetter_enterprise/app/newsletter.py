"""
Bülten katmanı. Haber içeriği (kategori/kaynak/haber) artık PLATFORM
GENELİ paylaşımlı bir havuz; sadece gönderim (kime, hangi kategoriler,
ne zaman) organizasyon/abone bazında kişiselleştirilir.
"""
import html
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Category, NewsItem, NewsletterLog, Organization, Source, Subscriber

logger = logging.getLogger("newsletter")


def _tema_paleti(theme: str, accent: str) -> dict:
    accent = accent if _hex_guvenli_mi(accent) else "#111111"
    tema_gorselleri = {
        "klasik": "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80",
        "minimal": "https://images.unsplash.com/photo-1517048676731-7d7df1d36cf1?auto=format&fit=crop&w=1200&q=80",
        "modern": "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?auto=format&fit=crop&w=1200&q=80",
        "editorial": "https://images.unsplash.com/photo-1516979187457-637abb4f9353?auto=format&fit=crop&w=1200&q=80",
        "bold": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80",
        "fresh": "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?auto=format&fit=crop&w=1200&q=80",
        "dark": "https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=1200&q=80",
        "aurora": "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1200&q=80",
        "ocean": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
        "sunset": "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?auto=format&fit=crop&w=1200&q=80",
        "elegant": "https://images.unsplash.com/photo-1524758631624-e2822e304c36?auto=format&fit=crop&w=1200&q=80",
        "neon": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    }
    tema_gorselleri = {
        key: (value if "w=900" in value else f"{value}&w=900&q=75")
        for key, value in tema_gorselleri.items()
    }
    if theme == "minimal":
        return {
            "header_bg": "#ffffff",
            "header_text": "#111111",
            "header_border": accent,
            "meta_color": "#6b7280",
            "body_bg": "#f8fafc",
            "card_bg": "#ffffff",
            "card_border": "#e5e7eb",
            "shadow": "0 10px 28px rgba(15, 23, 42, 0.06)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.98)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.98)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "modern":
        return {
            "header_bg": "#0f172a",
            "header_text": "#ffffff",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.78)",
            "body_bg": "#f8fafc",
            "card_bg": "#ffffff",
            "card_border": "#e2e8f0",
            "shadow": "0 12px 32px rgba(15, 23, 42, 0.08)",
            "text_color": "#0f172a",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "editorial":
        return {
            "header_bg": "#f8f5ef",
            "header_text": "#111111",
            "header_border": accent,
            "meta_color": "#6b7280",
            "body_bg": "#f7f4ee",
            "card_bg": "#ffffff",
            "card_border": "#dfd8cd",
            "shadow": "0 8px 24px rgba(66, 48, 24, 0.08)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "bold":
        return {
            "header_bg": accent,
            "header_text": "#ffffff",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.78)",
            "body_bg": "#fef2f2",
            "card_bg": "#ffffff",
            "card_border": "#f3d8d8",
            "shadow": "0 12px 32px rgba(124, 45, 18, 0.1)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "fresh":
        return {
            "header_bg": "#ecfeff",
            "header_text": "#0f172a",
            "header_border": accent,
            "meta_color": "#64748b",
            "body_bg": "#f8fffe",
            "card_bg": "#ffffff",
            "card_border": "#d1fae5",
            "shadow": "0 10px 28px rgba(15, 23, 42, 0.06)",
            "text_color": "#0f172a",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "dark":
        return {
            "header_bg": "#111827",
            "header_text": "#f9fafb",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.72)",
            "body_bg": "#030712",
            "card_bg": "#111827",
            "card_border": "#374151",
            "shadow": "0 12px 32px rgba(0, 0, 0, 0.25)",
            "text_color": "#f9fafb",
            "content_bg": "rgba(10,11,20,0.94)",
            "content_text_color": "#f8fafc",
            "category_color": "#ffffff",
            "category_label_bg": "rgba(255,255,255,0.08)",
            "category_label_text": "#f8fafc",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "aurora":
        return {
            "header_bg": "#312e81",
            "header_text": "#ffffff",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.78)",
            "body_bg": "#f5f3ff",
            "card_bg": "#ffffff",
            "card_border": "#ddd6fe",
            "shadow": "0 12px 32px rgba(49, 46, 129, 0.12)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.94)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "ocean":
        return {
            "header_bg": "#0f766e",
            "header_text": "#ffffff",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.8)",
            "body_bg": "#f0fdfa",
            "card_bg": "#ffffff",
            "card_border": "#bfdbfe",
            "shadow": "0 10px 24px rgba(15, 118, 110, 0.12)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "sunset":
        return {
            "header_bg": "#c2410c",
            "header_text": "#ffffff",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.78)",
            "body_bg": "#fff7ed",
            "card_bg": "#ffffff",
            "card_border": "#fed7aa",
            "shadow": "0 10px 28px rgba(194, 65, 12, 0.12)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "elegant":
        return {
            "header_bg": "#1f2937",
            "header_text": "#f9fafb",
            "header_border": accent,
            "meta_color": "rgba(255,255,255,0.72)",
            "body_bg": "#fafaf9",
            "card_bg": "#ffffff",
            "card_border": "#e5e7eb",
            "shadow": "0 12px 32px rgba(31, 41, 55, 0.08)",
            "text_color": "#111111",
            "content_bg": "rgba(255,255,255,0.96)",
            "content_text_color": "#111111",
            "category_color": accent,
            "category_label_bg": "rgba(255,255,255,0.92)",
            "category_label_text": "#111111",
            "background_image": tema_gorselleri.get(theme),
        }
    if theme == "neon":
        return {
            "header_bg": "#111111",
            "header_text": "#fef3c7",
            "header_border": accent,
            "meta_color": "rgba(254, 243, 199, 0.8)",
            "body_bg": "#0b0b0b",
            "card_bg": "#111111",
            "card_border": accent,
            "shadow": "0 12px 32px rgba(17, 17, 17, 0.15)",
            "text_color": "#fef3c7",
            "content_bg": "rgba(5, 5, 10, 0.92)",
            "content_text_color": "#fef3c7",
            "category_color": "#ffffff",
            "category_label_bg": "rgba(255,255,255,0.06)",
            "category_label_text": "#fef3c7",
            "background_image": None,
        }
    return {
        "header_bg": accent,
        "header_text": "#ffffff",
        "header_border": accent,
        "meta_color": "rgba(255,255,255,0.78)",
        "body_bg": "#f4f4f4",
        "card_bg": "#ffffff",
        "card_border": "#e0e0e0",
        "shadow": "0 8px 24px rgba(17, 17, 17, 0.06)",
        "text_color": "#111111",
        "content_bg": "rgba(255,255,255,0.96)",
        "content_text_color": "#111111",
        "category_color": accent,
        "category_label_bg": "rgba(255,255,255,0.92)",
        "category_label_text": "#111111",
        "background_image": tema_gorselleri.get(theme),
    }


def get_recent_news_by_category(db: Session, lookback_hours: int | None = None,
                                 per_category: int | None = None,
                                 category_ids: list[int] | None = None) -> dict:
    lookback_hours = lookback_hours or settings.NEWSLETTER_LOOKBACK_HOURS
    per_category = per_category or settings.ARTICLES_PER_CATEGORY
    esik = datetime.utcnow() - timedelta(hours=lookback_hours)

    kategori_sorgu = db.query(Category).order_by(Category.name)
    if category_ids is not None:
        kategori_sorgu = kategori_sorgu.filter(Category.id.in_(category_ids))

    sonuc = {}
    for kategori in kategori_sorgu.all():
        kaynaklar = (
            db.query(Source)
            .filter(Source.category_id == kategori.id, Source.active.is_(True))
            .order_by(Source.id)
            .all()
        )
        if not kaynaklar:
            sonuc[kategori.name] = []
            continue

        adet = len(kaynaklar)
        taban_kota, kalan = divmod(per_category, adet)

        kaynak_bazli_listeler = []
        for i, kaynak in enumerate(kaynaklar):
            kota = taban_kota + (1 if i < kalan else 0)
            if kota <= 0:
                continue
            items = (
                db.query(NewsItem)
                .filter(NewsItem.source_id == kaynak.id, NewsItem.fetched_at >= esik)
                .order_by(NewsItem.fetched_at.desc())
                .limit(kota)
                .all()
            )
            kaynak_bazli_listeler.append(items)

        karisik = []
        i = 0
        while len(karisik) < per_category:
            eklendi = False
            for liste in kaynak_bazli_listeler:
                if i < len(liste):
                    karisik.append(liste[i])
                    eklendi = True
                    if len(karisik) >= per_category:
                        break
            if not eklendi:
                break
            i += 1

        sonuc[kategori.name] = karisik
    return sonuc


def _hex_guvenli_mi(renk: str) -> bool:
    """Vurgu rengi sadece güvenli bir hex kod olabilir (HTML/CSS enjeksiyonunu önler)."""
    if not renk or not renk.startswith("#") or len(renk) not in (4, 7):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in renk[1:])


def sort_news_for_location(news_items: list, location_name: str | None) -> list:
    """Konum adı varsa önce bölgesel/konuma ait haberleri getirir, sonrasında diğerlerini ekler."""
    if not location_name:
        return list(news_items)

    location_key = location_name.lower().strip()
    if not location_key:
        return list(news_items)

    local_items = []
    other_items = []
    for item in news_items:
        text = " ".join(filter(None, [getattr(item, "title", ""), getattr(item, "summary", "")])).lower()
        if location_key in text:
            local_items.append(item)
        else:
            other_items.append(item)
    return local_items + other_items


def _haber_bloklari_olustur(kategorize_haberler: dict, accent: str, text_color: str = "#111111", category_color: str | None = None, palet: dict | None = None) -> str:
    bloklar = ""
    category_color = category_color or accent
    palet = palet or {}
    for kategori, haberler in kategorize_haberler.items():
        if not haberler:
            continue
        bloklar += f"""
        <tr><td style="padding: 28px 0 10px 0; border-bottom: 1px solid #dcdcdc;">
        <span style="font-size: 13px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: {category_color}; display: inline-block;">
        {html.escape(kategori)}
        </span></td></tr>
        """
        for haber in haberler:
            baslik = html.escape(haber.title)
            link = html.escape(haber.link, quote=True)
            bloklar += f"""
            <tr><td style="padding: 14px 0; border-bottom: 1px solid #eeeeee;">
            <a href="{link}" style="color: {palet['content_text_color']}; text-decoration: none; font-size: 15px; line-height: 1.5; font-weight: 600;">
            {baslik}
            </a></td></tr>
            """
    return bloklar


def html_bulten_olustur(kategorize_haberler: dict, marka_adi: str,
                         theme: str = "klasik", accent: str = "#111111",
                         location_name: str | None = None) -> str:
    accent = accent if _hex_guvenli_mi(accent) else "#111111"
    palet = _tema_paleti(theme, accent)
    bugun = datetime.now().strftime("%d.%m.%Y")
    haber_var_mi = any(kategorize_haberler.values())
    if haber_var_mi:
        sirali_haberler = {}
        for kategori, haberler in kategorize_haberler.items():
            sirali_haberler[kategori] = sort_news_for_location(haberler, location_name)
        icerik = _haber_bloklari_olustur(sirali_haberler, accent, palet["content_text_color"], palet.get("category_color"), palet)
    else:
        icerik = f'<tr><td style="padding:30px 0;color:{palet["meta_color"]};font-size:14px;">Bugün için görüntülenecek haber bulunamadı.</td></tr>'

    header_style = f"padding:28px 32px 18px 32px;background-color:{palet['header_bg']};border-bottom:2px solid {palet['header_border']};"
    if palet.get("background_image"):
        header_style += f"background-image:linear-gradient(135deg, rgba(255,255,255,0.18), rgba(255,255,255,0.08)), url('{palet['background_image']}');background-size:cover;background-position:center;background-repeat:no-repeat;"
    else:
        header_style += f"background-image:linear-gradient(135deg, rgba(255,255,255,0.18), rgba(255,255,255,0.06));"
    ust_bant = f"""
    <tr><td style="{header_style}">
    <span style="font-size:20px;font-weight:700;color:{palet['header_text']};">{html.escape(marka_adi)}</span>
    <span style="float:right;font-size:13px;color:{palet['meta_color']};padding-top:4px;">{bugun}</span>
    </td></tr>
    """

    body_style = f"background-color:{palet['body_bg']};padding:30px 0;"
    card_style = f"background-color:{palet['card_bg']};border:1px solid {palet['card_border']};box-shadow:{palet['shadow']};"
    if palet.get("background_image"):
        card_style += f"background-image:linear-gradient(135deg, rgba(255,255,255,0.82), rgba(255,255,255,0.72)), url('{palet['background_image']}');background-size:cover;background-position:center;background-repeat:no-repeat;"

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="{body_style}">
    <tr><td align="center">
    <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="{card_style}">
    {ust_bant}
    <tr><td style="padding:0 32px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    {icerik}
    </table></td></tr>
    <tr><td style="padding:24px 32px;color:{palet['meta_color']};font-size:12px;">Bu bülten otomatik olarak oluşturulmuştur.</td></tr>
    </table></td></tr></table>
    """


def duz_metin_bulten_olustur(kategorize_haberler: dict, marka_adi: str) -> str:
    satirlar = [f"{marka_adi} - {datetime.now().strftime('%d.%m.%Y')}", ""]
    for kategori, haberler in kategorize_haberler.items():
        if not haberler:
            continue
        satirlar.append(kategori.upper())
        for haber in haberler:
            satirlar.append(f"- {haber.title}")
            satirlar.append(f"  {haber.link}")
        satirlar.append("")
    return "\n".join(satirlar)


def _mesaj_olustur(kategorize_haberler: dict, alici_email: str, marka_adi: str,
                    theme: str, accent: str, location_name: str | None = None) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{marka_adi} - {datetime.now().strftime('%d.%m.%Y')}"
    msg["From"] = settings.MAIL_FROM
    msg["To"] = alici_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText(duz_metin_bulten_olustur(kategorize_haberler, marka_adi), "plain", "utf-8"))
    msg.attach(MIMEText(html_bulten_olustur(kategorize_haberler, marka_adi, theme, accent, location_name), "html", "utf-8"))
    return msg


def send_newsletter(db: Session, organization_id: int, dry_run: bool = False,
                     subscriber_ids: list[int] | None = None) -> bool:
    """
    Bir organizasyonun aktif abonelerine gönderir. subscriber_ids verilirse
    sadece o abonelere gönderilir. Her abone kendi kategorileriyle
    kişiselleştirilmiş bir e-posta alır.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not settings.MAIL_FROM:
        logger.error("SMTP_USER / SMTP_PASSWORD / MAIL_FROM ayarlanmamış (.env)")
        return False

    org = db.get(Organization, organization_id)
    marka_adi = org.brand_name if org else settings.APP_BRAND_NAME
    tema = org.mail_theme if org else "klasik"
    vurgu_rengi = org.mail_accent if org else "#111111"

    sorgu = db.query(Subscriber).filter(
        Subscriber.organization_id == organization_id, Subscriber.active.is_(True)
    )
    if subscriber_ids is not None:
        sorgu = sorgu.filter(Subscriber.id.in_(subscriber_ids))
    aboneler = sorgu.all()

    if not aboneler:
        logger.warning("Org #%s: gönderilecek aktif abone yok", organization_id)
        return False

    basari_sayisi = 0
    toplam_haber_sayisi = 0
    hata_notu = None
    basarili = False

    try:
        server = None
        if not dry_run:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        for abone in aboneler:
            kategori_idler = [k.id for k in abone.categories] or None
            kategorize = get_recent_news_by_category(db, category_ids=kategori_idler)
            haber_sayisi = sum(len(v) for v in kategorize.values())
            if haber_sayisi == 0:
                continue

            if dry_run:
                basari_sayisi += 1
                toplam_haber_sayisi += haber_sayisi
                continue

            location_name = getattr(abone, "detected_city", None) or None
            msg = _mesaj_olustur(kategorize, abone.email, marka_adi, tema, vurgu_rengi, location_name)
            server.sendmail(settings.MAIL_FROM, [abone.email], msg.as_string())
            basari_sayisi += 1
            toplam_haber_sayisi += haber_sayisi

        if server:
            server.quit()

        basarili = basari_sayisi > 0
        if not basarili:
            hata_notu = "Gösterilecek haberi olan aktif abone bulunamadı"
    except smtplib.SMTPAuthenticationError:
        hata_notu = "SMTP kimlik doğrulama hatası (kullanıcı/şifre veya uygulama parolası hatalı)"
        logger.error(hata_notu)
        basarili = False
    except (smtplib.SMTPException, OSError) as e:
        hata_notu = str(e)
        logger.error("Mail gönderilirken hata: %s", e)
        basarili = False

    if not dry_run:
        db.add(NewsletterLog(
            organization_id=organization_id,
            recipient_count=basari_sayisi,
            article_count=toplam_haber_sayisi,
            success=basarili,
            note=hata_notu,
        ))
        db.commit()

    return basarili