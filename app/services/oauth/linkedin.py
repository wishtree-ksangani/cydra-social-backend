import httpx
from urllib.parse import urlencode
from typing import Dict
from app.services.oauth.base import BaseOAuthProvider
from app.core.config import settings
from app.core.oauth_constants import LinkedInOAuthURLs


class LinkedInOAuthProvider(BaseOAuthProvider):
    """
    LinkedIn OAuth 2.0 provider.
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(client_id, client_secret, redirect_uri)
        # Use configurable scopes from settings
        self.scopes = settings.linkedin_scopes_list
        # Get URLs from centralized constants
        self.authorization_url = LinkedInOAuthURLs.get_authorization_url()
        self.token_url = LinkedInOAuthURLs.get_token_url()
        self.user_info_url = LinkedInOAuthURLs.get_user_info_url()
    
    def get_authorization_url(self, state: str) -> str:
        """Generate LinkedIn OAuth authorization URL."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": f"{self.redirect_uri}/api/v1/oauth/callback/linkedin",
            "state": state,
            "scope": " ".join(self.scopes),
        }
        return f"{self.authorization_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, any]:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{self.redirect_uri}/api/v1/oauth/callback/linkedin",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            token_data = response.json()
            
            return {
                "access_token": token_data["access_token"],
                "token_type": token_data.get("token_type", "bearer"),
                "expires_in": token_data.get("expires_in"),
                "refresh_token": token_data.get("refresh_token"),
            }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, any]:
        """
        Refresh an expired access token.
        Note: LinkedIn refresh tokens are single-use.
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            token_data = response.json()
            
            return {
                "access_token": token_data["access_token"],
                "token_type": token_data.get("token_type", "bearer"),
                "expires_in": token_data.get("expires_in"),
                "refresh_token": token_data.get("refresh_token"),
            }
    
    async def get_user_info(self, access_token: str) -> Dict[str, any]:
        """
        Get LinkedIn user info.
        Note: Using placeholder until OpenID Connect product is fully activated.
        The account will still work for posting - username can be updated later.
        """
        import time
        
        return {
            "user_id": f"linkedin_{int(time.time())}",
            "username": "LinkedIn User",
            "name": "LinkedIn User",
            "email": None,
        }
