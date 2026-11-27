"""Builds the agenda slides' BPMN pictures from the report's process model.

The deck uses the report's BPMN model (submission/final-report/figures/flow.drawio) as its agenda.
agenda.drawio gets one page per state of the talk:

  0 Overview            the model as in the report (slide "Our journey")
  1 First pass          select, map, match and analyse the raw data
  2 Back to the data    the step back: clean the data
  3 Matching            map the cleaned files again and match them
  4 Fusion              fuse the values into 35,551 universities

Steps of earlier sections keep their colours, the current section is navy with an orange border,
later sections are faded. Each page is exported to agenda_<n>.png at the scale of the slide picture.

Run from the repo root:  python submission/final-presentation/scripts/agenda_bpmn.py
Writes to submission/final-presentation/figures. Needs the draw.io desktop app for the PNG export
(set DRAWIO to its executable if it is not in the default place).
"""
import copy
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SRC = ROOT / "submission" / "final-report" / "figures" / "flow.drawio"
OUT = HERE.parent / "figures"

NAVY, ORANGE = "#003056", "#D96C1E"
FADE = {"opacity": "28", "textOpacity": "28"}
TASKS = {f"t{i}" for i in range(1, 9)}

# section of each cell of flow.drawio (the lanes stay as they are)
SECTION = {
    "s1": 1, "f1": 1, "t1": 1, "f2": 1, "t2": 1, "f3": 1, "t3": 1, "f4": 1, "t4": 1,
    "f7": 2, "t5": 2,
    "f8": 3, "t6": 3, "f9": 3, "t7": 3,
    "f10": 4, "t8": 4, "f11": 4, "e1": 4, "a1": 4, "d1": 4,
}
PAGES = ["Overview", "First pass", "Back to the data", "Matching", "Fusion"]


def parse(style):
    return dict(part.partition("=")[::2] for part in style.split(";") if part)


def dump(style):
    return "".join(f"{k}={v};" if v else f"{k};" for k, v in style.items())


def restyle(cell, section, current):
    style = parse(cell.get("style", ""))
    if section > current:
        style.update(FADE)
    elif section == current:
        if cell.get("id") in TASKS:
            style.update(fillColor=NAVY, strokeColor=ORANGE, strokeWidth="3", fontColor="#FFFFFF")
        elif cell.get("id") == "f7":  # the step back to the data
            style.update(strokeColor=ORANGE, fontColor=ORANGE, strokeWidth="3")
        elif cell.get("id") == "d1":  # the result
            style.update(strokeColor=ORANGE, strokeWidth="2.5", fontStyle="1")
    cell.set("style", dump(style))


def build():
    tree = ET.parse(SRC)
    mxfile = tree.getroot()
    base = mxfile.find("diagram")
    mxfile.remove(base)
    for current, name in enumerate(PAGES):
        page = copy.deepcopy(base)
        page.set("id", f"agenda-{current}")
        page.set("name", f"{current} {name}")
        if current:
            for cell in page.iter("mxCell"):
                if cell.get("id") in SECTION:
                    restyle(cell, SECTION[cell.get("id")], current)
        mxfile.append(page)
    ET.indent(tree, space="  ")
    target = OUT / "agenda.drawio"
    tree.write(target, encoding="utf-8")
    return target


def drawio():
    for cand in (os.environ.get("DRAWIO"), shutil.which("draw.io"), shutil.which("drawio"),
                 Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "draw.io" / "draw.io.exe",
                 Path(os.environ.get("PROGRAMFILES", "")) / "draw.io" / "draw.io.exe",
                 "/Applications/draw.io.app/Contents/MacOS/draw.io"):
        if cand and Path(cand).is_file():
            return str(cand)
    raise SystemExit("draw.io not found: set DRAWIO to the draw.io executable")


def export(source):
    exe = drawio()
    for index in range(len(PAGES)):
        png = OUT / f"agenda_{index}.png"
        # scale 5 matches the slide picture (about 320 dpi at 10.3 inches wide)
        subprocess.run([exe, "-x", "-f", "png", "-s", "5", "-b", "1", "--theme", "light",
                        "-p", str(index + 1), "-o", str(png), str(source)], check=True, capture_output=True)
        print("wrote", png.relative_to(ROOT))


if __name__ == "__main__":
    export(build())
