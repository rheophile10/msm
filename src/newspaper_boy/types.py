from typing import TypedDict, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime


class SearchType(Enum):
    SEARCH = "search"
    NEWS = "news"
    VIDEO = "videos"


DateRangeStr = Literal[
    "past_hour", "past_day", "past_week", "past_month", "past_year", "all_time"
]

CountryCode = Literal["ca", "us", "gb", "au", "de", "fr", "jp"]


class SerperScrapeTask(TypedDict):
    raw_string: str
    csv_or_list: str
    search_type: Literal["search", "news", "videos"]
    country: Literal["ca", "us", "gb", "au", "de", "fr", "jp"]
    location: str
    language: str
    date_range: DateRangeStr
    max_page_count: int


class Citation(TypedDict):
    citation_id: str
    source_type: str
    title: Optional[str]
    date: datetime
    url: str
    access_date: datetime
    raw_date_string: Optional[str]
    jurisdiction: str
    publisher: Optional[str]
    publication: Optional[str]
    author: Optional[str]
    media_type: str = "news"
    metadata: Optional[Dict[str, Any]]


class TextChunk(TypedDict):
    textchunk_id: str
    citation_id: str
    text: str
    section: Optional[str]
