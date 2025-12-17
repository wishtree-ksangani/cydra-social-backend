from fastapi import APIRouter
from app.api.v1.endpoints import users, auth, me, workspaces, oauth, social_accounts

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
api_router.include_router(social_accounts.router, prefix="/social-accounts", tags=["social-accounts"])
