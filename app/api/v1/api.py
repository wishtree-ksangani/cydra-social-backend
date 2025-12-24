from fastapi import APIRouter
from app.api.v1.endpoints import auth, me, workspaces, oauth, social_accounts, pages, media, platform_posts, multi_post, post_management, content_generation, agents

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(me.router, prefix="/me", tags=["users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(social_accounts.router, prefix="/social-accounts", tags=["social-accounts"])
api_router.include_router(pages.router, prefix="/social-accounts", tags=["pages"])
api_router.include_router(platform_posts.router, prefix="/post", tags=["posts"])
api_router.include_router(multi_post.router, prefix="/post", tags=["posts"])  # Multi-platform posting
api_router.include_router(content_generation.router, prefix="/post", tags=["content-generation"])  # AI content generation
api_router.include_router(post_management.router, prefix="/posts", tags=["post-management"])  # Post tracking & CRUD
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])  # Agent management
api_router.include_router(media.router, prefix="/media", tags=["media"])

