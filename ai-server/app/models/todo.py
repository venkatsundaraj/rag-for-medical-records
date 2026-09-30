from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from typing import List
from app.models.base import Base
from datetime import datetime




class User(Base):
    __tablename__ = "user"
    id:Mapped[int] = mapped_column(primary_key=True)
    name:Mapped[str] = mapped_column(String(128), nullable=False)
    todos:Mapped[List['Todo']] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    
class Todo(Base):
    __tablename__ = "todos"
    id:Mapped[int] = mapped_column(primary_key=True)
    title:Mapped[str] = mapped_column(nullable=False)
    completed:Mapped[bool] = mapped_column(default=False)
    created_at:Mapped[datetime] = mapped_column(default=datetime.utcnow)
    user_id:Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="cascade"), nullable=False)
    user:Mapped["User"] = relationship(back_populates="todos")
