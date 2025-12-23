"""Instagram posting service - 2-step posting process"""

import httpx
import asyncio
from typing import Dict
from app.core.config import settings


class InstagramPostingService:
    """Service for posting content to Instagram Business accounts"""
    
    @staticmethod
    async def post_image(
        instagram_account_id: str,
        page_access_token: str,
        image_url: str,
        caption: str
    ) -> Dict[str, str]:
        """
        Post an image to Instagram (2-step process).
        
        Args:
            instagram_account_id: Instagram Business account ID
            page_access_token: Facebook Page's access token
            image_url: URL of the image to post
            caption: Post caption
            
        Returns:
            Dict with post_id and platform_url
        """
        # Step 1: Create media container
        creation_id = await InstagramPostingService._create_media_container(
            instagram_account_id,
            page_access_token,
            image_url,
            caption
        )
        
        # Step 2: Wait for Instagram to process the image, then publish
        post_id = await InstagramPostingService._publish_media_container(
            instagram_account_id,
            page_access_token,
            creation_id,
            max_retries=10,
            retry_delay=3
        )
        
        return {
            "post_id": post_id,
            "platform_url": f"https://instagram.com/p/{post_id}"
        }
    
    @staticmethod
    async def _create_media_container(
        instagram_account_id: str,
        page_access_token: str,
        image_url: str,
        caption: str
    ) -> str:
        """
        Step 1: Create Instagram media container.
        
        Returns:
            creation_id for the media container
        """
        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{instagram_account_id}/media"
        data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": page_access_token
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            result = response.json()
            
            return result["id"]
    
    @staticmethod
    async def _publish_media_container(
        instagram_account_id: str,
        page_access_token: str,
        creation_id: str,
        max_retries: int = 10,
        retry_delay: int = 3
    ) -> str:
        """
        Step 2: Publish the media container.
        Retries if Instagram is still processing the image.
        
        Returns:
            Published post ID
        """
        url = f"https://graph.facebook.com/{settings.FACEBOOK_API_VERSION}/{instagram_account_id}/media_publish"
        data = {
            "creation_id": creation_id,
            "access_token": page_access_token
        }
        
        # Initial wait for Instagram to start processing
        await asyncio.sleep(5)
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, data=data)
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result["id"]
                    elif response.status_code == 400:
                        # Check if it's a "still processing" error
                        error_data = response.json()
                        error_message = error_data.get("error", {}).get("message", "")
                        
                        if "Media is still being processed" in error_message or "not ready" in error_message.lower():
                            # Wait and retry
                            wait_time = retry_delay * (attempt + 1)  # Exponential backoff
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Different error, raise it
                            response.raise_for_status()
                    else:
                        response.raise_for_status()
                        
            except httpx.HTTPStatusError as e:
                if attempt == max_retries - 1:
                    # Last attempt, raise the error
                    raise Exception(f"Failed to publish Instagram post after {max_retries} attempts: {str(e)}")
                # Wait and retry
                await asyncio.sleep(retry_delay * (attempt + 1))
        
        raise Exception(f"Instagram post timed out after {max_retries} attempts. The post may still publish later.")
