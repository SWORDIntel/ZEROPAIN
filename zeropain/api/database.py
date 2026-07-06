import os
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from zeropain.database.backends import database_backend_status, require_database_backend

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zeropain.db")

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)


def init_db() -> None:
    require_database_backend()
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


__all__ = ["DATABASE_URL", "database_backend_status", "engine", "get_session", "init_db"]
