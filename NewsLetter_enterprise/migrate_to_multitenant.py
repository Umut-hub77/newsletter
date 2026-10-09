"""
TEK SEFERLİK migrasyon: mevcut tek-kiracılı (Sefine IT) veritabanını yeni
çok-kiracılı (multi-tenant/SaaS) şemaya taşır. Mevcut haberleriniz,
kaynaklarınız ve abone listeniz KORUNUR.

ÇALIŞTIRMADAN ÖNCE data/haberbotu.db dosyanızın bir yedeğini alın.

Kullanım (proje kökünden, venv aktifken, UYGULAMAYI YENİDEN BAŞLATMADAN ÖNCE):
    python migrate_to_multitenant.py
"""
import secrets
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "data/haberbotu.db"


def sutun_var_mi(cur, tablo, sutun):
    cur.execute(f"PRAGMA table_info({tablo})")
    return sutun in [r[1] for r in cur.fetchall()]


def tablo_var_mi(cur, tablo):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tablo,))
    return cur.fetchone() is not None


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if tablo_var_mi(cur, "organizations"):
        print("Zaten çok-kiracılı şemaya geçilmiş (organizations tablosu var). Bir şey yapmıyorum.")
        return

    if not tablo_var_mi(cur, "subscribers"):
        print("Eski tablo yapısı bulunamadı; sıfır bir kurulumdasınız, migrasyona gerek yok.")
        return

    print("Migrasyon başlıyor...")

    cur.execute("""
        CREATE TABLE organizations (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(200) UNIQUE NOT NULL,
            brand_name VARCHAR(200) NOT NULL,
            owner_email VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            plan VARCHAR(30) NOT NULL DEFAULT 'free',
            subscription_status VARCHAR(30) NOT NULL DEFAULT 'trialing',
            trial_ends_at DATETIME,
            subscription_expires_at DATETIME,
            renewal_reminder_sent_at DATETIME,
            api_key VARCHAR(64) UNIQUE
        )
    """)

    eski_admin_username = None
    if tablo_var_mi(cur, "admin_users") and sutun_var_mi(cur, "admin_users", "username"):
        cur.execute("SELECT username FROM admin_users LIMIT 1")
        row = cur.fetchone()
        if row:
            eski_admin_username = row[0]

    owner_email = f"{eski_admin_username or 'admin'}@migrated.local"
    api_key = secrets.token_hex(24)
    simdi = datetime.utcnow().isoformat()
    uzak_gelecek = (datetime.utcnow() + timedelta(days=36500)).isoformat()

    # Mevcut kurulumunuz "pro" planla ve aktif durumla taşınır; dilerseniz
    # panelden/veritabanından sonra değiştirebilirsiniz.
    cur.execute("""
        INSERT INTO organizations
        (id, name, slug, brand_name, owner_email, created_at, plan, subscription_status, trial_ends_at, api_key)
        VALUES (1, 'Sefine IT', 'sefine-it', 'Sefine IT', ?, ?, 'pro', 'active', ?, ?)
    """, (owner_email, simdi, uzak_gelecek, api_key))

    for tablo in ["categories", "sources", "news_items", "subscribers", "newsletter_logs", "admin_users"]:
        if tablo_var_mi(cur, tablo) and not sutun_var_mi(cur, tablo, "organization_id"):
            cur.execute(f"ALTER TABLE {tablo} ADD COLUMN organization_id INTEGER")
            cur.execute(f"UPDATE {tablo} SET organization_id = 1")
            print(f"  {tablo}.organization_id eklendi ve mevcut kayıtlar organizasyon #1'e bağlandı")

    if sutun_var_mi(cur, "admin_users", "username") and not sutun_var_mi(cur, "admin_users", "email"):
        cur.execute("ALTER TABLE admin_users ADD COLUMN email VARCHAR(255)")
        cur.execute("UPDATE admin_users SET email = username || '@migrated.local'")
        print("  admin_users.email eklendi (username'den türetildi)")

    if not sutun_var_mi(cur, "admin_users", "email_verified"):
        cur.execute("ALTER TABLE admin_users ADD COLUMN email_verified BOOLEAN DEFAULT 1 NOT NULL")
        cur.execute("ALTER TABLE admin_users ADD COLUMN email_verification_token VARCHAR(64)")
        print("  admin_users.email_verified eklendi (mevcut hesap doğrulanmış kabul edildi)")

    if tablo_var_mi(cur, "newsletter_schedule") and not sutun_var_mi(cur, "newsletter_schedule", "organization_id"):
        cur.execute("ALTER TABLE newsletter_schedule ADD COLUMN organization_id INTEGER")
        cur.execute("UPDATE newsletter_schedule SET organization_id = 1")
        print("  newsletter_schedule.organization_id eklendi ve organizasyon #1'e bağlandı")

    conn.commit()
    conn.close()

    print()
    print("Migrasyon tamamlandı.")
    print(f"Giriş e-postanız: {owner_email}  (şifreniz DEĞİŞMEDİ, aynı admin şifrenizle giriş yapın)")
    print("Bu placeholder e-postayı gerçek e-postanızla değiştirmek isterseniz:")
    print("  python set_admin_email.py yenieposta@sirketiniz.com")
    print()
    print("Şimdi uygulamayı normal şekilde başlatabilirsiniz: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
