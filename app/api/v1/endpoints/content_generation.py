"""Content and image generation endpoints - Calls n8n webhooks for AI-generated content"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import httpx
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Request/Response Schemas ====================

class GenerateContentRequest(BaseModel):
    """Request schema for content generation"""
    topic: str  # "Why AI agents are changing software development"
    tone: str  # "professional and insightful"
    hashtag: str  # "#AI #SoftwareDevelopment #TechTrends"
    platforms: List[str]  # ["facebook", "twitter", "linkedin"]


class PlatformContent(BaseModel):
    """Generated content for a single platform"""
    platform: str
    content: str


class GenerateContentResponse(BaseModel):
    """Response schema for content generation"""
    success: bool
    generated: Dict[str, PlatformContent]
    input: Dict


class GenerateImageRequest(BaseModel):
    """Request schema for image generation"""
    topic: str  # "Why AI agents are changing software development"
    tone: str  # "professional and insightful"
    hashtag: str  # "#AI #SoftwareDevelopment #TechTrends"
    platforms: List[str]  # ["facebook", "twitter", "linkedin"]


class PlatformImage(BaseModel):
    """Generated image for a single platform"""
    platform: str
    image_url: str
    dimensions: Dict  # {"width": 1200, "height": 630}


class GenerateImageResponse(BaseModel):
    """Response schema for image generation"""
    success: bool
    generated: Dict[str, PlatformImage]
    input: Dict


# ==================== Helper Functions ====================

def get_n8n_url(webhook_path: str) -> str:
    """Build full n8n webhook URL from host and path"""
    if not settings.N8N_HOST_URL:
        raise HTTPException(
            status_code=500,
            detail="n8n is not configured. Set N8N_HOST_URL in environment."
        )
    
    host = settings.N8N_HOST_URL.rstrip("/")
    path = webhook_path.lstrip("/") if webhook_path else ""
    
    return f"{host}/{path}"


# ==================== Generate Content Endpoint ====================

@router.post("/generate/content", response_model=GenerateContentResponse)
async def generate_content(
    request: GenerateContentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered content for multiple platforms.
    
    This endpoint calls an n8n webhook to generate platform-optimized content
    based on the provided context, tone, and keywords.
    
    **Note:** This is a stateless endpoint - nothing is saved to the database.
    Use the generated content with /post/multi to save as draft, schedule, or publish.
    
    **Request:**
    - `topic`: What the post is about
    - `tone`: Desired tone (professional, casual, friendly, etc.)
    - `hashtag`: Hashtags to include in the post
    - `platforms`: List of platforms to generate content for
    
    **Response:**
    Platform-specific content optimized for each selected platform.
    """
    # Check if content webhook is configured
    if not settings.N8N_CONTENT_WEBHOOK_PATH:
        raise HTTPException(
            status_code=500,
            detail="Content generation is not configured. Set N8N_CONTENT_WEBHOOK_PATH in environment."
        )
    
    webhook_url = get_n8n_url(settings.N8N_CONTENT_WEBHOOK_PATH)
    
    # Get user's workspace
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == current_user.id)
    )
    workspace = result.scalars().first()
    
    # Build workspace info
    workspace_info = None
    if workspace:
        workspace_info = {
            "business_name": workspace.business_name,
            "industry": workspace.industry,
            "default_tone": workspace.default_tone,
            "timezone": workspace.timezone
        }
    
    try:
        # Call n8n webhook
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json={
                    "topic": request.topic,
                    "tone": request.tone,
                    "hashtag": request.hashtag,
                    "platforms": request.platforms,
                    "workspace": workspace_info
                },
                timeout=60.0  # 60 second timeout for AI generation
            )
            
            if response.status_code != 200:
                logger.error(f"n8n returned error status: {response.status_code}")
                logger.error(f"n8n response body: {response.text}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Content generation service returned error: {response.status_code}"
                )
            
            n8n_response = response.json()
            logger.info(f"n8n response type: {type(n8n_response)}")
            logger.info(f"n8n raw response: {n8n_response}")
    
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Content generation timed out. Please try again."
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to content generation service: {str(e)}"
        )
    
    # Parse n8n response - can be either:
    # Format 1: {"results": [{"text": "...", "platform": "..."}]}
    # Format 2: [{"results": [{"text": "...", "platform": "..."}]}]
    generated = {}
    
    logger.info(f"Parsing n8n response, type: {type(n8n_response)}")
    
    # Extract results array from response
    results = []
    if isinstance(n8n_response, dict):
        # Direct dict format: {"results": [...]}
        results = n8n_response.get("results", [])
        logger.info(f"Dict format - found {len(results)} results")
    elif isinstance(n8n_response, list) and len(n8n_response) > 0:
        # Array format: [{"results": [...]}]
        results = n8n_response[0].get("results", [])
        logger.info(f"List format - found {len(results)} results")
    else:
        logger.warning(f"Unknown n8n response format: {n8n_response}")
    
    # Process results
    for result in results:
        platform = result.get("platform", "")
        text = result.get("text", "")
        logger.info(f"Processing platform: {platform}, text length: {len(text)}")
        if platform:
            generated[platform] = PlatformContent(
                platform=platform,
                content=text
            )

    
    # Ensure all requested platforms have an entry
    for platform in request.platforms:
        if platform not in generated:
            generated[platform] = PlatformContent(
                platform=platform,
                content=""
            )
    
    return GenerateContentResponse(
        success=True,
        generated=generated,
        input={
            "topic": request.topic,
            "tone": request.tone,
            "hashtag": request.hashtag
        }
    )


# ==================== Generate Image Endpoint ====================

@router.post("/generate/image", response_model=GenerateImageResponse)
async def generate_image(
    request: GenerateImageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered images for multiple platforms.
    
    This endpoint calls an n8n webhook to generate platform-optimized images
    with correct dimensions for each selected platform.
    
    **Platform Dimensions:**
    - `facebook`: 1200x630 (landscape)
    - `twitter`: 1200x675 (landscape)
    - `linkedin`: 1200x627 (landscape)
    - `instagram`: 1080x1080 (square)
    
    **Request:**
    - `topic`: What the image should represent
    - `tone`: Desired tone (professional, casual, friendly, etc.)
    - `hashtag`: Hashtags to inform the image style
    - `platforms`: List of target platforms
    
    **Response:**
    URLs to generated images for each platform.
    """
    # Check if image webhook is configured
    if not settings.N8N_IMAGE_WEBHOOK_PATH:
        raise HTTPException(
            status_code=500,
            detail="Image generation is not configured. Set N8N_IMAGE_WEBHOOK_PATH in environment."
        )
    
    webhook_url = get_n8n_url(settings.N8N_IMAGE_WEBHOOK_PATH)
    
    # Platform-specific dimensions
    platform_dimensions = {
        "facebook": {"width": 1200, "height": 630},
        "twitter": {"width": 1200, "height": 675},
        "linkedin": {"width": 1200, "height": 627},
        "instagram": {"width": 1080, "height": 1080}  # Square format
    }
    
    # Get user's workspace
    result = await db.execute(
        select(Workspace).where(Workspace.user_id == current_user.id)
    )
    workspace = result.scalars().first()
    
    # Build workspace info
    workspace_info = None
    if workspace:
        workspace_info = {
            "business_name": workspace.business_name,
            "industry": workspace.industry,
            "default_tone": workspace.default_tone,
            "timezone": workspace.timezone
        }
    
    try:
        # Call n8n webhook with all platforms
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json={
                    "topic": request.topic,
                    "tone": request.tone,
                    "hashtag": request.hashtag,
                    "platforms": request.platforms,
                    "workspace": workspace_info
                },
                timeout=120.0  # 120 second timeout for image generation
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Image generation service returned error: {response.status_code}"
                )
            
            n8n_response = response.json()
    
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Image generation timed out. Please try again."
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to image generation service: {str(e)}"
        )
    
    # Parse n8n response and build platform images
    generated = {}
    for platform in request.platforms:
        platform_data = n8n_response.get(platform, {})
        dimensions = platform_dimensions.get(platform, {"width": 1200, "height": 630})
        
        generated[platform] = PlatformImage(
            platform=platform,
            image_url=platform_data.get("image_url", ""),
            dimensions=dimensions
        )
    
    return GenerateImageResponse(
        success=True,
        generated=generated,
        input={
            "topic": request.topic,
            "tone": request.tone,
            "hashtag": request.hashtag
        }
    )

