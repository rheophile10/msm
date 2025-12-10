from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import asyncio
from urllib.parse import urlparse

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from newspaper_boy.types import Citation, TextChunk
from newspaper_boy.serper import serper_search
from newspaper_boy import KEYWORDS


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


async def scrape_news_playwright(
    citations: List[Citation],
    *,
    delay: float = 2.0,
    concurrency: int = 5,
) -> List[Dict[str, Any]]:
    """
    Enriches existing news citations with full text.
    Only processes citations where source_type == "news"
    Preserves original citation_id and metadata.
    """
    # Filter only news citations
    news_citations = [
        c for c in citations if c.get("media_type") == "text" and c.get("url")
    ]

    if not news_citations:
        print("No news citations to scrape.")
        return []

    collected = []
    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        async def process_citation(original_citation: Citation):
            async with semaphore:
                citation = original_citation.copy()  # work on a mutable copy
                url = citation["url"]
                print(f"Scraping → {url}")

                try:
                    text = await fetch_article_content(url, browser)
                    if not text or len(text) < 400:
                        print(
                            f"   too short or failed ({len(text) if text else 0} chars)"
                        )
                        return

                    # Enhance title from page if missing or generic
                    if not citation.get("title") or "Untitled" in citation.get(
                        "title", ""
                    ):
                        context = await browser.new_context()
                        page = await context.new_page()
                        try:
                            await page.goto(
                                url, wait_until="domcontentloaded", timeout=15_000
                            )
                            page_title = await page.title()
                            citation["title"] = page_title.strip() or citation["title"]
                        except:
                            pass
                        finally:
                            await context.close()

                    # Add/enrich fields
                    citation.update(
                        {
                            "media_type": citation.get(
                                "source_type", "news"
                            ),  # map source_type → media_type
                            "publisher": citation.get("publisher")
                            or urlparse(url).netloc.replace("www.", ""),
                            "access_date": datetime.now(
                                timezone.utc
                            ),  # update to actual access time
                            "jurisdiction": citation.get("jurisdiction") or "Canada",
                            "metadata": {
                                **(citation.get("metadata") or {}),
                                "full_text_scraped": True,
                                "scraped_word_count": len(text.split()),
                                "serper_snippet": (
                                    citation["metadata"].get("serper_snippet")
                                    if citation.get("metadata")
                                    else None
                                ),
                            },
                        }
                    )

                    # Split into chunks
                    paragraphs = [
                        p.strip() for p in text.split("\n\n") if len(p.strip()) > 80
                    ]

                    chunks: List[TextChunk] = [
                        {
                            "textchunk_id": str(uuid.uuid4()),
                            "citation_id": citation["citation_id"],
                            "text": para,
                            "section": f"para_{i+1}",
                            "char_start": sum(len(p) + 2 for p in paragraphs[:i]),
                            "char_end": sum(len(p) + 2 for p in paragraphs[: i + 1]),
                        }
                        for i, para in enumerate(paragraphs)
                    ]

                    collected.append({"citation": citation, "chunks": chunks})
                    print(
                        f"   saved {len(paragraphs)} paragraphs | {citation['title'][:60]}..."
                    )

                except Exception as e:
                    print(f"   error scraping {url}: {e}")
                finally:
                    await asyncio.sleep(delay)

        # Run all news citations concurrently
        tasks = [process_citation(c) for c in news_citations]
        await asyncio.gather(*tasks, return_exceptions=True)

        await browser.close()

    print(f"Scraping complete: {len(collected)} articles enriched")
    return collected


# Convenience sync wrapper
scrape_news = lambda *args, **kwargs: asyncio.run(
    scrape_news_playwright(*args, **kwargs)
)
