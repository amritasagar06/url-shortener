from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Date
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.models import ShortURL, ClickAnalytics

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Zenith Deep Telemetry Engine"]
)

@router.get("/{short_code}/summary", status_code=status.HTTP_200_OK)
async def get_url_summary(short_code: str, db: AsyncSession = Depends(get_db)):
    """
    Task T4-5: Retrieve high-fidelity analytical summary including total clicks, 
    unique visitor IP counts, top 5 countries, and top 5 referrers.
    """
    # 1. Fetch parent record
    url_stmt = select(ShortURL).where(ShortURL.short_code == short_code)
    url_result = await db.execute(url_stmt)
    url_record = url_result.scalar_one_or_none()
    
    if not url_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Telemetry target mapping tracking data not found for code: [{short_code}]"
        )

    url_id = url_record.id

    # 2. Count Unique IPs
    unique_ip_stmt = (
        select(func.count(func.distinct(ClickAnalytics.ip_hash)))
        .where(ClickAnalytics.url_id == url_id)
    )
    unique_ip_result = await db.execute(unique_ip_stmt)
    unique_ips = unique_ip_result.scalar() or 0

    # 3. Top 5 Countries
    country_stmt = (
        select(ClickAnalytics.country_code, func.count(ClickAnalytics.id))
        .where(ClickAnalytics.url_id == url_id)
        .group_by(ClickAnalytics.country_code)
        .order_by(func.count(ClickAnalytics.id).desc())
        .limit(5)
    )
    country_result = await db.execute(country_stmt)
    top_countries = [{"country_code": row[0], "clicks": row[1]} for row in country_result.all()]

    # 4. Top 5 Referrers
    referrer_stmt = (
        select(ClickAnalytics.referrer, func.count(ClickAnalytics.id))
        .where(ClickAnalytics.url_id == url_id)
        .group_by(ClickAnalytics.referrer)
        .order_by(func.count(ClickAnalytics.id).desc())
        .limit(5)
    )
    referrer_result = await db.execute(referrer_stmt)
    top_referrers = [{"referrer": row[0], "clicks": row[1]} for row in referrer_result.all()]

    return {
        "short_code": short_code,
        "long_url": url_record.long_url,
        "total_clicks": url_record.clicks_count,
        "unique_visitors": unique_ips,
        "top_countries": top_countries,
        "top_referrers": top_referrers,
        "is_active": url_record.is_active,
        "expires_at": url_record.expires_at.isoformat() if url_record.expires_at else None
    }


@router.get("/{short_code}/timeline", status_code=status.HTTP_200_OK)
async def get_url_timeline(short_code: str, db: AsyncSession = Depends(get_db)):
    """
    Task T4-6: Retrieve chronologically grouped click trends for the last 30 days.
    """
    # 1. Fetch parent record
    url_stmt = select(ShortURL).where(ShortURL.short_code == short_code)
    url_result = await db.execute(url_stmt)
    url_record = url_result.scalar_one_or_none()
    
    if not url_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Telemetry target mapping tracking data not found for code: [{short_code}]"
        )

    # Calculate 30-day window limit
    thirty_days_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)

    # 2. Run grouped trend query casting timestamps to dates
    timeline_stmt = (
        select(
            func.cast(ClickAnalytics.clicked_at, Date).label("click_date"),
            func.count(ClickAnalytics.id).label("clicks")
        )
        .where(ClickAnalytics.url_id == url_record.id)
        .where(ClickAnalytics.clicked_at >= thirty_days_ago)
        .group_by(func.cast(ClickAnalytics.clicked_at, Date))
        .order_by("click_date")
    )
    
    timeline_result = await db.execute(timeline_stmt)
    timeline_data = [
        {"date": row[0].isoformat(), "clicks": row[1]} for row in timeline_result.all()
    ]

    return {
        "short_code": short_code,
        "timeframe": "30_days",
        "timeline": timeline_data
    }