from dotenv import load_dotenv
import os
from openai import OpenAI
from pathlib import Path

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

KEYWORDS = os.getenv("KEYWORDS")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
PACKAGE_ROOT = Path(__file__).resolve().parent
PROMPTS = PACKAGE_ROOT / "prompts.yaml"
TASKS_PATH = PACKAGE_ROOT / "serper_tasks.yaml"


def set_package_root(path: Path):
    global PACKAGE_ROOT, PROMPTS, TASKS_PATH
    PACKAGE_ROOT = path
    PROMPTS = PACKAGE_ROOT / "prompts.yaml"
    TASKS_PATH = PACKAGE_ROOT / "serper_tasks.yaml"
