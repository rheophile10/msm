from typing import TypedDict, Optional, Dict, Any

class Citation(TypedDict):
    citation_id: str
    source_type: str
    title: Optional[str]
    date: Optional[str]
    url: str
    access_date: str
    jurisdiction: str
    publisher: Optional[str]
    publication: Optional[str]
    author: Optional[str]
    metadata: Optional[Dict[str, Any]]

class TextChunk(TypedDict):
    textchunk_id: str
    citation_id: str
    text: str
    section: Optional[str]