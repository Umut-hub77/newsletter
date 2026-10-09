"""
Migrasyon sonrası oluşan geçici (...@migrated.local) admin e-postasını
gerçek e-postanızla değiştirir. Şifreniz etkilenmez.

Kullanım:
    python set_admin_email.py yenieposta@sirketiniz.com
"""
import sys

from app.database import SessionLocal
from app.models import AdminUser

if len(sys.argv) != 2:
    print("Kullanım: python set_admin_email.py yenieposta@sirketiniz.com")
    sys.exit(1)

yeni_email = sys.argv[1].strip().lower()

db = SessionLocal()
try:
    admin = db.query(AdminUser).first()
    if not admin:
        print("Hiç admin kullanıcı bulunamadı.")
        sys.exit(1)
    eski = admin.email
    admin.email = yeni_email
    db.commit()
    print(f"Güncellendi: {eski} -> {yeni_email}")
finally:
    db.close()
