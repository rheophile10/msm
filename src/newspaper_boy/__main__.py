import json
from newspaper_boy.get import scrape_news

if __name__ == "__main__":

    data = scrape_news(
        max_results=200,
        delay=2.0,
    )

    print(f"\nDone. Collected {len(data)} full-text articles.")

    with open("output.jsonl", "w", encoding="utf-8") as f:
        for item in data:
            json.dump(item, f, ensure_ascii=False)
            f.write("\n")
