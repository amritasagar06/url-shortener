from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import ShortURL  # Adjust import based on your exact model filename
from app.utils.base62 import encode, generate_random_secure_id

class URLService:
    @staticmethod
    async def generate_unique_code(db: AsyncSession, max_retries: int = 5) -> str:
        """Generates a short code and verifies uniqueness against PostgreSQL with a retry loop."""
        for attempt in range(max_retries):
            # Generate a secure pseudorandom base62 handle
            potential_code = encode(generate_random_secure_id())
            
            # Collision Check: Check if it already exists in the database
            query = select(ShortURL).where(ShortURL.short_code == potential_code)
            result = await db.execute(query)
            if not result.scalar_one_or_none():
                return potential_code
                
        raise RuntimeError(f"System failed to allocate a unique short code after {max_retries} attempts.")

    @staticmethod
    async def create_short_url(
        db: AsyncSession, 
        original_url: str, 
        custom_code: str = None, 
        expires_in_days: int = None
    ) -> ShortURL:
        """Handles record initialization, custom alias evaluation, and expiration logic."""
        if custom_code:
            # Check if the custom alias is already occupied
            query = select(ShortURL).where(ShortURL.short_code == custom_code)
            result = await db.execute(query)
            if result.scalar_one_or_none():
                raise ValueError("The requested custom alias is already taken.")
            short_code = custom_code
        else:
            short_code = await URLService.generate_unique_code(db)

        # Calculate optional expiration timeline
        expires_at = None
        if expires_in_days:
            # ✨ FIXED: Generate UTC time and forcefully strip the tzinfo metadata to prevent DB conflicts
            expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).replace(tzinfo=None)

        new_url_record = ShortURL(
            short_code=short_code,
            original_url=original_url,
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(new_url_record)
        await db.commit()
        await db.refresh(new_url_record)
        return new_url_record