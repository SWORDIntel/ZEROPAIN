from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Column, DateTime, Field, JSON, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default="user")
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True)))


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    job_type: str
    status: str
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True)))
