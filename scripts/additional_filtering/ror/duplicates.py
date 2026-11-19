"""ROR: candidate duplicate pairs within ROR.  Usage: python duplicates.py
Writes duplicate_check.csv (see ../common.py: find_duplicates, write_duplicate_check)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import find_duplicates, write_duplicate_check

if __name__ == "__main__":
    write_duplicate_check(HERE, find_duplicates("ror", HERE))
