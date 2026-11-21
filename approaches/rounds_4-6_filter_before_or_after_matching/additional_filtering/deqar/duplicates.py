"""DEQAR: finds candidate duplicate pairs inside DEQAR and writes duplicate_check.csv.
Run with: python duplicates.py"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import find_duplicates, write_duplicate_check

if __name__ == "__main__":
    write_duplicate_check(HERE, find_duplicates("deqar", HERE))
