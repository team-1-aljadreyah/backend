from datetime import date, datetime, timezone
from typing import Optional, Any
from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, PK_BIGINT


class StockItem(Base, TimestampMixin):
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="tablet", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)

    moves: Mapped[list["StockMove"]] = relationship("StockMove", back_populates="item")


class StockMove(Base):
    __tablename__ = "stock_moves"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    by: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # create, receive, dispense, edit, sale
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock_items.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    change: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    item: Mapped["StockItem"] = relationship("StockItem", back_populates="moves")


class PharmacySale(Base):
    __tablename__ = "pharmacy_sales"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    by: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # prescription, counter
    customer: Mapped[str] = mapped_column(String(128), nullable=False)
    lines: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
