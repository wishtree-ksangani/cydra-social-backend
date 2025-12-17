from pydantic_settings import BaseSettings
import json

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: str = "*"  # Can be "*", comma-separated, or JSON array

    class Config:
        env_file = ".env"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Convert CORS_ORIGINS to list. Supports: *, comma-separated, or JSON array"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        
        # Try to parse as JSON array first
        if self.CORS_ORIGINS.startswith("["):
            try:
                return json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                pass
        
        # Fall back to comma-separated
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

settings = Settings()
