from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    db_host: str
    db_name: str
    db_user: str
    db_password: str
    allow_cors: str

@lru_cache
def get_settings():
    """
    Get application settings
    """
    return Settings()

# @app.get("/info")
# async def info(settings: Annotated[Settings, Depends(get_settings)]):
#     return {
#         "app_name": settings.app_name,
#         "admin_email": settings.admin_email,
#         "items_per_user": settings.items_per_user,
#     }