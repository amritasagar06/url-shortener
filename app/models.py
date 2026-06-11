import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    urls = relationship("ShortURL", back_populates="owner", cascade="all, delete-orphan")


class ShortURL(Base):
    __tablename__ = "short_urls"

    id = Column(Integer, primary_key=True, index=True)
    long_url = Column(Text, nullable=False)
    short_code = Column(String, unique=True, index=True, nullable=False)
    clicks_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # Day 3 Architectural Additions
    expires_at = Column(DateTime, nullable=True)  # Handles link temporal limits
    is_active = Column(Boolean, default=True, nullable=False)  # Implements soft-deletion tracking
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    owner = relationship("User", back_populates="urls")
    clicks = relationship("ClickAnalytics", back_populates="short_url", cascade="all, delete-orphan")


class ClickAnalytics(Base):
    __tablename__ = "click_analytics"

    id = Column(Integer, primary_key=True, index=True)
    url_id = Column(Integer, ForeignKey("short_urls.id", ondelete="CASCADE"), nullable=False)
    clicked_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # Day 4 Deep Telemetry Metrics Columns (Privacy-safe & Granular)
    ip_hash = Column(String(64), nullable=False)       # Privacy compliance (SHA-256)
    referrer = Column(String(512), default="Direct")
    country_code = Column(String(8), default="UN")
    city = Column(String(128), default="Unknown")
    browser = Column(String(64), default="Unknown")
    device_type = Column(String(32), default="desktop") # mobile, desktop, bot

    # Relationships
    short_url = relationship("ShortURL", back_populates="clicks")