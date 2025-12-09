import json
import requests
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
import uuid
import asyncio
from urllib.parse import urlparse

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from newspaper_boy.types import Citation, TextChunk
from newspaper_boy import SERPER_API_KEY, KEYWORDS


async def fetch_article_content(
    url: str, browser, timeout: int = 30_000
) -> Optional[str]:
    """
    Fetch and extract clean article text using Playwright with multiple fallback strategies.
    """
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        java_script_enabled=True,
        bypass_csp=True,
    )

    # Optional: Block images, fonts, etc. for speed
    await context.route(
        "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort()
    )

    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        # Wait a bit for dynamic content
        await page.wait_for_timeout(3000)

        # Strategy 1: Look for common article selectors
        article_selectors = [
            "article",
            "[role='article']",
            ".article-body",
            ".story-body",
            ".post-content",
            ".entry-content",
            "main article",
            ".content__article-body",
            ".article__content",
        ]

        text_content = None
        for selector in article_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text_content = await element.inner_text()
                    if text_content and len(text_content.strip()) > 200:
                        break
            except:
                continue

        # Strategy 2: Fallback to readability-like extraction (all <p> inside main content areas)
        if not text_content or len(text_content.strip()) < 200:
            # Try to find the main content area
            main_selectors = [
                "main",
                "article",
                "[class*='content']",
                "[class*='post']",
                "[class*='story']",
            ]
            main_content = None
            for sel in main_selectors:
                el = await page.query_selector(sel)
                if el:
                    main_content = el
                    break

            if main_content:
                paragraphs = await main_content.query_selector_all(
                    "p, div[class*='paragraph'], div[class*='body']"
                )
                lines = []
                for p in paragraphs:
                    text = await p.inner_text()
                    text = text.strip()
                    if not text:
                        continue
                    if len(text) > 30:  # filter junk
                        lines.append(text)
                text_content = "\n\n".join(lines)

        # Strategy 3: Last resort - all visible text
        if not text_content or len(text_content.strip()) < 200:
            text_content = await page.evaluate(
                """() => {
                // Remove scripts, styles, nav, header, footer
                document.querySelectorAll('script, style, nav, header, footer, aside, .ad, .advert').forEach(el => el.remove());
                return document.body.innerText || '';
            }"""
            )

        full_text = text_content.strip() if text_content else ""

        # Clean up extra whitespace
        import re

        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = re.sub(r"[ \t]+", " ", full_text)

        return full_text if len(full_text) > 200 else None

    except PlaywrightTimeoutError:
        print("   timeout")
        return None
    except Exception as e:
        print(f"   playwright error: {e}")
        return None
    finally:
        await context.close()


def serper_search(query: str, num: int = 100) -> List[Dict[str, Any]]:
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": num})
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("organic", [])


def build_query(
    keywords: List[str],
    country: str = "Canada",
    after: date = date.today() - timedelta(days=1),
) -> str:
    after_str = after.strftime("%Y-%m-%d")
    keyword_part = " ".join(keywords)
    return f"{keyword_part} {country} after:{after_str}"


async def scrape_news_playwright(
    keywords: List[str] = KEYWORDS,
    after: date = date.today() - timedelta(days=1),
    max_results: int = 200,
    delay: float = 2.0,
    concurrency: int = 5,  # control how many tabs at once
) -> List[Dict[str, Any]]:
    query = build_query(keywords, after=after)
    print(f"Query: {query}")

    results = serper_search(query, num=max_results)
    print(f"Found ~{len(results)} results from Serper")

    collected = []
    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def process_item(item):
            async with semaphore:
                url = item["link"]
                title_from_serper = item.get("title")
                date_from_serper = item.get("date")
                print(f"→ {url}")

                try:
                    text = await fetch_article_content(url, browser)
                    if not text or len(text) < 300:
                        print("   too short or failed to extract")
                        return

                    citation_id = str(uuid.uuid4())

                    # Try to get title from page if possible
                    context = await browser.new_context()
                    page = await context.new_page()
                    try:
                        await page.goto(
                            url, wait_until="domcontentloaded", timeout=15_000
                        )
                        page_title = await page.title()
                    except:
                        page_title = title_from_serper
                    finally:
                        await context.close()

                    citation: Citation = {
                        "citation_id": citation_id,
                        "source_type": "news_article",
                        "title": page_title or title_from_serper or "Untitled",
                        "date": date_from_serper,
                        "url": url,
                        "access_date": date.today().isoformat(),
                        "jurisdiction": "Canada",
                        "publisher": urlparse(url).netloc,
                        "author": None,  # could enhance later with meta tags
                        "metadata": {"serper_snippet": item.get("snippet")},
                    }

                    # Split into paragraphs
                    paragraphs = [
                        p.strip() for p in text.split("\n\n") if len(p.strip()) > 50
                    ]

                    chunks: List[TextChunk] = [
                        {
                            "textchunk_id": str(uuid.uuid4()),
                            "citation_id": citation_id,
                            "text": para,
                            "section": f"para_{i+1}",
                        }
                        for i, para in enumerate(paragraphs)
                    ]

                    collected.append({"citation": citation, "chunks": chunks})
                    print(f"   saved {len(paragraphs)} paragraphs")

                except Exception as e:
                    print(f"   error: {e}")
                finally:
                    await asyncio.sleep(delay)  # politeness delay

        # Run concurrently
        tasks = [process_item(item) for item in results]
        await asyncio.gather(*tasks, return_exceptions=False)

        await browser.close()

    return collected


# Convenience sync wrapper
scrape_news = lambda *args, **kwargs: asyncio.run(
    scrape_news_playwright(*args, **kwargs)
)
