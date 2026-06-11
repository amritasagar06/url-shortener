from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional
from datetime import datetime

# --- URL Schemas ---
class URLBase(BaseModel):
    long_url: str

class URLCreate(URLBase):
    custom_code: Optional[str] = None

class URLResponse(URLBase):
    id: int
    short_code: str
    created_at: datetime
    clicks_count: int
    short_url: str # Calculated value field

    class Config:
        from_attributes = True

# --- Analytics Schemas ---
class ClickAnalyticsResponse(BaseModel):
    id: int
    clicked_at: datetime
    ip_address: Optional[str]
    country: Optional[str]
    referrer: Optional[str]
    user_agent: Optional[str]

    class Config:
        from_attributes = True