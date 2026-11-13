from typing import Optional, Any
import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Category(Base):
    __tablename__ = 'categories'  # ← Проверьте в Supabase, если там 'Category', оставьте 'Category'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='Category_pkey'),
        UniqueConstraint('name', name='Category_name_key'),
        UniqueConstraint('slug', name='Category_slug_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    events: Mapped[list['Event']] = relationship('Event', back_populates='category')

class City(Base):
    __tablename__ = 'cities'  # ← Проверьте в Supabase
    __table_args__ = (
        PrimaryKeyConstraint('id', name='City_pkey'),
        UniqueConstraint('name', name='City_name_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    district: Mapped[Optional[str]] = mapped_column(Text)

    events: Mapped[list['Event']] = relationship('Event', back_populates='city')

class Source(Base):
    __tablename__ = 'sources'  # ← Проверьте в Supabase
    __table_args__ = (
        PrimaryKeyConstraint('id', name='Source_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    base_url: Mapped[Optional[str]] = mapped_column(Text)

    import_logs: Mapped[list['ImportLog']] = relationship('ImportLog', back_populates='source')
    event_sources: Mapped[list['EventSource']] = relationship('EventSource', back_populates='source')

class Event(Base):
    __tablename__ = 'events'  # ← Проверьте в Supabase
    __table_args__ = (
        CheckConstraint('age_limit IS NULL OR age_limit >= 0', name='Event_age_limit_check'),
        CheckConstraint('end_at IS NULL OR end_at >= start_at', name='Event_check1'),
        CheckConstraint('price_max IS NULL OR price_max >= 0', name='Event_price_max_check'),
        CheckConstraint('price_min IS NULL OR price_max IS NULL OR price_max >= price_min', name='Event_check'),
        CheckConstraint('price_min IS NULL OR price_min >= 0', name='Event_price_min_check'),
        CheckConstraint("status = ANY (ARRAY['draft'::text, 'published'::text, 'cancelled'::text])", name='Event_status_check'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], name='Event_category_id_fkey'),
        ForeignKeyConstraint(['city_id'], ['cities.id'], name='Event_city_id_fkey'),
        PrimaryKeyConstraint('id', name='Event_pkey'),
        Index('Event_category_idx', 'category_id'),
        Index('Event_city_idx', 'city_id'),
        Index('Event_start_at_idx', 'start_at'),
        Index('Event_status_idx', 'status'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'published'::text"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    description: Mapped[Optional[str]] = mapped_column(Text)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    city_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    address: Mapped[Optional[str]] = mapped_column(Text)
    end_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    price_min: Mapped[Optional[int]] = mapped_column(Integer)
    price_max: Mapped[Optional[int]] = mapped_column(Integer)
    age_limit: Mapped[Optional[int]] = mapped_column(Integer)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    organizer: Mapped[Optional[str]] = mapped_column(Text)

    category: Mapped[Optional['Category']] = relationship('Category', back_populates='events')
    city: Mapped[Optional['City']] = relationship('City', back_populates='events')
    event_sources: Mapped[list['EventSource']] = relationship('EventSource', back_populates='event', cascade="all, delete-orphan")

class ImportLog(Base):
    __tablename__ = 'import_logs'
    __table_args__ = (
        ForeignKeyConstraint(['source_id'], ['sources.id'], name='import_logs_source_id_fkey'),
        PrimaryKeyConstraint('id', name='import_logs_pkey')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'running'::text"))
    records_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    errors: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    source: Mapped[Optional['Source']] = relationship('Source', back_populates='import_logs')

class EventSource(Base):
    __tablename__ = 'event_sources'  # ← Проверьте в Supabase (было 'event_Source')
    __table_args__ = (
        ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE', name='event_Source_event_id_fkey'),
        ForeignKeyConstraint(['source_id'], ['sources.id'], name='event_Source_source_id_fkey'),
        PrimaryKeyConstraint('id', name='event_Source_pkey'),
        UniqueConstraint('source_id', 'external_id', name='event_Source_source_id_external_id_key'),
        Index('event_Source_event_idx', 'event_id'),
        Index('event_Source_source_idx', 'source_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    external_id: Mapped[Optional[str]] = mapped_column(Text)
    raw_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    event: Mapped['Event'] = relationship('Event', back_populates='event_sources')
    source: Mapped['Source'] = relationship('Source', back_populates='event_sources')

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    session_hash: Mapped[Optional[str]] = mapped_column(Text, unique=True)
    session_expires: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
