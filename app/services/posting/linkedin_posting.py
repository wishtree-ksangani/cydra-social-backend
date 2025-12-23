"""LinkedIn posting service"""

import httpx
from typing import Dict, Optional
from app.core.config import settings


class LinkedInPostingService:
    """Service for posting content to LinkedIn"""
    
    @staticmethod
    async def get_person_urn(access_token: str) -> str:
        """
        Get the LinkedIn person URN for the authenticated user.
        
        Args:
            access_token: LinkedIn access token
            
        Returns:
            Person URN (e.g., "urn:li:person:ABC123")
        """
        url = "https://api.linkedin.com/v2/userinfo"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract person ID from sub field
            person_id = data.get("sub")
            return f"urn:li:person:{person_id}"
    
    @staticmethod
    async def upload_image(
        image_url: str,
        access_token: str,
        person_urn: str
    ) -> str:
        """
        Upload an image to LinkedIn and get asset URN.
        
        Args:
            image_url: URL of the image to upload
            access_token: LinkedIn access token
            person_urn: LinkedIn person URN
            
        Returns:
            Asset URN string
        """
        # Step 1: Register upload
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                register_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=register_payload
            )
            response.raise_for_status()
            register_data = response.json()
            
            upload_url = register_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
            asset_urn = register_data["value"]["asset"]
        
        # Step 2: Download image
        async with httpx.AsyncClient() as client:
            img_response = await client.get(image_url, timeout=30.0)
            img_response.raise_for_status()
            image_data = img_response.content
            
            # Detect content type
            content_type = img_response.headers.get("content-type", "image/jpeg")
            if "png" in content_type.lower():
                content_type = "image/png"
            else:
                content_type = "image/jpeg"
        
        # Step 3: Upload image to LinkedIn
        async with httpx.AsyncClient() as client:
            response = await client.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": content_type
                },
                content=image_data
            )
            
            print(f"LinkedIn image upload status: {response.status_code}")
            print(f"Upload URL: {upload_url}")
            print(f"Asset URN: {asset_urn}")
            
            response.raise_for_status()
        
        return asset_urn
    
    @staticmethod
    async def create_post(
        access_token: str,
        text: str,
        image_url: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create a post on LinkedIn.
        
        Args:
            access_token: LinkedIn access token
            text: Post text (max 3000 characters)
            image_url: Optional image URL
            
        Returns:
            Dict with post_id and platform_url
        """
        # Validate text length
        if len(text) > 3000:
            raise Exception("LinkedIn post text exceeds 3000 character limit")
        
        # Get person URN
        person_urn = await LinkedInPostingService.get_person_urn(access_token)
        
        # Upload image if provided
        asset_urn = None
        if image_url:
            asset_urn = await LinkedInPostingService.upload_image(
                image_url, access_token, person_urn
            )
        
        # Create post payload
        url = "https://api.linkedin.com/v2/ugcPosts"
        
        payload = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE" if not asset_urn else "IMAGE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        # Add media if uploaded
        if asset_urn:
            print(f"Adding media to LinkedIn post: {asset_urn}")
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {
                    "status": "READY",
                    "media": asset_urn
                }
            ]
        
        print(f"LinkedIn post payload: {payload}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Restli-Protocol-Version": "2.0.0"
                },
                json=payload
            )
            
            print(f"LinkedIn post response status: {response.status_code}")
            print(f"LinkedIn post response: {response.text}")
            
            # Handle errors
            if response.status_code != 201:
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", "Unknown error")
                    error_status = error_data.get("status", "Unknown")
                    
                    raise Exception(
                        f"LinkedIn API Error ({error_status}): {error_message}"
                    )
                except Exception as e:
                    if "LinkedIn API Error" in str(e):
                        raise
                    response.raise_for_status()
            
            # Extract post ID from response header
            post_id = response.headers.get("X-RestLi-Id", "unknown")
            
            return {
                "post_id": post_id,
                "platform_url": f"https://www.linkedin.com/feed/update/{post_id}"
            }
