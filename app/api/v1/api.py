from fastapi import APIRouter
from app.api.v1.endpoints import auth, me, workspaces, oauth, social_accounts, pages, posts, media, platform_posts

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(me.router, prefix="/me", tags=["users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(social_accounts.router, prefix="/social-accounts", tags=["social-accounts"])
api_router.include_router(pages.router, prefix="/social-accounts", tags=["pages"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])  # Legacy unified endpoint
api_router.include_router(platform_posts.router, prefix="/post", tags=["platform-posts"])  # New clean endpoints
api_router.include_router(media.router, prefix="/media", tags=["media"])
