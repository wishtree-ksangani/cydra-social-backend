"""Twitter/X posting service"""

import httpx
from typing import Dict, Optional, List
from app.core.config import settings


class TwitterPostingService:
    """Service for posting content to Twitter/X"""
    
    @staticmethod
    async def upload_media(image_url: str, access_token: str) -> str:
        """
        Upload an image to Twitter using v2 3-step chunked upload.
        
        Steps:
        1. Initialize - Get media_id
        2. Append - Upload image data
        3. Finalize - Complete upload
        
        Args:
            image_url: URL of the image to upload
            access_token: Twitter access token
            
        Returns:
            media_id string
        """
        # Download the image first
        async with httpx.AsyncClient() as client:
            img_response = await client.get(image_url, timeout=30.0)
            img_response.raise_for_status()
            image_data = img_response.content
            
            # Detect content type and media category
            content_type = img_response.headers.get("content-type", "image/jpeg")
            media_type = "image/jpeg" if "jpeg" in content_type or "jpg" in content_type else "image/png"
            total_bytes = len(image_data)
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 1: Initialize upload
        init_url = "https://api.twitter.com/2/media/upload/initialize"
        init_data = {
            "media_type": media_type,
            "total_bytes": total_bytes,
            "media_category": "tweet_image"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(init_url, headers=headers, json=init_data)
            
            if response.status_code not in [200, 201]:
                # Log full error for debugging
                print(f"Twitter Media Init Failed:")
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")
                
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", error_data.get("title", str(error_data)))
                    raise Exception(f"Twitter Media Init Error: {error_message}")
                except Exception as e:
                    if "Twitter Media" in str(e):
                        raise
                    raise Exception(f"Twitter Media Init Error: {response.status_code} - {response.text}")
            
            result = response.json()
            print(f"Initialize response: {result}")  # Debug
            
            # Extract media_id from response
            # Twitter v2 returns: {"data": {"id": "...", "media_key": "..."}}
            if "data" in result:
                media_id = result["data"].get("id") or result["data"].get("media_id") or result["data"].get("media_id_string")
            else:
                media_id = result.get("id") or result.get("media_id_string") or result.get("media_id")
            
            if not media_id:
                raise Exception(f"No media_id in response: {result}")
            
            print(f"Got media_id: {media_id}")  # Debug
        
        # Step 2: Append media data
        # Note: segment_index is required in the request body, starting from 0
        append_url = f"https://api.twitter.com/2/media/upload/{media_id}/append"
        
        async with httpx.AsyncClient() as client:
            # Send as multipart form data with segment_index
            data = {"segment_index": "0"}
            files = {"media": ("image.jpg", image_data, media_type)}
            
            response = await client.post(append_url, headers=headers, data=data, files=files)
            
            if response.status_code not in [200, 201, 204]:
                raise Exception(f"Twitter Media Append Error: {response.status_code} - {response.text}")

        
        # Step 3: Finalize upload
        finalize_url = f"https://api.twitter.com/2/media/upload/{media_id}/finalize"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(finalize_url, headers=headers)
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Twitter Media Finalize Error: {response.status_code} - {response.text}")
        
        return str(media_id)
    
    @staticmethod
    async def post_tweet(
        access_token: str,
        text: str,
        image_urls: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Post a tweet to Twitter/X.
        
        Args:
            access_token: Twitter access token
            text: Tweet text (max 280 characters)
            image_urls: Optional list of image URLs (max 4)
            
        Returns:
            Dict with tweet_id and platform_url
        """
        # Validate text length
        if len(text) > 280:
            raise Exception("Tweet text exceeds 280 character limit")
        
        # Upload media if provided
        media_ids = []
        if image_urls:
            if len(image_urls) > 4:
                raise Exception("Twitter allows maximum 4 images per tweet")
            
            for image_url in image_urls:
                media_id = await TwitterPostingService.upload_media(image_url, access_token)
                media_ids.append(media_id)
        
        # Create tweet
        url = f"https://api.twitter.com/2/tweets"
        
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            # Handle errors
            if response.status_code != 201:
                try:
                    error_data = response.json()
                    error_message = error_data.get("detail", error_data.get("title", "Unknown error"))
                    error_type = error_data.get("type", "Unknown")
                    
                    raise Exception(
                        f"Twitter API Error: {error_message} [Type: {error_type}]"
                    )
                except Exception as e:
                    if "Twitter API Error" in str(e):
                        raise
                    response.raise_for_status()
            
            result = response.json()
            tweet_id = result["data"]["id"]
            
            return {
                "post_id": tweet_id,
                "platform_url": f"https://twitter.com/i/web/status/{tweet_id}"
            }
