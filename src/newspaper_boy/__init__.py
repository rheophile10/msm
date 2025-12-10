from dotenv import load_dotenv
import os

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

KEYWORDS = os.getenv("KEYWORDS")
