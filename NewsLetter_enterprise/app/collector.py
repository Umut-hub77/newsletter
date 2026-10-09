"""
Toplayıcı katman.

Sorumluluğu tek: aktif Source kayıtlarındaki RSS beslemelerini okumak,
yeni haberleri MERKEZİ news_items tablosuna yazmak.

GÜVENLİK NOTU: discover_feed_url artık dışarıdan (SaaS müşterisinden)
gelen keyfi bir URL alıyor. Bu fonksiyon, sunucunun kendi iç ağına veya
localhost'a istek atmasını (SSRF) engellemek için hedef adresi çözüp
özel/yerel IP aralıklarını reddeder. Bu, mükemmel bir SSRF koruması
değildir (DNS rebinding gibi ileri teknikler için bir ters proxy/allow-list
katmanı önerilir) ama temel ve yaygın saldırı yüzeyini kapatır.
"""
import ipaddress
import logging
import re
import socket
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urljoin, urlparse

import feedparser
from sqlalchemy.orm import Session

from app.config import settings
from app.models import NewsItem, Source

logger = logging.getLogger("collector")

_LINK_TAG_RE = re.compile(
    r"<link[^>]+rel=[\"']alternate[\"'][^>]*type=[\"']application/(?:rss|atom)\+xml[\"'][^>]*>"
    r"|<link[^>]+type=[\"']application/(?:rss|atom)\+xml[\"'][^>]*rel=[\"']alternate[\"'][^>]*>",
    re.IGNORECASE,
)
_HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)

_COMMON_FEED_PATHS = ["/feed", "/feed/", "/rss", "/rss/", "/rss.xml", "/atom.xml", "/feed.xml", "?feed=rss2"]


def _is_safe_host(hostname: str) -> bool:
    """Hostname'in çözümlendiği TÜM IP'lerin genel (public) olmasını zorunlu kılar."""
    if not hostname or hostname.lower() in ("localhost",):
        return False
    try:
        adresler = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for adres in adresler:
        ip_str = adres[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        ):
            return False
    return True


def _validate_url(url: str) -> str:
    """Şemayı ve hedef IP'yi doğrular; güvenliyse normalleştirilmiş URL'yi döner."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Sadece http/https adresleri desteklenir")
    if not _is_safe_host(parsed.hostname or ""):
        raise ValueError("Bu adrese erişim güvenlik nedeniyle engellendi")
    return url


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (haberbotu-collector)"})
    with urllib.request.urlopen(req, timeout=settings.RSS_TIMEOUT_SECONDS) as resp:
        raw = resp.read(500_000)
    return raw.decode("utf-8", errors="ignore")


def _looks_like_feed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if not _is_safe_host(parsed.hostname or ""):
            return False
        feed = feedparser.parse(url)
        return bool(feed.entries)
    except Exception:
        return False


def discover_feed_url(url: str) -> str:
    """
    Kullanıcının girdiği düz site linkinden gerçek RSS/Atom besleme adresini
    otomatik bulur. Her aday adres güvenlik doğrulamasından geçirilir.
    Bulamazsa veya adres güvensizse ValueError fırlatır.
    """
    url = _validate_url(url)

    if _looks_like_feed(url):
        return url

    try:
        html = _fetch_html(url)
        for tag in _LINK_TAG_RE.findall(html):
            href_match = _HREF_RE.search(tag)
            if href_match:
                candidate = urljoin(url, href_match.group(1))
                try:
                    candidate = _validate_url(candidate)
                except ValueError:
                    continue
                if _looks_like_feed(candidate):
                    return candidate
    except (urllib.error.URLError, TimeoutError, OSError):
        pass

    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in _COMMON_FEED_PATHS:
        candidate = base + path if not path.startswith("?") else url.rstrip("/") + path
        if _looks_like_feed(candidate):
            return candidate

    raise ValueError(
        f"'{url}' adresinde RSS/Atom beslemesi bulunamadı. "
        "Site RSS sunmuyor olabilir; RSS URL'sini biliyorsanız doğrudan onu girin."
    )


def _parse_published(entry) -> datetime | None:
    if getattr(entry, "published_parsed", None):
        try:
            return datetime(*entry.published_parsed[:6])
        except (TypeError, ValueError):
            return None
    return None


def collect_source(db: Session, source: Source) -> int:
    """Tek bir kaynağı çeker, yeni haberleri DB'ye yazar. Eklenen sayıyı döner."""
    eklenen = 0
    eski_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(settings.RSS_TIMEOUT_SECONDS)
    try:
        feed = feedparser.parse(source.feed_url)
        if feed.bozo and not feed.entries:
            raise (feed.bozo_exception or ValueError("Akış ayrıştırılamadı"))

        for entry in feed.entries:
            baslik = getattr(entry, "title", None)
            link = getattr(entry, "link", None)
            if not baslik or not link:
                continue
            link = link.strip()

            var_mi = db.query(NewsItem.id).filter(NewsItem.link == link).first()
            if var_mi:
                continue

            db.add(NewsItem(
                title=baslik.strip(),
                link=link,
                summary=getattr(entry, "summary", None),
                published_at=_parse_published(entry),
                source_id=source.id,
                category_id=source.category_id,
            ))
            eklenen += 1

        source.last_fetched_at = datetime.utcnow()
        source.last_error = None
        db.commit()
        logger.info("Kaynak OK: %s -> %d yeni haber", source.name, eklenen)
    except Exception as exc:
        db.rollback()
        source.last_error = str(exc)[:500]
        source.last_fetched_at = datetime.utcnow()
        db.commit()
        logger.error("Kaynak HATA: %s -> %s", source.name, exc)
    finally:
        socket.setdefaulttimeout(eski_timeout)

    return eklenen


def collect_all(db: Session) -> dict:
    """Platformdaki tüm aktif (paylaşımlı) kaynakları toplar. {source_name: eklenen_sayi} döner."""
    sonuc = {}
    kaynaklar = db.query(Source).filter(Source.active.is_(True)).all()
    for source in kaynaklar:
        sonuc[source.name] = collect_source(db, source)
    return sonuc