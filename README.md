# Cydra Socials Backend

FastAPI backend for Cydra Socials application with JWT authentication, PostgreSQL database, multi-platform social media posting, and AI-powered content generation.

## Features

- 🔐 **JWT Authentication** - Secure user authentication with access tokens
- 👤 **User Management** - Complete CRUD operations for user profiles
- 🏢 **Workspace Management** - One-to-one workspace per user
- 🗄️ **PostgreSQL Database** - Async SQLAlchemy with Alembic migrations
- 🔒 **Password Security** - Bcrypt password hashing
- 🌐 **CORS Support** - Configurable cross-origin resource sharing
- 📝 **API Documentation** - Auto-generated Swagger/ReDoc docs
- 🤖 **AI Content Generation** - n8n webhook integration for AI-powered content
- 📱 **Multi-Platform Posting** - Post to Facebook, Instagram, Twitter, LinkedIn
- 📅 **Draft & Scheduling** - Save drafts, schedule posts, or publish immediately
- 📊 **Analytics** - Post statistics by status and platform


## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy (async)
- **Migrations**: Alembic
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt
- **Package Manager**: uv
- **Python**: 3.12

## Prerequisites

- Python 3.12+
- Docker and Docker Compose (for PostgreSQL)
- uv package manager

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd cydra-socials-backend
```

### 2. Environment Setup

```bash
cp .env.sample .env
```

Edit `.env` and configure your settings. **Important**: Generate a secure `SECRET_KEY` for production:

```bash
openssl rand -hex 32
```

### 3. Start Database

```bash
docker-compose up -d
```

### 4. Install Dependencies

```bash
uv sync
```

### 5. Run Migrations

```bash
uv run alembic upgrade head
```

### 6. Start Application

```bash
uv run uvicorn app.main:app --reload
```

The application will be available at:
- **API**: http://localhost:8000
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Development

### Database Migrations

```bash
# Create new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback last migration
uv run alembic downgrade -1
```

### Database Management

```bash
# Stop database
docker-compose down

# Reset database (WARNING: Deletes all data)
docker-compose down -v
docker-compose up -d
uv run alembic upgrade head
```

## Project Structure

```
cydra-socials-backend/
├── alembic/                 # Database migrations
├── app/
│   ├── api/                # API routes and dependencies
│   ├── core/               # Configuration and utilities
│   ├── models/             # Database models
│   ├── schemas/            # Pydantic schemas
│   └── main.py             # Application entry point
├── docker-compose.yml      # PostgreSQL container
├── .env.sample             # Environment template
└── README.md
```

## Environment Configuration

### Required Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (change in production!) |
| `ENCRYPTION_KEY` | Token encryption key (generate with Fernet) |

### Social Platform OAuth

| Variable | Description |
|----------|-------------|
| `FACEBOOK_CLIENT_ID` | Facebook App Client ID |
| `FACEBOOK_CLIENT_SECRET` | Facebook App Secret |
| `TWITTER_CLIENT_ID` | Twitter API Client ID |
| `TWITTER_CLIENT_SECRET` | Twitter API Client Secret |
| `LINKEDIN_CLIENT_ID` | LinkedIn App Client ID |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn App Secret |
| `OAUTH_REDIRECT_URL` | OAuth callback URL |

### AI Content Generation (n8n)

| Variable | Description |
|----------|-------------|
| `N8N_HOST_URL` | n8n instance URL (e.g., https://n8n.example.com) |
| `N8N_CONTENT_WEBHOOK_PATH` | Webhook path for content generation |
| `N8N_IMAGE_WEBHOOK_PATH` | Webhook path for image generation |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALGORITHM` | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | Token expiration time |
| `CORS_ORIGINS` | * | Allowed CORS origins |
| `SCHEDULER_INTERVAL_SECONDS` | 30 | Post scheduler interval |


### CORS Configuration

Supports multiple formats:

```env
# Allow all (development)
CORS_ORIGINS=*

# Comma-separated
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# JSON array (recommended)
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

## Production Deployment

1. Generate strong `SECRET_KEY`
2. Update `CORS_ORIGINS` with your frontend domain(s)
3. Use production database credentials
4. Set environment variables securely (don't use .env file)
5. Enable HTTPS
6. Run with multiple workers:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Troubleshooting

**Port 5432 already in use:**
```bash
lsof -i :5432
sudo systemctl stop postgresql
```

**Database connection failed:**
- Check Docker container: `docker-compose ps`
- Verify DATABASE_URL in `.env`
- Check logs: `docker-compose logs postgres`

**Migration errors:**
```bash
uv run alembic current
uv run alembic history
```
