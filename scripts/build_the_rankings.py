"""Build the Times Higher Education World University Rankings 2026 file, one row per university.

Source:  https://www.timeshighereducation.com/world-university-rankings/2026/world-ranking
         (the table data the page loads, published October 2025)
Scope:   all 3,118 listed universities: 2,191 ranked and 927 "reporters" (they submitted data but
         did not get a rank, so they have student figures and no scores).
Output:  data/the_rankings_2026.csv  (UTF-8, list values separated by " | ")

Note:    THE's terms allow personal use and ask for the source to be cited. The data must not be
         republished, so the output file should not be put into a public repository.

Changes to the downloaded data
  - ranking_status added: "ranked" or "reporter"; rank and scores are empty for reporters
  - rank: "=" (tie marker) removed; bands such as "401-500" and "1501+" are kept as text
  - overall_score: exact for the top 200, a range such as "46.2-49.8" below that (kept as text)
  - students "22,005" -> 22005; international students "43%" -> 43;
    female : male ratio "52 : 48" -> female_students_pct 52
  - subjects split into a list (several subject names contain commas themselves)
  - internal fields (account type, sort keys, advertising links, search aliases) dropped

Run:  python scripts/build_the_rankings.py [path/to/downloaded.json]
      Without a path the file is downloaded to the system temp folder.
"""
import csv
import json
import re
import sys
import tempfile
from pathlib import Path

import requests

DOWNLOAD_URL = "https://www.timeshighereducation.com/json/ranking_tables/world_university_rankings/2026"
DOWNLOAD_NAME = "the_world_university_rankings_2026.json"
SITE = "https://www.timeshighereducation.com"
OUT = Path(__file__).resolve().parent.parent / "data" / "the_rankings_2026.csv"
SEP = " | "
PILLARS = ["teaching", "research", "citations", "industry_income", "international_outlook"]


def download():
    path = Path(tempfile.gettempdir()) / DOWNLOAD_NAME
    if not path.exists():
        print("downloading", DOWNLOAD_URL)
        r = requests.get(DOWNLOAD_URL, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def clean(value):
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text.replace("|", "/").replace("–", "-")).strip()


def split_subjects(text):
    """Subjects are separated by "," without a space; a ", " with a space belongs to one subject name."""
    return sorted({clean(s) for s in re.split(r",(?! )", text or "") if s.strip()})


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else download()
    content = json.loads(source.read_text(encoding="utf-8"))

    columns = (["the_id", "name", "country", "ranking_status", "rank", "overall_score"]
               + [f"{p}_{kind}" for p in PILLARS for kind in ("score", "rank")]
               + ["students", "students_per_staff", "international_students_pct", "female_students_pct",
                  "subjects", "profile_url"])
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in sorted(content["data"], key=lambda r: int(r["rank_order"])):
            ranked = r["rank"] != "Reporter"
            row = {
                "the_id": r["nid"],
                "name": clean(r["name"]),
                "country": clean(r["location"]),
                "ranking_status": "ranked" if ranked else "reporter",
                "rank": clean(r["rank"]).lstrip("=") if ranked else "",
                "overall_score": clean(r["scores_overall"]) if ranked else "",
                "students": clean(r["stats_number_students"]).replace(",", ""),
                "students_per_staff": clean(r["stats_student_staff_ratio"]),
                "international_students_pct": clean(r["stats_pc_intl_students"]).rstrip("%"),
                "female_students_pct": clean(r["stats_female_male_ratio"]).split(" : ")[0],
                "subjects": SEP.join(split_subjects(r.get("subjects_offered"))),
                "profile_url": SITE + r["url"],
            }
            for p in PILLARS:
                row[f"{p}_score"] = clean(r[f"scores_{p}"]) if ranked else ""
                row[f"{p}_rank"] = clean(r[f"scores_{p}_rank"]) if ranked else ""
            writer.writerow(row)
    print(f"done: {len(content['data'])} rows written to {OUT}")


if __name__ == "__main__":
    main()
