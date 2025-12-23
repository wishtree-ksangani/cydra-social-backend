from app.services.oauth.base import BaseOAuthProvider
from app.services.oauth.facebook import FacebookOAuthProvider
from app.services.oauth.twitter import TwitterOAuthProvider
from app.services.oauth.linkedin import LinkedInOAuthProvider
from app.core.config import settings


def get_oauth_provider(platform: str) -> BaseOAuthProvider:
    """
    Factory function to get the appropriate OAuth provider.
    
    Args:
        platform: Platform name (facebook, instagram, twitter, linkedin)
        
    Returns:
        OAuth provider instance
        
    Raises:
        ValueError: If platform is not supported
    """
    platform = platform.lower()
    
    if platform == "facebook" or platform == "instagram":
        # Instagram Business uses Facebook OAuth (Instagram Graph API)
        return FacebookOAuthProvider(
            client_id=settings.FACEBOOK_CLIENT_ID,
            client_secret=settings.FACEBOOK_CLIENT_SECRET,
            redirect_uri=settings.OAUTH_REDIRECT_URI
        )
    
    elif platform == "twitter":
        return TwitterOAuthProvider(
            client_id=settings.TWITTER_CLIENT_ID,
            client_secret=settings.TWITTER_CLIENT_SECRET,
            redirect_uri=settings.OAUTH_REDIRECT_URI
        )
    
    elif platform == "linkedin":
        return LinkedInOAuthProvider(
            client_id=settings.LINKEDIN_CLIENT_ID,
            client_secret=settings.LINKEDIN_CLIENT_SECRET,
            redirect_uri=settings.OAUTH_REDIRECT_URI
        )
    
    else:
        raise ValueError(f"Unsupported platform: {platform}")
