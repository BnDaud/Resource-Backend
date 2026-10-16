from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket: str = "product-images"
    jwt_secret: str
    encryption_keys: str
    blind_index_key: str
    jwt_expire_minutes: int = 480
    frontend_origin: str = "http://localhost:5173"  # one or more website origins, comma-separated
    site_url: str = ""  # public website address, used in the sitemap; defaults to frontend_origin
    cookie_secure: bool = False
    environment: str = "development"
    max_upload_mb: int = 5


    @property
    def allowed_origins(self) -> list[str]:
        """Origins allowed by CORS. Trailing slashes are removed: a browser origin never has one."""
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
