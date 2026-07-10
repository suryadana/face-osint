"""
Face OSINT - Instagram Face Search Tool
Configuration
"""
import os, json, inspect

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CONFIG_DIR, "data")
RESULTS_DIR = os.path.join(CONFIG_DIR, "results")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

COOKIE_STRING = ''

MODEL_NAME = "buffalo_l"
SIM_THRESHOLD = 0.35
PLAYWRIGHT_TIMEOUT = 15000
PAGE_WAIT = 1500
WORKERS = 3
MAX_DEPTH = 3

# --- Rate-limit hardening ---
RATE_PER_MIN = 20                 # global read pace (requests/min); 0 disables
DELAY_RANGE = (1.0, 3.0)          # jittered inter-action delay (seconds)
MAX_REQUESTS = 800                # per-run request budget; None disables
MAX_EXPANSIONS_PER_LAYER = 15     # cap accounts expanded per BFS layer; None disables
BACKOFF_CAP = 300                 # max backoff seconds (was hardcoded 30)

# --- Post-image aggregation ---
POST_SAMPLE_N = 3      # recent posts sampled per checked account (0 = profile pic only)
CONSENSUS_MIN = 2      # distinct images >= SIM_THRESHOLD required to auto-stop (FOUND)
