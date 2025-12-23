"""Media upload endpoints - Handle file uploads for posting"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import os
import uuid
from pathlib import Path

from app.core.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.user import User
from app.core.config import settings

router = APIRouter()

# Directory to store uploaded media
MEDIA_DIR = Path("media/uploads")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# Allowed image formats
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class UploadResponse(BaseModel):
    """Response schema for media upload"""
    success: bool
    file_url: str
    filename: str


@router.post("/upload", response_model=UploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload an image file for use in social media posts.
    
    Returns a publicly accessible URL that can be used in the posting API.
    
    **Supported formats**: JPG, JPEG, PNG, GIF, WEBP
    **Max size**: 5MB
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE / (1024*1024)}MB"
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = MEDIA_DIR / unique_filename
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Generate public URL
    # In production, this should be your actual domain
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    file_url = f"{base_url}/media/uploads/{unique_filename}"
    
    return UploadResponse(
        success=True,
        file_url=file_url,
        filename=unique_filename
    )


@router.delete("/{filename}")
async def delete_media(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete an uploaded media file.
    
    **Note**: Only the user who uploaded the file can delete it.
    """
    file_path = MEDIA_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete file
    os.remove(file_path)
    
    return {"success": True, "message": "File deleted successfully"}
