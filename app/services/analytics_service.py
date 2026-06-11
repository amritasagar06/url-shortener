import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ClickAnalytics  # Updated model name!
from structlog import get_logger

logger = get_logger()

async def record_click(short_url_id: int, ip_address: str, user_agent: str, referrer: str, db: AsyncSession):
    """
    Asynchronously logs click parameters without slowing down the redirection route.
    """
    try:
        country = "Unknown"
        
        # Geolocation lookup block
        if ip_address and ip_address not in ("127.0.0.1", "localhost", "::1"):
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"http://ip-api.com/json/{ip_address}")
                    if response.status_code == 200:
                        geo_data = response.json()
                        if geo_data.get("status") == "success":
                            country = geo_data.get("countryCode", "Unknown")
            except Exception as geo_err:
                logger.warning("geoip_lookup_failed", error=str(geo_err))

        clean_referrer = "Direct"
        if referrer:
            clean_referrer = referrer[:500]

        # 3. Instantiate using your precise model property fields
        new_click = ClickAnalytics(
            short_url_id=short_url_id,
            ip_address=ip_address, # Saved raw matching your model schema structure
            referrer=clean_referrer,
            country=country,
            user_agent=user_agent[:500] if user_agent else None
        )
        
        db.add(new_click)
        await db.commit()
        logger.info("analytics_logged_successfully", short_url_id=short_url_id, country=country)

    except Exception as e:
        logger.error("analytics_engine_failure", error=str(e))
        await db.rollback()