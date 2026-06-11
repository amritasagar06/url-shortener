from fastapi import FastAPI, Depends, Request, HTTPException, status, Security, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse
from ua_parser import user_agent_parser
import datetime
import hashlib
import secrets
import httpx
import asyncio

try:
    import redis.asyncio as aioredis
except ImportError:
    from redis import asyncio as aioredis

# Core Application Imports
from app.config import settings
from app.database import engine, get_db, AsyncSessionLocal
from app.models import ShortURL, ClickAnalytics
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limiter import SlidingWindowRateLimiter
from app.utils.url_validator import is_safe_url, validate_custom_code
from app.routers import analytics

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs"
)

# --- SECURITY PROTOCOLS ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        return None
    hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
    if hashed_key != settings.API_KEY_HASH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The provided API key is invalid or unauthorized."
        )
    return api_key

# --- MIDDLEWARES ---
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

redis_client = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
rate_limiter = SlidingWindowRateLimiter(redis_client)

@app.middleware("http")
async def enforce_sliding_rate_limiter(request: Request, call_next):
    # Pass metrics, health-checks, and documentation routes instantly
    if request.url.path in ("/", "/docs", "/openapi.json", "/health"):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    if api_key:
        identifier = f"apikey:{hashlib.sha256(api_key.encode()).hexdigest()[:12]}"
        limit = 100
    else:
        client_ip = request.client.host if request.client else "127.0.0.1"
        identifier = f"ip:{client_ip}"
        limit = 15

    if request.url.path == "/api/v1/shorten" and request.method == "POST":
        identifier = f"create:{identifier}"
        limit = 5

    try:
        await rate_limiter.check_rate_limit(identifier=identifier, limit=limit)
    except HTTPException as limit_exc:
        return JSONResponse(
            status_code=limit_exc.status_code,
            content={"detail": limit_exc.detail, "request_id": getattr(request.state, "request_id", None)}
        )

    return await call_next(request)


# --- GLOBAL EXCEPTION HANDLERS ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers or {},
        content={"detail": exc.detail, "request_id": getattr(request.state, "request_id", "unknown")}
    )

@app.exception_handler(Exception)
async def global_system_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "request_id": getattr(request.state, "request_id", "unknown")}
    )


# --- MOUNT ASSOCIATED ROUTERS ---
app.include_router(analytics.router)


# --- SYSTEM API BASE ENDPOINTS (MUST BE DEFINED BEFORE DYNAMIC REDIRECTS) ---
@app.get("/health")
async def health_check():
    """Verify infrastructure connectivity with non-blocking timeouts."""
    health_status = {"status": "healthy", "infrastructure": {"postgres": "unknown", "redis": "unknown"}}
    try:
        async def test_db():
            async with engine.connect() as conn: 
                await conn.execute(text("SELECT 1"))
        await asyncio.wait_for(test_db(), timeout=3.0)
        health_status["infrastructure"]["postgres"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["infrastructure"]["postgres"] = f"error: {str(e)}"
        
    try:
        await asyncio.wait_for(redis_client.ping(), timeout=3.0)
        health_status["infrastructure"]["redis"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["infrastructure"]["redis"] = f"error: {str(e)}"
    return health_status

@app.get("/")
async def root():
    return {"message": "Headless URL Shortener Engine Online. Connect via client."}


# --- URL CORE SHORTENING ROUTE ---
class ShortenRequest(BaseModel):
    long_url: str  
    custom_code: str | None = None  
    expires_in_days: int | None = None  

BASE62_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def generate_secure_base62_code(length: int = 6) -> str:
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(length))

@app.post("/api/v1/shorten", status_code=status.HTTP_201_CREATED)
async def create_short_url(payload: ShortenRequest, db: AsyncSession = Depends(get_db), api_key: str = Depends(verify_api_key)):
    if not is_safe_url(payload.long_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The provided destination URL points to a blocked or private location."
        )

    try:
        if payload.custom_code:
            chosen_code = validate_custom_code(payload.custom_code)
            stmt = select(ShortURL).where(ShortURL.short_code == chosen_code)
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="This custom alias is already taken!")
            generated_code = chosen_code
        else:
            generated_code = None
            for attempt in range(5):
                potential_code = generate_secure_base62_code(6)
                stmt = select(ShortURL).where(ShortURL.short_code == potential_code)
                res = await db.execute(stmt)
                if not res.scalar_one_or_none():
                    generated_code = potential_code
                    break
            if not generated_code:
                raise HTTPException(status_code=500, detail="Failed to allocate unique short code.")
        
        expiration_date = None
        if payload.expires_in_days and payload.expires_in_days > 0:
            expiration_date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=payload.expires_in_days)).replace(tzinfo=None)

        new_url = ShortURL(
            long_url=payload.long_url,  
            short_code=generated_code,
            clicks_count=0,
            expires_at=expiration_date,
            is_active=True
        )
        db.add(new_url)
        await db.commit()
        await db.refresh(new_url)
        
        return {
            "id": str(new_url.id),
            "short_code": generated_code,
            "long_url": payload.long_url,
            "short_url": f"http://localhost/{generated_code}", 
            "clicks_count": 0,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "expires_at": expiration_date.isoformat() if expiration_date else None
        }
    except HTTPException:
        raise
    except Exception as db_err:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(db_err))


# --- PAGINATED URL EXPLORER ---
@app.get("/api/v1/urls", status_code=status.HTTP_200_OK)
async def get_paginated_urls(page: int = 1, size: int = 10, db: AsyncSession = Depends(get_db)):
    if page < 1: page = 1
    if size < 1 or size > 100: size = 10
    offset_val = (page - 1) * size

    total_stmt = select(func.count(ShortURL.id))
    total_result = await db.execute(total_stmt)
    total_records = total_result.scalar() or 0

    urls_stmt = select(ShortURL).order_by(ShortURL.created_at.desc()).offset(offset_val).limit(size)
    urls_result = await db.execute(urls_stmt)
    records = urls_result.scalars().all()

    return {
        "total": total_records,
        "page": page,
        "size": size,
        "items": [
            {
                "id": str(r.id),
                "short_code": r.short_code,
                "long_url": r.long_url,
                "clicks_count": r.clicks_count,
                "is_active": r.is_active,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None
            } for r in records
        ]
    }


# --- REDIRECTION INTERCEPTOR (WILDCARD - KEEP AT BOTTOM) ---
@app.get("/{short_code}")
async def redirect_to_original(short_code: str, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # Ignore favicon requests
    if short_code == "favicon.ico":
         return JSONResponse(status_code=404, content={"detail": "Not found"})

    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Unknown")
    referrer = request.headers.get("referer", "Direct")

    cached_url = await redis_client.get(f"code:{short_code}")
    if cached_url:
        original_url = cached_url.decode('utf-8') if isinstance(cached_url, bytes) else cached_url
        background_tasks.add_task(async_click_logger_worker, short_code, client_ip, user_agent, referrer)
        return RedirectResponse(url=original_url, status_code=status.HTTP_302_FOUND)

    stmt = select(ShortURL).where(ShortURL.short_code == short_code, ShortURL.is_active == True)
    result = await db.execute(stmt)
    url_record = result.scalar_one_or_none()

    if not url_record:
        raise HTTPException(status_code=404, detail="Shortened link target not found.")

    if url_record.expires_at:
        expires_at = url_record.expires_at.replace(tzinfo=datetime.timezone.utc) if url_record.expires_at.tzinfo is None else url_record.expires_at
        if datetime.datetime.now(datetime.timezone.utc) > expires_at:
            await redis_client.delete(f"code:{short_code}")
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="This target has expired.")

    await redis_client.set(f"code:{short_code}", url_record.long_url, ex=3600)
    background_tasks.add_task(async_click_logger_worker, short_code, client_ip, user_agent, referrer)
    return RedirectResponse(url=url_record.long_url, status_code=status.HTTP_302_FOUND)


# --- BACKGROUND TELEMETRY WORKER ---
async def async_click_logger_worker(short_code: str, ip: str, ua: str, ref: str):
    async with AsyncSessionLocal() as session:
        try:
            url_stmt = select(ShortURL).where(ShortURL.short_code == short_code)
            url_result = await session.execute(url_stmt)
            url_record = url_result.scalar_one_or_none()
            if not url_record: return

            ip_hash = hashlib.sha256((ip + "ZENITH_PRODUCTION_SECRET_SALT").encode("utf-8")).hexdigest()
            parsed_ua = user_agent_parser.Parse(ua)
            browser = parsed_ua.get('user_agent', {}).get('family', 'Unknown')
            device_info = parsed_ua.get('device', {})
            is_bot = parsed_ua.get('user_agent', {}).get('family', '').lower() in ['bot', 'spider', 'crawler']
            
            if is_bot: device_type = "bot"
            elif device_info.get('is_mobile') or parsed_ua.get('os', {}).get('family') in ['Android', 'iOS']: device_type = "mobile"
            else: device_type = "desktop"

            country_code, city = "UN", "Unknown"
            if ip not in ["127.0.0.1", "localhost", "::1"]:
                try:
                    async with httpx.AsyncClient(timeout=1.5) as client:
                        response = await client.get(f"http://ip-api.com/json/{ip}")
                        if response.status_code == 200:
                            geo_data = response.json()
                            if geo_data.get("status") == "success":
                                country_code = geo_data.get("countryCode", "UN")
                                city = geo_data.get("city", "Unknown")
                except Exception: pass

            clean_referrer = "Direct"
            if ref and ref != "Direct":
                try:
                    parsed_ref = urlparse(ref)
                    clean_referrer = parsed_ref.netloc if parsed_ref.netloc else ref
                except Exception: clean_referrer = ref

            analytics_entry = ClickAnalytics(
                url_id=url_record.id,
                ip_hash=ip_hash,
                referrer=clean_referrer,
                country_code=country_code,
                city=city,
                browser=browser,
                device_type=device_type
            )
            session.add(analytics_entry)
            url_record.clicks_count += 1
            await session.commit()
        except Exception as async_err:
            await session.rollback()