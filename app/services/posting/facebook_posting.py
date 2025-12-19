"""Facebook posting service"""

import httpx
from typing import Dict, Optional
from app.core.config import settings


class FacebookPostingService:
    """Service for posting content to Facebook Pages"""
    
    @staticmethod
    async def post_to_page(
        page_id: str,
        page_access_token: str,
        message: str,
        image_url: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Post content to a Facebook Page.
        
        Args:
            page_id: Facebook Page ID
            page_access_token: Page's access token
            message: Post message/content
            image_url: Optional image URL
            
        Returns:
            Dict with post_id and platform_url
        """
        if image_url:
            # Post with photo
            url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{page_id}/photos"
            data = {
                "url": image_url,
                "caption": message,
                "access_token": page_access_token
            }
        else:
            # Post text only
            url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{page_id}/feed"
            data = {
                "message": message,
                "access_token": page_access_token
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            
            # If error, try to get Facebook's error message
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "Unknown error")
                    error_code = error_data.get("error", {}).get("code", "Unknown")
                    error_type = error_data.get("error", {}).get("type", "Unknown")
                    
                    raise Exception(
                        f"Facebook API Error (Code {error_code}): {error_message} "
                        f"[Type: {error_type}]"
                    )
                except Exception as e:
                    if "Facebook API Error" in str(e):
                        raise
                    # If we can't parse the error, raise the original
                    response.raise_for_status()
            
            result = response.json()
            
            post_id = result.get("id") or result.get("post_id")
            
            return {
                "post_id": post_id,
                "platform_url": f"https://facebook.com/{post_id}"
            }
