from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

# ---------- Справочники ----------
class CityBase(BaseModel):
    name: str
    district: Optional[str] = None

class CityOut(CityBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    name: str
    slug: str

class CategoryOut(CategoryBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

# ---------- Событие ----------
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    address: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    age_limit: Optional[int] = None
    image_url: Optional[str] = None
    organizer: Optional[str] = None
    status: str = "published"

class EventOut(EventBase):
    latitude: float | None = None
    longitude: float | None = None
    source_urls: list[str] = Field(default_factory=list)
    id: UUID
    city: Optional[CityOut] = None
    category: Optional[CategoryOut] = None
    model_config = ConfigDict(from_attributes=True)

# ---------- Входные данные от парсера ----------
class EventCreate(EventBase):
    city_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    external_id: Optional[str] = None
    source_id: UUID
    source_url: Optional[str] = None
    raw_data: Optional[dict] = None

# ---------- Фильтры для GET /events ----------
class EventFilter(BaseModel):
    ids: list[UUID] | None = None
    family_only: bool = False
    city_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    price_max: Optional[int] = None
    age_max: Optional[int] = None
    q: Optional[str] = None  # поиск по title