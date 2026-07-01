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
