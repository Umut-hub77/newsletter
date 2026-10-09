"""
Plan tanımları, limitleri ve hesap türüne göre ayrılmış özellikler.

Her plan+süre kombinasyonu için fiyat burada TAM OLARAK yazmalısınız.
"""

PLAN_LIMITS = {
    "free": {
        "label": "Ücretsiz Deneme",
        "description": "Hızlı başlamanız için sınırlı temel gönderim özellikleri.",
        "prices": {},
        "account_types": {
            "company": {
                "max_subscribers": 5,
                "max_team_members": 1,
                "custom_schedule_allowed": False,
                "team_management_allowed": False,
                "max_categories": 3,
                "location_insights": False,
                "custom_branding": False,
                "advanced_reporting": False,
                "priority_support": False,
                "ai_subject_suggestions": False,
                "scheduled_reports": False,
                "subscriber_segmentation": False,
                "send_time_insights": False,
                "behavior_scores": False,
                "features": [
                    "3 kategoriye kadar otomatik gönderim",
                    "Basit abone yönetimi",
                    "Deneme süresi boyunca ücretsiz kullanım",
                ],
            },
            "individual": {
                "max_subscribers": 1,
                "max_team_members": 0,
                "custom_schedule_allowed": False,
                "team_management_allowed": False,
                "max_categories": 5,
                "location_insights": False,
                "custom_branding": False,
                "advanced_reporting": False,
                "priority_support": False,
                "ai_subject_suggestions": False,
                "scheduled_reports": False,
                "subscriber_segmentation": False,
                "send_time_insights": False,
                "behavior_scores": False,
                "features": [
                    "Kişisel bülteninizi başlatın",
                    "5 kategoriye kadar seçim",
                    "Deneme süresi boyunca ücretsiz kullanım",
                ],
            },
        },
    },
    "starter": {
        "label": "Starter",
        "description": "Küçük ekipler ve kişisel kullanıcılar için güçlü temel paket.",
        "prices": {
            "30": 49.99,
            "90": 139.99,
            "180": 254.99,
            "365": 479.99,
        },
        "account_types": {
            "company": {
                "max_subscribers": 25,
                "max_team_members": 3,
                "custom_schedule_allowed": True,
                "team_management_allowed": True,
                "max_categories": 12,
                "location_insights": True,
                "custom_branding": True,
                "advanced_reporting": False,
                "priority_support": False,
                "ai_subject_suggestions": True,
                "scheduled_reports": False,
                "subscriber_segmentation": True,
                "send_time_insights": True,
                "behavior_scores": False,
                "features": [
                    "3 ekip üyesine kadar yönetim",
                    "Kişisel gönderim takvimi",
                    "Yerel haber önerileri",
                    "Abone segmentasyonu",
                    "En uygun gönderim zamanı önerileri",
                ],
            },
            "individual": {
                "max_subscribers": 1,
                "max_team_members": 0,
                "custom_schedule_allowed": True,
                "team_management_allowed": False,
                "max_categories": 15,
                "location_insights": True,
                "custom_branding": False,
                "advanced_reporting": False,
                "priority_support": False,
                "ai_subject_suggestions": True,
                "scheduled_reports": False,
                "subscriber_segmentation": True,
                "send_time_insights": True,
                "behavior_scores": False,
                "features": [
                    "Kişisel gönderim takvimi",
                    "Yerel içerik vurgusu",
                    "Akıllı kategori önerileri",
                    "Hızlı kişisel raporlar",
                    "En uygun gönderim zamanı önerileri",
                ],
            },
        },
    },
    "pro": {
        "label": "Pro",
        "description": "Tam e-posta pazarlama kontrolü, gelişmiş raporlar ve premium destek.",
        "prices": {
            "30": 249.99,
            "90": 699.99,
            "180": 1274.99,
            "365": 2399.99,
        },
        "account_types": {
            "company": {
                "max_subscribers": 1000,
                "max_team_members": 10,
                "custom_schedule_allowed": True,
                "team_management_allowed": True,
                "max_categories": 50,
                "location_insights": True,
                "custom_branding": True,
                "advanced_reporting": True,
                "priority_support": True,
                "ai_subject_suggestions": True,
                "scheduled_reports": True,
                "subscriber_segmentation": True,
                "send_time_insights": True,
                "behavior_scores": True,
                "features": [
                    "Gelişmiş ekip yönetimi",
                    "Detaylı performans raporlar",
                    "Öncelikli destek",
                    "Hedefli abone segmentleri",
                    "Abone davranış puanları",
                ],
            },
            "individual": {
                "max_subscribers": 1,
                "max_team_members": 0,
                "custom_schedule_allowed": True,
                "team_management_allowed": False,
                "max_categories": 30,
                "location_insights": True,
                "custom_branding": True,
                "advanced_reporting": True,
                "priority_support": True,
                "ai_subject_suggestions": True,
                "scheduled_reports": True,
                "subscriber_segmentation": True,
                "send_time_insights": True,
                "behavior_scores": True,
                "features": [
                    "Kişisel marka teması",
                    "Gelişmiş günlük ve aylık raporlar",
                    "Öncelikli destek",
                    "Profesyonel gönderim araçları",
                    "Abone davranış puanları",
                ],
            },
        },
    },
}

# Süre seçeneklerinin sadece etiketi ve gün karşılığı burada; fiyat DEĞİŞ
# (fiyatlar yukarida plan başına ayrı ayrı tanımlı).
DURATIONS = {
    "30": {"days": 30, "label": "Aylık"},
    "90": {"days": 90, "label": "3 Aylık"},
    "180": {"days": 180, "label": "6 Aylık"},
    "365": {"days": 365, "label": "Yıllık"},
}


def get_plan(plan_key: str, account_type: str = "company") -> dict:
    plan = PLAN_LIMITS.get(plan_key, PLAN_LIMITS["free"])
    account_type = account_type if account_type in ("company", "individual") else "company"
    account_settings = plan.get("account_types", {}).get(account_type, {})
    merged = {k: v for k, v in plan.items() if k != "account_types"}
    merged.update(account_settings)
    merged["account_type"] = account_type
    return merged


def get_duration(duration_key: str) -> dict:
    return DURATIONS.get(duration_key, DURATIONS["30"])


def get_price(plan_key: str, duration_key: str) -> float:
    plan = PLAN_LIMITS.get(plan_key, PLAN_LIMITS["free"])
    return plan.get("prices", {}).get(duration_key, 0.0)
