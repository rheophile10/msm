from pathlib import Path
from typing import List
import yaml
from newspaper_boy import TASKS_PATH

from newspaper_boy.types import SerperScrapeTask


def load_serper_scrape_tasks(path: Path = TASKS_PATH) -> List[SerperScrapeTask]:
    """
    Load a list of SerperScrapeTask objects from a YAML file.

    Expected YAML structure:

    tasks:
        - raw_string: "..."
        csv_or_list: "..."
        ...
    """
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if isinstance(data, dict) and "tasks" in data:
        tasks_raw = data["tasks"]
    else:
        tasks_raw = data

    if not isinstance(tasks_raw, list):
        raise ValueError(
            "YAML must contain a list of tasks (under 'tasks' or as the root list)."
        )

    tasks: List[SerperScrapeTask] = tasks_raw  # type: ignore[assignment]
    return tasks
