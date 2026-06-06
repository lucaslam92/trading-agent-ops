import os
from dotenv import load_dotenv

load_dotenv()

ADAPTER = os.getenv("ADAPTER", "mock")
TICK_INTERVAL = float(os.getenv("TICK_INTERVAL", "2.2"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "market.db")
