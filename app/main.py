from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import check_db_connection
from app.core.config import settings
from app.api.v1.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        await check_db_connection()
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise e
    yield
    # Shutdown (if needed)

app = FastAPI(title="FastAPI with uv", lifespan=lifespan)

# Configure CORS from environment settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "FastAPI + uv is working 🚀"}
