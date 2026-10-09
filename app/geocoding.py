"""
Tarayıcıdan gelen enlem/boylamı bir şehir adına çevirir. Sunucu tarafında
yapılır (tarayıcıdan doğrudan çağırmak yerine) çünkü:
  - Nominatim'in kullanım politikası bir User-Agent header'ı zorunlu kılar
  - Tek bir yerden hız sınırlaması/hata yönetimi yapmak daha güvenilir

Kaynak: OpenStreetMap Nominatim (ücretsiz, kullanım politikasına dikkat
edilmeli: https://operations.osmfoundation.org/policies/nominatim/).
Yoğun kullanımda kendi Nominatim örneğinize veya ücretli bir geocoding
servisine geçmeniz gerekebilir.
"""
import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

def resolve_region(lat: float, lon: float) -> str | None:
    """Enlem/boylamdan en olası bölge adını döner; bulunamazsa None."""
    params = urllib.parse.urlencode({
        "lat": lat, "lon": lon, "format": "json", "zoom": 10, "accept-language": "tr",
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        # User-Agent'ı botuna uygun şekilde güncelledik
        headers={"User-Agent": "NewsLetter-App/1.0 (Bölgesel Haber Botu)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            veri = json.loads(resp.read().decode("utf-8"))
        
        adres = veri.get("address", {})
        
        # Önceliği 'region' anahtarına veriyoruz. 
        # Bulamazsa il, şehir veya eyalet bilgisini döner.
        return (
            adres.get("region") or 
            adres.get("province") or 
            adres.get("city") or 
            adres.get("state")
        )
    except Exception as exc:
        logger.warning("Ters coğrafi kodlama başarısız (%s, %s): %s", lat, lon, exc)
        return None

def fetch_local_news(lat: float, lon: float, haber_kaynaklari: list) -> list:
    """
    Konumu tespit eder ve kullanıcının kaynaklarındaki haberler içinde 
    o bölgeyle eşleşenleri döndürür.
    """
    bolge_adi = resolve_region(lat, lon)
    
    if not bolge_adi:
        logger.info("Konum çözümlenemediği için bölgesel haber getirilemedi.")
        return []

    logger.info(f"Tespit edilen bölge: '{bolge_adi}'. İlgili haberler filtreleniyor...")
    
    bolgesel_haberler = []
    aranan_kelime = bolge_adi.lower()
    
    # Haber kaynaklarında filtreleme yapıyoruz (Haberlerin dict formatında olduğunu varsayıyoruz)
    for haber in haber_kaynaklari:
        # Haberin başlığında, özetinde veya içeriğinde bölge adı geçiyor mu?
        baslik = haber.get("baslik", "").lower()
        icerik = haber.get("icerik", "").lower()
        
        if aranan_kelime in baslik or aranan_kelime in icerik:
            bolgesel_haberler.append(haber)
            
    return bolgesel_haberler