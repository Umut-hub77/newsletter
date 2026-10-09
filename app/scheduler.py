import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.collector import collect_all
from app.config import settings
from app.database import SessionLocal
from app.models import NewsletterSchedule, Organization, Subscriber
from app.newsletter import send_newsletter
from app.transactional_mail import send_simple_email

logger = logging.getLogger("scheduler")
scheduler = BackgroundScheduler(timezone=settings.APP_TIMEZONE)


def job_global_collect():
    """
    PLATFORM GENELİ toplama işi (tek, paylaşımlı kaynak havuzu için).
    Organizasyon başına değil, sabit bir periyotta (COLLECT_INTERVAL_MINUTES)
    bir kez çalışır; tüm organizasyonların bültenleri bu ortak havuzdan beslenir.
    """
    db = SessionLocal()
    try:
        sonuc = collect_all(db)
        logger.info("Platform geneli toplama tamamlandı: %s", sonuc)
    finally:
        db.close()


def job_send_newsletter(organization_id: int):
    """Bir organizasyonun genel zamanlama işi: mevcut havuzdan, genel zamanlamaya tabi abonelere gönder."""
    db = SessionLocal()
    try:
        abone_idler = [
            s.id for s in db.query(Subscriber).filter(
                Subscriber.organization_id == organization_id,
                Subscriber.active.is_(True),
                Subscriber.use_custom_schedule.is_(False),
            ).all()
        ]
        if abone_idler:
            send_newsletter(db, organization_id, subscriber_ids=abone_idler)
    finally:
        db.close()


def job_send_for_subscriber(subscriber_id: int):
    """Kişisel zamanlaması olan tek bir abone için: mevcut havuzdan sadece ona gönder."""
    db = SessionLocal()
    try:
        abone = db.get(Subscriber, subscriber_id)
        if not abone:
            return
        send_newsletter(db, abone.organization_id, subscriber_ids=[subscriber_id])
    finally:
        db.close()


def reschedule_newsletter_job(schedule: NewsletterSchedule):
    job_id = f"newsletter_job_{schedule.organization_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not schedule.enabled:
        logger.info("Org #%s: genel zamanlama devre dışı", schedule.organization_id)
        return

    gunler = schedule.days_of_week or "mon,tue,wed,thu,fri,sat,sun"
    scheduler.add_job(
        job_send_newsletter,
        trigger=CronTrigger(day_of_week=gunler, hour=schedule.hour, minute=schedule.minute),
        id=job_id,
        replace_existing=True,
        kwargs={"organization_id": schedule.organization_id},
    )
    logger.info(
        "Org #%s genel zamanlama güncellendi: günler=%s saat=%02d:%02d",
        schedule.organization_id, gunler, schedule.hour, schedule.minute,
    )


def reschedule_subscriber_job(subscriber: Subscriber):
    job_id = f"subscriber_{subscriber.id}_job"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not subscriber.use_custom_schedule or not subscriber.active:
        return

    gunler = subscriber.custom_days_of_week or "mon,tue,wed,thu,fri,sat,sun"
    saat = subscriber.custom_hour if subscriber.custom_hour is not None else 8
    dakika = subscriber.custom_minute if subscriber.custom_minute is not None else 0

    scheduler.add_job(
        job_send_for_subscriber,
        trigger=CronTrigger(day_of_week=gunler, hour=saat, minute=dakika),
        id=job_id,
        replace_existing=True,
        kwargs={"subscriber_id": subscriber.id},
    )


def remove_org_job(organization_id: int):
    job_id = f"newsletter_job_{organization_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def remove_subscriber_job(subscriber_id: int):
    job_id = f"subscriber_{subscriber_id}_job"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def check_subscriptions():
    """
    Günde bir kez çalışır (Shopier'de otomatik tekrarlayan ödeme olmadığı
    için manuel takip gerekir):
      - Süresi dolan aktif abonelikleri Free plana düşürür
      - Süresi yaklaşan (RENEWAL_REMINDER_DAYS_BEFORE gün kala) abonelere
        bir kez hatırlatma maili gönderir
    """
    db = SessionLocal()
    try:
        simdi = datetime.utcnow()
        for org in db.query(Organization).filter(Organization.plan != "free").all():
            if not org.subscription_expires_at:
                continue

            if org.subscription_expires_at <= simdi:
                logger.info("Org #%s aboneliği sona erdi, Free plana düşürülüyor", org.id)
                org.plan = "free"
                org.subscription_status = "expired"
                db.commit()
                send_simple_email(
                    org.owner_email,
                    f"{org.name} - Aboneliğiniz sona erdi",
                    f"Merhaba,\n\n{org.name} hesabınızın aboneliği sona erdi ve plan otomatik "
                    f"olarak Ücretsiz'e düşürüldü.\n\nYenilemek için: {settings.APP_BASE_URL}/panel/billing",
                )
                continue

            hatirlatma_esigi = org.subscription_expires_at - timedelta(days=settings.RENEWAL_REMINDER_DAYS_BEFORE)
            if simdi >= hatirlatma_esigi and not org.renewal_reminder_sent_at:
                send_simple_email(
                    org.owner_email,
                    f"{org.name} - Aboneliğiniz yakında sona eriyor",
                    f"Merhaba,\n\n{org.name} hesabınızın aboneliği "
                    f"{org.subscription_expires_at.strftime('%d.%m.%Y')} tarihinde sona erecek.\n\n"
                    f"Kesintisiz devam etmesi için: {settings.APP_BASE_URL}/panel/billing",
                )
                org.renewal_reminder_sent_at = simdi
                db.commit()
    finally:
        db.close()


def get_or_create_schedule(db, organization_id: int) -> NewsletterSchedule:
    schedule = db.query(NewsletterSchedule).filter(
        NewsletterSchedule.organization_id == organization_id
    ).first()
    if not schedule:
        schedule = NewsletterSchedule(
            organization_id=organization_id,
            days_of_week="mon,tue,wed,thu,fri,sat,sun",
            hour=8,
            minute=0,
            enabled=True,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
    return schedule


def start_scheduler():
    """Tüm organizasyonlar için mevcut zamanlamaları yükler ve işleri kurar."""
    db = SessionLocal()
    ozel_sayisi = 0
    try:
        for org in db.query(Organization).all():
            schedule = get_or_create_schedule(db, org.id)
            reschedule_newsletter_job(schedule)

        ozel_zamanlamali_aboneler = db.query(Subscriber).filter(
            Subscriber.use_custom_schedule.is_(True)
        ).all()
        ozel_sayisi = len(ozel_zamanlamali_aboneler)
        for abone in ozel_zamanlamali_aboneler:
            reschedule_subscriber_job(abone)
    finally:
        db.close()

    scheduler.add_job(
        check_subscriptions,
        trigger=CronTrigger(hour=6, minute=0),
        id="check_subscriptions_job",
        replace_existing=True,
    )

    scheduler.add_job(
        job_global_collect,
        trigger=IntervalTrigger(minutes=settings.COLLECT_INTERVAL_MINUTES),
        id="global_collect_job",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Zamanlayıcı başladı: platform geneli toplama her %d dakikada, "
        "%d kişisel abone zamanlaması aktif",
        settings.COLLECT_INTERVAL_MINUTES, ozel_sayisi,
    )