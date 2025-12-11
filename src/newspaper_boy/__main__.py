import json
from newspaper_boy.playwright_scrape import scrape_news
from newspaper_boy.serper import serper_search
from newspaper_boy.types import SerperScrapeTask
from newspaper_boy.llm import filter_firearms_policy_citations
from newspaper_boy.io import load_serper_scrape_tasks

if __name__ == "__main__":

    tasks = load_serper_scrape_tasks()
    for task in tasks:
        print(f"Serper Task: {task['raw_string']} -> {task['csv_or_list']}")
        serper_search_results = serper_search(**task)

        filtered_citations = filter_firearms_policy_citations(
            serper_search_results,
            model="gpt-4.1-mini",
        )

        data = scrape_news(
            filtered_citations,
            concurrency=4,
        )
