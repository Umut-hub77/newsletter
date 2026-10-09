from fastapi.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["brand_name"] = settings.APP_BRAND_NAME
templates.env.globals["owner_email"] = settings.PLATFORM_OWNER_EMAIL
