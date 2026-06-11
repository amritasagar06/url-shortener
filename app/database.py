from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# --- 1. INITIALIZE ASYNC ENGINE ---
# Leverages the database connection URL and toggles dynamic SQL echoing 
# based on our newly added ENVIRONMENT settings.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True if settings.ENVIRONMENT == "development" else False,
    future=True
)

# --- 2. ASYNC SESSION FACTORY ---
# Configures a non-blocking local session maker for transaction contexts.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# --- 3. DECLARATIVE BASE ---
# Serves as the structural ORM parent for all database tables/models.
Base = declarative_base()

# --- 4. FASTAPI DEPENDENCY ---
# Provides a transactional database session per incoming request scope 
# and guarantees clean closure upon execution completion.
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()