import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional


class OAuthStateManager:
    """
    Simple in-memory state manager for OAuth CSRF protection.
    Stores state tokens with user_id and expiration.
    
    For production, consider using Redis.
    """
    
    def __init__(self):
        self._states: Dict[str, Dict] = {}
    
    def create_state(
        self, 
        user_id: int, 
        platform: str,
        code_verifier: Optional[str] = None,
        expires_in_seconds: int = 600
    ) -> str:
        """
        Create a new state token for OAuth flow.
        
        Args:
            user_id: ID of the user initiating OAuth
            platform: Platform name (facebook, twitter, etc.)
            code_verifier: Optional PKCE code verifier for Twitter
            expires_in_seconds: Token expiration time (default 10 minutes)
            
        Returns:
            State token string
        """
        state = secrets.token_urlsafe(32)
        
        self._states[state] = {
            "user_id": user_id,
            "platform": platform,
            "code_verifier": code_verifier,  # Store PKCE verifier
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        }
        
        # Clean up expired states
        self._cleanup_expired()
        
        return state
    
    def validate_and_consume_state(self, state: str, platform: str) -> Optional[tuple[int, Optional[str]]]:
        """
        Validate state token and consume it (one-time use).
        
        Args:
            state: State token to validate
            platform: Expected platform name
            
        Returns:
            Tuple of (user_id, code_verifier) if valid, None otherwise
        """
        state_data = self._states.get(state)
        
        if not state_data:
            return None
        
        # Check expiration
        if datetime.utcnow() > state_data["expires_at"]:
            del self._states[state]
            return None
        
        # Check platform matches
        if state_data["platform"] != platform:
            return None
        
        # Get user_id and code_verifier
        user_id = state_data["user_id"]
        code_verifier = state_data.get("code_verifier")
        
        # Consume state (delete it)
        del self._states[state]
        
        return (user_id, code_verifier)
    
    def _cleanup_expired(self):
        """Remove expired state tokens."""
        now = datetime.utcnow()
        expired_states = [
            state for state, data in self._states.items()
            if now > data["expires_at"]
        ]
        for state in expired_states:
            del self._states[state]


# Global instance
oauth_state_manager = OAuthStateManager()
