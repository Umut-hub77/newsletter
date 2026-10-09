"""
Shopier ödeme entegrasyonu.

MİMARİ FARK (Stripe'tan farklı olarak): Shopier'de otomatik tekrarlayan
(recurring) abonelik / müşteri portalı YOKTUR. Her ödeme tek seferliktir.
Bu yüzden:
  1) Kullanıcı "Starter"ı seçer -> Shopier'in barındırdığı ödeme sayfasına
     imzalı bir form ile yönlendirilir.
  2) Ödeme tamamlanınca Shopier, sizin panelinizde tanımladığınız
     "Bildirim URL'si"ne (OSB - Otomatik Sipariş Bildirimi) sunucu-sunucu
     bir POST isteği atar. Organizasyonun planı ve subscription_expires_at
     (bugün + SUBSCRIPTION_DAYS) burada güncellenir.
  3) Süre dolduğunda scheduler.py içindeki günlük iş organizasyonu
     otomatik olarak Free plana düşürür (bkz. check_expired_subscriptions).

ÖNEMLİ DOĞRULAMA NOTU: Aşağıdaki alan adları, sabitler (ör. para birimi
ve ürün tipi kodları) ve imza (signature) hesaplama yöntemi, Shopier'in
herkese açık PHP SDK'sı ve topluluk örneklerinden derlenmiştir. Canlıya
almadan önce MUTLAKA Shopier panelinizdeki Entegrasyonlar > API
sayfasındaki güncel dokümantasyonla karşılaştırın ve panelde "Test Modu"
açıkken uçtan uca bir deneme yapın.
"""
import base64
import hashlib
import hmac
import logging
import random

from app.config import settings

logger = logging.getLogger("billing")

SHOPIER_PAYMENT_URL = "https://www.shopier.com/ShowProduct/api_pay4.php"


def _imza_uret(random_nr: str, order_id: str) -> str:
    veri = f"{random_nr}{order_id}".encode("utf-8")
    return base64.b64encode(
        hmac.new(settings.SHOPIER_API_SECRET.encode("utf-8"), veri, hashlib.sha256).digest()
    ).decode("utf-8")


def build_payment_form_fields(order_id: str, amount_try: float, product_name: str,
                               buyer_email: str, buyer_name: str = "Musteri",
                               buyer_surname: str = "Kullanici") -> dict:
    """
    Shopier ödeme sayfasına POST edilecek gizli form alanlarını üretir.
    Bu alanlar template'te otomatik gönderilen bir <form>'a gömülür.
    """
    random_nr = str(random.randint(100000, 999999))
    alanlar = {
        "API_key": settings.SHOPIER_API_KEY,
        "website_index": settings.SHOPIER_WEBSITE_INDEX,
        "platform_order_id": order_id,
        "product_name": product_name,
        "product_type": "1",  # 1 = sanal/dijital ürün (fiziksel kargo yok)
        "buyer_name": buyer_name,
        "buyer_surname": buyer_surname,
        "buyer_email": buyer_email,
        "buyer_account_age": "0",
        "buyer_id_nr": "11111111111",
        "billing_address": "Dijital teslimat - adres gerekmiyor",
        "billing_city": "Istanbul",
        "billing_country": "Turkey",
        "billing_postcode": "34000",
        "shipping_address": "Dijital teslimat - adres gerekmiyor",
        "shipping_city": "Istanbul",
        "shipping_country": "Turkey",
        "shipping_postcode": "34000",
        "total_order_value": f"{amount_try:.2f}",
        "currency": "0",  # 0 = TRY
        "platform": "0",
        "is_in_frame": "0",
        "current_language": "0",  # 0 = TR
        "modul_version": settings.SHOPIER_MODULE_VERSION,
        "random_nr": random_nr,
    }
    alanlar["signature"] = _imza_uret(random_nr, order_id)
    return alanlar


def verify_notification_signature(form_data: dict) -> bool:
    """Shopier'den gelen OSB (webhook) bildiriminin imzasını doğrular."""
    random_nr = form_data.get("random_nr", "")
    order_id = form_data.get("platform_order_id", "")
    gelen_imza = form_data.get("signature", "")
    beklenen_imza = _imza_uret(random_nr, order_id)
    return hmac.compare_digest(gelen_imza, beklenen_imza)