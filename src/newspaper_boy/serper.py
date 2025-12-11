import requests
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime, timedelta, timezone, date
import dateutil.parser as dateutil_parser
import re
from newspaper_boy import SERPER_API_KEY, KEYWORDS
from newspaper_boy.types import Citation, DateRangeStr, SearchType

DATE_RANGE_MAP = {
    "past_hour": "qdr:h,sbd:1",
    "past_day": "qdr:d,sbd:1",
    "past_week": "qdr:w,sbd:1",
    "past_month": "qdr:m,sbd:1",
    "past_year": "qdr:y,sbd:1",
    "all_time": None,
}


def _build_query(raw_string: str, csv_or_list: str) -> str:
    or_list = [f'"{item.strip()}"' for item in csv_or_list.split(",") if item.strip()]
    or_string = " OR ".join(or_list)
    return f"{or_string} {raw_string}".strip()


def _normalize_serper_date(
    raw: Optional[str], reference_dt: datetime
) -> Optional[datetime]:
    """
    Convert Serper's human-readable date → real datetime (UTC).
    Returns None if parsing fails.
    """
    if not raw:
        return None

    raw = raw.strip().lower()

    try:
        dt = dateutil_parser.parse(raw, fuzzy=False)
        if dt.year >= 1000:
            return (
                dt.astimezone(timezone.utc)
                if dt.tzinfo
                else dt.replace(tzinfo=timezone.utc)
            )
    except (ValueError, TypeError, OverflowError):
        pass

    now = reference_dt or datetime.now(timezone.utc)

    patterns = [
        (r"(\d+)\s*minutes? ago", timedelta(minutes=1)),
        (r"(\d+)\s*hours? ago", timedelta(hours=1)),
        (r"(\d+)\s*days? ago", timedelta(days=1)),
    ]
    for pattern, delta in patterns:
        m = re.match(pattern, raw)
        if m:
            return now - delta * int(m.group(1))

    if "yesterday" in raw:
        return (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if raw in ("just now", "moments ago", "seconds ago"):
        return now

    return None


def _serper_results_to_citations(
    results: List[Dict[str, Any]],
    source_type: str = "news",
    access_date: Optional[str] = None,
    reference_dt: Optional[datetime] = None,
    exclude_publishers: Optional[List[str]] = [],
) -> List[Citation]:
    """
    Convert Serper results → Citation records with **normalized ISO datetime**.
    """
    if access_date is None:
        access_date = date.today().isoformat()

    if reference_dt is None:
        reference_dt = datetime.now(timezone.utc)

    citations: List[Citation] = []
    seen_urls = set()

    for idx, item in enumerate(results, start=1):
        url = item.get("link") or item.get("url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = item.get("title")
        raw_date = item.get("date")
        publisher = item.get("source") or item.get("siteName")

        # Normalize the date
        normalized_date = _normalize_serper_date(raw_date, reference_dt)
        media_type = "video" if source_type == "videos" else "text"
        citation: Citation = {
            "citation_id": f"{source_type[:1].upper()}{idx:04d}",
            "source_type": source_type,
            "title": title,
            "date": normalized_date,  # ISO datetime string or None
            "url": url,
            "access_date": access_date,
            "jurisdiction": None,
            "publisher": publisher,
            "publication": None,
            "author": None,
            "metadata": {
                "original_date_string": raw_date,
                "snippet": item.get("snippet"),
                "imageUrl": item.get("imageUrl"),
            },
            "media_type": media_type,
        }

        # Remove empty metadata dict
        if not any(citation["metadata"].values()):
            citation["metadata"] = None

        if publisher not in exclude_publishers:
            citations.append(citation)

    return citations


def serper_search(
    raw_string: str = "",
    csv_or_list: str = KEYWORDS,
    search_type: Literal["search", "news", "videos"] | SearchType = "news",
    country: Literal["ca", "us", "gb", "au", "de", "fr", "jp"] = "ca",
    location: str = "Canada",
    language: str = "en",
    date_range: DateRangeStr = "past_day",  # ← now human readable!
    max_page_count: int = 1,
    exclude_publishers: Optional[List[str]] = [],
) -> List[Citation]:
    """
    Example usage:
        citations = serper_search(
            csv_or_list="gun control, bill c-21, handgun freeze",
            date_range="past_day",        # ← so much nicer!
            max_page_count=3
        )
    """
    # Resolve search_type
    if isinstance(search_type, SearchType):
        search_type_str = search_type.value
    else:
        search_type_str = search_type

    # Resolve date_range → tbs value
    tbs_value = DATE_RANGE_MAP.get(date_range)

    base_url = "https://google.serper.dev"
    url = (
        f"{base_url}/news"
        if search_type_str == "news"
        else (
            f"{base_url}/videos"
            if search_type_str == "videos"
            else f"{base_url}/search"
        )
    )

    def build_payload(page: int = 1) -> Dict[str, Any]:
        q = _build_query(raw_string, csv_or_list)
        payload = {
            "q": q,
            "gl": country,
            "hl": language,
            "location": location,
            "page": page,
        }
        if tbs_value:
            payload["tbs"] = tbs_value
        return payload

    all_results: List[Dict[str, Any]] = []
    page = 1
    seen_links = set()

    while page <= max_page_count:
        payload = build_payload(page)

        try:
            response = requests.post(
                url,
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.HTTPError as e:
            print(f"HTTP {e.response.status_code}: {e.response.text}")
            break
        except Exception as e:
            print(f"Request failed: {e}")
            break

        results_key = (
            "news"
            if search_type_str == "news"
            else "videos" if search_type_str == "videos" else "organic"
        )
        new_results = data.get(results_key, [])

        if not new_results:
            break

        for item in new_results:
            link = item.get("link") or item.get("url")
            if link and link not in seen_links:
                all_results.append(item)
                seen_links.add(link)

        if len(new_results) < 10:
            break

        page += 1

    citations = _serper_results_to_citations(
        all_results, source_type=search_type_str, exclude_publishers=exclude_publishers
    )
    return citations
