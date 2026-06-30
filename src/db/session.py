import os
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Enable foreign key constraints in SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def get_db_engine(db_path: str = "data/platform.db") -> Engine:
    """
    Creates and returns a SQLAlchemy Engine.
    Ensures the parent directory exists.
    """
    # Resolve absolute path
    abs_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    
    database_url = f"sqlite:///{abs_path}"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
    )
    return engine

def init_db(db_path: str = "data/platform.db") -> None:
    """Creates all tables in the SQLite database if they don't exist."""
    engine = get_db_engine(db_path)
    Base.metadata.create_all(engine)

def get_session_factory(db_path: str = "data/platform.db") -> sessionmaker[Session]:
    """Returns a sessionmaker factory configured for the SQLite DB."""
    engine = get_db_engine(db_path)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
