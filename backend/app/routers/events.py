from pydantic import BaseModel, HttpUrl, Field
from datetime import date, time
from typing import Optional, Literal
from enum import Enum

class Category(str, Enum):
    THEATER = "theater"
    CONCERT = "concert"
    EXHIBITION = "exhibition"
    CINEMA = "cinema"
    FESTIVAL = "festival"
    SPORT = "sport"
    KIDS = "kids"
    OTHER = "other"

class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: Category = Category.OTHER
    date_start: date
    date_end: Optional[date] = None
    time_start: Optional[time] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    city: str = "Уфа"
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    is_free: bool = False
    age_restriction: Optional[str] = None  # "0+", "6+", "12+", "18+"
    image_url: Optional[HttpUrl] = None
    source_url: HttpUrl
    source_site: str
    tags: list[str] = []

class EventCreate(EventBase):
    dedup_hash: str

class EventRead(EventBase):
    id: int
    class Config:
        from_attributes = True