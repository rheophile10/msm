import json
from newspaper_boy.playwright_scrape import scrape_news
from newspaper_boy.serper import serper_search
from newspaper_boy.types import SerperScrapeTask

if __name__ == "__main__":

    example_task: SerperScrapeTask = {
        "raw_string": "Canada",
        "csv_or_list": "gun buyback,assault-style,illegal handgun",
        "search_type": "news",
        "country": "ca",
        "location": "Canada",
        "language": "en",
        "date_range": "past_day",
        "max_page_count": 2,
    }

    serper_search_results = serper_search(**example_task)

    data = scrape_news(
        serper_search_results,
        concurrency=4,
    )

    print(f"\nDone. Collected {len(data)} full-text articles.")

    with open("output.jsonl", "w", encoding="utf-8") as f:
        for item in data:
            json.dump(item, f, ensure_ascii=False, default=str)
            f.write("\n")
