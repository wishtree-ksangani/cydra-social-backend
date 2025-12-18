"""
OAuth Provider URL Constants

This file contains all OAuth provider URLs in one place for easy configuration.
If a provider changes their API endpoints, you only need to update them here.
"""

from app.core.config import settings


class FacebookOAuthURLs:
    """Facebook/Instagram OAuth endpoint URLs"""
    
    @staticmethod
    def get_authorization_url() -> str:
        return f"https://www.facebook.com/{settings.FACEBOOK_API_VERSION}/dialog/oauth"
    
    @staticmethod
    def get_token_url() -> str:
        return f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/oauth/access_token"
    
    @staticmethod
    def get_user_info_url() -> str:
        return "https://graph.facebook.com/me"


class TwitterOAuthURLs:
    """Twitter/X OAuth endpoint URLs"""
    
    @staticmethod
    def get_authorization_url() -> str:
        return "https://twitter.com/i/oauth2/authorize"
    
    @staticmethod
    def get_token_url() -> str:
        return f"https://api.twitter.com/{settings.TWITTER_API_VERSION}/oauth2/token"
    
    @staticmethod
    def get_user_info_url() -> str:
        return f"https://api.twitter.com/{settings.TWITTER_API_VERSION}/users/me"


class LinkedInOAuthURLs:
    """LinkedIn OAuth endpoint URLs"""
    
    @staticmethod
    def get_authorization_url() -> str:
        return f"https://www.linkedin.com/oauth/{settings.LINKEDIN_API_VERSION}/authorization"
    
    @staticmethod
    def get_token_url() -> str:
        return f"https://www.linkedin.com/oauth/{settings.LINKEDIN_API_VERSION}/accessToken"
    
    @staticmethod
    def get_user_info_url() -> str:
        return f"https://api.linkedin.com/{settings.LINKEDIN_API_VERSION}/me"
