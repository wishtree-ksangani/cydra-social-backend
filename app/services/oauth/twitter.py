import httpx
import secrets
import hashlib
import base64
from urllib.parse import urlencode
from typing import Dict
from app.services.oauth.base import BaseOAuthProvider
from app.core.config import settings
from app.core.oauth_constants import TwitterOAuthURLs


class TwitterOAuthProvider(BaseOAuthProvider):
    """
    Twitter/X OAuth 2.0 provider with PKCE.
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(client_id, client_secret, redirect_uri)
        # Use configurable scopes from settings
        self.scopes = settings.twitter_scopes_list
        # Get URLs from centralized constants
        self.authorization_url = TwitterOAuthURLs.get_authorization_url()
        self.token_url = TwitterOAuthURLs.get_token_url()
        self.user_info_url = TwitterOAuthURLs.get_user_info_url()
        # Generate PKCE code verifier and challenge
        self.code_verifier = self._generate_code_verifier()
        self.code_challenge = self._generate_code_challenge(self.code_verifier)
    
    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier."""
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    
    def get_authorization_url(self, state: str) -> str:
        """Generate Twitter OAuth authorization URL with PKCE."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": f"{self.redirect_uri}/api/v1/oauth/callback/twitter",
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.authorization_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, any]:
        """Exchange authorization code for access token."""
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": f"{self.redirect_uri}/api/v1/oauth/callback/twitter",
            "code_verifier": self.code_verifier,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        # Basic auth with client credentials
        auth = (self.client_id, self.client_secret)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers=headers,
                auth=auth
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
        """Refresh an expired access token."""
        data = {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "client_id": self.client_id,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        auth = (self.client_id, self.client_secret)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers=headers,
                auth=auth
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
        """Get Twitter user profile information."""
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        
        params = {
            "user.fields": "id,name,username",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.user_info_url,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            result = response.json()
            data = result.get("data", {})
            
            return {
                "user_id": data.get("id", ""),
                "username": data.get("username", ""),
                "name": data.get("name", ""),
                "email": None,  # Twitter API v2 doesn't provide email in /users/me
            }
