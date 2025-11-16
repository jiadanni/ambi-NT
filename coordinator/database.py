"""
Database setup and session management for the coordinator.

This module handles:
- Database connection pooling
- Session management
- Database initialization
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

from models import Base

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager."""

    def __init__(self, database_url: str):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection string
                         Format: postgresql://user:pass@host:port/dbname
        """
        self.database_url = database_url

        # Create engine with connection pooling
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL debugging
        )

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info(f"Database engine created for: {self._safe_url()}")

    def _safe_url(self) -> str:
        """Return database URL with password masked."""
        if '@' in self.database_url:
            parts = self.database_url.split('@')
            if ':' in parts[0]:
                user_part = parts[0].split(':')[0]
                return f"{user_part}:***@{parts[1]}"
        return self.database_url

    def create_tables(self):
        """
        Create all tables defined in models.

        Should be called once during initial setup.
        """
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")

    def drop_tables(self):
        """
        Drop all tables.

        WARNING: This will delete all data!
        Only use in development or testing.
        """
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("Database tables dropped")

    @contextmanager
    def get_session(self) -> Session:
        """
        Get a database session with automatic cleanup.

        Usage:
            with db.get_session() as session:
                # Use session
                session.query(...)
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """
        Get a database session (must be closed manually).

        Use get_session() context manager instead when possible.
        """
        return self.SessionLocal()

    def close(self):
        """Close database engine and cleanup connections."""
        logger.info("Closing database connections...")
        self.engine.dispose()


# Dependency for FastAPI
def get_db(database: Database):
    """
    FastAPI dependency for database sessions.

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db session
    """
    session = database.get_session_direct()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
