import json
from newspaper_boy.playwright_scrape import scrape_news
from newspaper_boy.serper import serper_search, total_serper_search_results
from newspaper_boy.types import SerperScrapeTask
from newspaper_boy.llm import filter_firearms_policy_citations
from newspaper_boy.io import load_serper_scrape_tasks
from datetime import datetime, date

if __name__ == "__main__":

    tasks = load_serper_scrape_tasks()
    citations = total_serper_search_results(**tasks[0])
    print(f"Total citations from serper_search: {len(citations)}")

    # citations = []
    # tasks = load_serper_scrape_tasks()
    # for task in tasks:
    #     serper_search_results = serper_search(**task)

    #     filtered_citations = filter_firearms_policy_citations(
    #         serper_search_results,
    #         model="gpt-4.1-mini",
    #     )

    #     citations.extend(filtered_citations)

    #     # data = scrape_news(
    #     #     filtered_citations,
    #     #     concurrency=4,
    #     # )

    # def json_serial(obj):
    #     if isinstance(obj, (datetime, date)):
    #         return obj.isoformat()
    #     raise TypeError(f"Type {type(obj)} not serializable")

    # with open("scraped_citations.json", "w", encoding="utf-8") as f:
    #     json.dump(citations, f, ensure_ascii=False, indent=2, default=json_serial)
