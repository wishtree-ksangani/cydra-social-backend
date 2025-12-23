from abc import ABC, abstractmethod
from typing import Dict


class BaseOAuthProvider(ABC):
    """
    Abstract base class for OAuth 2.0 providers.
    All social media OAuth providers must implement these methods.
    """
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """
        Generate OAuth authorization URL for user to visit.
        
        Args:
            state: CSRF protection token
            
        Returns:
            Authorization URL string
        """
        pass
    
    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> Dict[str, any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Dict containing:
                - access_token: str
                - refresh_token: str (optional)
                - expires_in: int (seconds, optional)
                - token_type: str
        """
        pass
    
    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: Refresh token from previous authorization
            
        Returns:
            Dict containing new token data (same format as exchange_code_for_token)
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, access_token: str) -> Dict[str, any]:
        """
        Get user profile information from the platform.
        
        Args:
            access_token: Valid access token
            
        Returns:
            Dict containing:
                - user_id: str (platform user ID)
                - username: str (username/handle)
                - name: str (display name, optional)
                - email: str (optional)
        """
        pass
