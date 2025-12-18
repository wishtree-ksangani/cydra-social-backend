from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.core.encryption import encrypt_token, decrypt_token
from app.models.user import User
from app.models.social_account import SocialAccount
from app.schemas.social_account import OAuthInitiateResponse
from app.services.oauth.factory import get_oauth_provider
from app.services.oauth.state_manager import oauth_state_manager

router = APIRouter()


@router.get("/{platform}/authorize", response_model=OAuthInitiateResponse)
async def initiate_oauth(
    platform: str,
    current_user: User = Depends(get_current_user)
):
    """
    Initiate OAuth flow for a social media platform.
    Returns authorization URL for user to visit.
    """
    try:
        provider = get_oauth_provider(platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # For Twitter, get the code_verifier to store in state
    code_verifier = None
    if platform.lower() == "twitter":
        code_verifier = provider.code_verifier
    
    # Create state token for CSRF protection (with code_verifier for Twitter)
    state = oauth_state_manager.create_state(current_user.id, platform, code_verifier)
    
    # Get authorization URL
    auth_url = provider.get_authorization_url(state)
    
    return OAuthInitiateResponse(
        authorization_url=auth_url,
        state=state
    )


@router.get("/callback/{platform}")
async def oauth_callback(
    platform: str,
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle OAuth callback from social media platform.
    Exchanges code for token and saves to database.
    """
    import urllib.parse
    
    # Check if OAuth provider returned an error
    if error:
        error_msg = error_description or error
        
        # Map common OAuth errors to user-friendly messages
        if error == "access_denied" or error == "user_cancelled_authorize":
            error_msg = f"You cancelled the {platform} authorization. Please try again if you want to connect your account."
            error_type = "user_cancelled"
        elif error == "unauthorized_scope_error":
            error_msg = f"Some requested permissions are not available for your {platform} app. Please check your app configuration."
            error_type = "scope_error"
        else:
            error_msg = f"{platform} authorization error: {error_msg}"
            error_type = "oauth_error"
        
        encoded_message = urllib.parse.quote(error_msg)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/error?platform={platform}&error_type={error_type}&message={encoded_message}"
        )
    
    # Validate required parameters
    if not code or not state:
        encoded_message = urllib.parse.quote("Missing authorization code or state parameter")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/error?platform={platform}&error_type=invalid_callback&message={encoded_message}"
        )
    
    # Validate state and get user_id (and code_verifier for Twitter)
    result = oauth_state_manager.validate_and_consume_state(state, platform)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter"
        )
    
    user_id, code_verifier = result
    
    try:
        provider = get_oauth_provider(platform)
        
        # For Twitter, set the code_verifier from state
        if platform.lower() == "twitter" and code_verifier:
            provider.code_verifier = code_verifier
        
        # Exchange code for access token
        token_data = await provider.exchange_code_for_token(code)
        
        # Get user info from platform
        user_info = await provider.get_user_info(token_data["access_token"])
        
        # Encrypt tokens
        encrypted_access_token = encrypt_token(token_data["access_token"])
        encrypted_refresh_token = None
        if token_data.get("refresh_token"):
            encrypted_refresh_token = encrypt_token(token_data["refresh_token"])
        
        # Calculate token expiration
        token_expires_at = None
        if token_data.get("expires_in"):
            token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        # Check if account already exists
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform
            )
        )
        existing_account = result.scalars().first()
        
        if existing_account:
            # Update existing account
            existing_account.platform_user_id = user_info["user_id"]
            existing_account.platform_username = user_info["username"]
            existing_account.access_token = encrypted_access_token
            existing_account.refresh_token = encrypted_refresh_token
            existing_account.token_expires_at = token_expires_at
            existing_account.is_active = True
            existing_account.updated_at = datetime.utcnow()
        else:
            # Create new account
            new_account = SocialAccount(
                user_id=user_id,
                platform=platform,
                platform_user_id=user_info["user_id"],
                platform_username=user_info["username"],
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expires_at=token_expires_at,
                is_active=True
            )
            db.add(new_account)
        
        await db.commit()
        
        # Redirect to frontend success page
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/oauth/success?platform={platform}")
        
    except Exception as e:
        # Log the error for debugging
        import traceback
        import urllib.parse
        
        print(f"OAuth callback error for {platform}:")
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        
        # Categorize error and create user-friendly message
        error_message = str(e)
        error_type = "unknown"
        
        # Check for specific error types
        if "HTTPStatusError" in str(type(e)):
            # HTTP errors from OAuth provider
            if "400" in str(e):
                error_type = "invalid_request"
                error_message = f"Invalid OAuth request to {platform}. Please try again."
            elif "401" in str(e):
                error_type = "unauthorized"
                error_message = f"Authorization failed for {platform}. Please check your credentials."
            elif "403" in str(e):
                error_type = "forbidden"
                error_message = f"Access forbidden by {platform}. You may need to enable required permissions in your {platform} app."
            elif "404" in str(e):
                error_type = "not_found"
                error_message = f"{platform} API endpoint not found. The API may have changed."
            else:
                error_type = "api_error"
                error_message = f"{platform} API error: {str(e)}"
        elif "ENCRYPTION_KEY" in str(e):
            error_type = "config_error"
            error_message = "Server configuration error. Please contact support."
        elif "database" in str(e).lower() or "sql" in str(e).lower():
            error_type = "database_error"
            error_message = "Failed to save account. Please try again."
        else:
            error_type = "unknown"
            error_message = f"Failed to connect {platform} account: {str(e)}"
        
        # URL encode the error message
        encoded_message = urllib.parse.quote(error_message)
        
        # Redirect to frontend error page with detailed error info
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/error?platform={platform}&error_type={error_type}&message={encoded_message}"
        )


@router.post("/{platform}/refresh")
async def refresh_token(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token for a social media platform.
    """
    # Get social account
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == platform,
            SocialAccount.is_active == True
        )
    )
    account = result.scalars().first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    if not account.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")
    
    try:
        provider = get_oauth_provider(platform)
        
        # Decrypt refresh token
        refresh_token = decrypt_token(account.refresh_token)
        
        # Refresh access token
        token_data = await provider.refresh_access_token(refresh_token)
        
        # Encrypt new tokens
        encrypted_access_token = encrypt_token(token_data["access_token"])
        encrypted_refresh_token = None
        if token_data.get("refresh_token"):
            encrypted_refresh_token = encrypt_token(token_data["refresh_token"])
        
        # Calculate token expiration
        token_expires_at = None
        if token_data.get("expires_in"):
            token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        # Update account
        account.access_token = encrypted_access_token
        if encrypted_refresh_token:
            account.refresh_token = encrypted_refresh_token
        account.token_expires_at = token_expires_at
        account.updated_at = datetime.utcnow()
        
        await db.commit()
        
        return {"success": True, "message": "Token refreshed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")


@router.delete("/{platform}/disconnect")
async def disconnect_account(
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect a social media account.
    """
    # Get social account
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == platform
        )
    )
    account = result.scalars().first()
    
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    
    # Set inactive instead of deleting (preserve history)
    account.is_active = False
    account.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {"success": True, "message": f"{platform.capitalize()} account disconnected"}
