"""Wikidata: writes the filtered and deduplicated copies from hand_check.csv and duplicate_check.csv.
Run with: python apply.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import apply

if __name__ == "__main__":
    apply("wikidata", HERE)
