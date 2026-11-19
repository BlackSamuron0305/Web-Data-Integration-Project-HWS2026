"""DEQAR: remove every row marked university = n in hand_check.csv.  Usage: python apply.py
Writes *_filtered.csv and *_Mapping_filtered.xml next to this script."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import apply

if __name__ == "__main__":
    apply("deqar", HERE)
