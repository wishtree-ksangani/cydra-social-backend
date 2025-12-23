from pydantic_settings import BaseSettings
import json

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: str = "*"  # Can be "*", comma-separated, or JSON array
    
    # OAuth - Facebook/Instagram (Instagram Graph API via Facebook)
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    FACEBOOK_API_VERSION: str = "v24.0"
    FACEBOOK_SCOPES: str = "public_profile,pages_show_list,business_management"
    
    # OAuth - Twitter/X
    TWITTER_CLIENT_ID: str = ""
    TWITTER_CLIENT_SECRET: str = ""
    TWITTER_API_VERSION: str = "2"
    TWITTER_SCOPES: str = "tweet.read tweet.write users.read offline.access"
    
    # OAuth - LinkedIn
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_API_VERSION: str = "v2"
    LINKEDIN_SCOPES: str = "openid profile email w_member_social"
    
    # OAuth Configuration
    OAUTH_REDIRECT_URI: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"  # For OAuth callback redirects
    
    # Token Encryption
    ENCRYPTION_KEY: str = ""  # Generate with: Fernet.generate_key().decode()
    
    # Scheduler Configuration
    SCHEDULER_INTERVAL_SECONDS: int = 30  # How often to check for scheduled posts
    
    # AI Content Generation (n8n webhooks)
    N8N_HOST_URL: str = ""  # n8n host URL (e.g., https://your-n8n-instance.com)
    N8N_CONTENT_WEBHOOK_PATH: str = ""  # Webhook path for content generation (e.g., /webhook/generate-content)
    N8N_IMAGE_WEBHOOK_PATH: str = ""  # Webhook path for image generation (e.g., /webhook/generate-image)

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
    
    @property
    def facebook_scopes_list(self) -> list[str]:
        """Convert Facebook scopes to list"""
        return [scope.strip() for scope in self.FACEBOOK_SCOPES.split(",")]
    
    @property
    def twitter_scopes_list(self) -> list[str]:
        """Convert Twitter scopes to list"""
        return [scope.strip() for scope in self.TWITTER_SCOPES.split(" ")]
    
    @property
    def linkedin_scopes_list(self) -> list[str]:
        """Convert LinkedIn scopes to list"""
        return [scope.strip() for scope in self.LINKEDIN_SCOPES.split(" ")]

settings = Settings()
