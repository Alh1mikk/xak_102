from typing import Optional
import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, Double, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, Table, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB, OID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Categories(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='categories_pkey'),
        UniqueConstraint('name', name='categories_name_key'),
        UniqueConstraint('slug', name='categories_slug_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))

    events: Mapped[list['Events']] = relationship('Events', back_populates='category')


class Cities(Base):
    __tablename__ = 'cities'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='cities_pkey'),
        UniqueConstraint('name', name='cities_name_key')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    district: Mapped[Optional[str]] = mapped_column(Text)

    events: Mapped[list['Events']] = relationship('Events', back_populates='city')


t_pg_stat_statements = Table(
    'pg_stat_statements', Base.metadata,
    Column('userid', OID),
    Column('dbid', OID),
    Column('toplevel', Boolean),
    Column('queryid', BigInteger),
    Column('query', Text),
    Column('plans', BigInteger),
    Column('total_plan_time', Double(53)),
    Column('min_plan_time', Double(53)),
    Column('max_plan_time', Double(53)),
    Column('mean_plan_time', Double(53)),
    Column('stddev_plan_time', Double(53)),
    Column('calls', BigInteger),
    Column('total_exec_time', Double(53)),
    Column('min_exec_time', Double(53)),
    Column('max_exec_time', Double(53)),
    Column('mean_exec_time', Double(53)),
    Column('stddev_exec_time', Double(53)),
    Column('rows', BigInteger),
    Column('shared_blks_hit', BigInteger),
    Column('shared_blks_read', BigInteger),
    Column('shared_blks_dirtied', BigInteger),
    Column('shared_blks_written', BigInteger),
    Column('local_blks_hit', BigInteger),
    Column('local_blks_read', BigInteger),
    Column('local_blks_dirtied', BigInteger),
    Column('local_blks_written', BigInteger),
    Column('temp_blks_read', BigInteger),
    Column('temp_blks_written', BigInteger),
    Column('shared_blk_read_time', Double(53)),
    Column('shared_blk_write_time', Double(53)),
    Column('local_blk_read_time', Double(53)),
    Column('local_blk_write_time', Double(53)),
    Column('temp_blk_read_time', Double(53)),
    Column('temp_blk_write_time', Double(53)),
    Column('wal_records', BigInteger),
    Column('wal_fpi', BigInteger),
    Column('wal_bytes', Numeric),
    Column('jit_functions', BigInteger),
    Column('jit_generation_time', Double(53)),
    Column('jit_inlining_count', BigInteger),
    Column('jit_inlining_time', Double(53)),
    Column('jit_optimization_count', BigInteger),
    Column('jit_optimization_time', Double(53)),
    Column('jit_emission_count', BigInteger),
    Column('jit_emission_time', Double(53)),
    Column('jit_deform_count', BigInteger),
    Column('jit_deform_time', Double(53)),
    Column('stats_since', DateTime(True)),
    Column('minmax_stats_since', DateTime(True))
)


t_pg_stat_statements_info = Table(
    'pg_stat_statements_info', Base.metadata,
    Column('dealloc', BigInteger),
    Column('stats_reset', DateTime(True))
)


class Sources(Base):
    __tablename__ = 'sources'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='sources_pkey'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    base_url: Mapped[Optional[str]] = mapped_column(Text)

    import_logs: Mapped[list['ImportLogs']] = relationship('ImportLogs', back_populates='source')
    event_sources: Mapped[list['EventSources']] = relationship('EventSources', back_populates='source')


class Events(Base):
    __tablename__ = 'events'
    __table_args__ = (
        CheckConstraint('age_limit IS NULL OR age_limit >= 0', name='events_age_limit_check'),
        CheckConstraint('end_at IS NULL OR end_at >= start_at', name='events_check1'),
        CheckConstraint('price_max IS NULL OR price_max >= 0', name='events_price_max_check'),
        CheckConstraint('price_min IS NULL OR price_max IS NULL OR price_max >= price_min', name='events_check'),
        CheckConstraint('price_min IS NULL OR price_min >= 0', name='events_price_min_check'),
        CheckConstraint("status = ANY (ARRAY['draft'::text, 'published'::text, 'cancelled'::text])", name='events_status_check'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], name='events_category_id_fkey'),
        ForeignKeyConstraint(['city_id'], ['cities.id'], name='events_city_id_fkey'),
        PrimaryKeyConstraint('id', name='events_pkey'),
        Index('events_category_idx', 'category_id'),
        Index('events_city_idx', 'city_id'),
        Index('events_start_at_idx', 'start_at'),
        Index('events_status_idx', 'status'),
        Index('events_title_trgm_idx', 'title', postgresql_ops={'title': 'gin_trgm_ops'}, postgresql_using='gin')
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

    category: Mapped[Optional['Categories']] = relationship('Categories', back_populates='events')
    city: Mapped[Optional['Cities']] = relationship('Cities', back_populates='events')
    event_sources: Mapped[list['EventSources']] = relationship('EventSources', back_populates='event')


class ImportLogs(Base):
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
    errors: Mapped[Optional[object]] = mapped_column(JSONB)

    source: Mapped[Optional['Sources']] = relationship('Sources', back_populates='import_logs')


class EventSources(Base):
    __tablename__ = 'event_sources'
    __table_args__ = (
        ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE', name='event_sources_event_id_fkey'),
        ForeignKeyConstraint(['source_id'], ['sources.id'], name='event_sources_source_id_fkey'),
        PrimaryKeyConstraint('id', name='event_sources_pkey'),
        UniqueConstraint('source_id', 'external_id', name='event_sources_source_id_external_id_key'),
        Index('event_sources_event_idx', 'event_id'),
        Index('event_sources_source_idx', 'source_id')
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    external_id: Mapped[Optional[str]] = mapped_column(Text)
    raw_data: Mapped[Optional[object]] = mapped_column(JSONB)

    event: Mapped['Events'] = relationship('Events', back_populates='event_sources')
    source: Mapped['Sources'] = relationship('Sources', back_populates='event_sources')
