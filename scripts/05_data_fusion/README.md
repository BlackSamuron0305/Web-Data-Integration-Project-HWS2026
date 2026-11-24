# Step 5: Data fusion

This step turns the linked records into one entry per university. Each group of linked records from
step 4 becomes one entry; a record without a partner becomes an entry of its own. Where the records of
a group disagree, fusion picks which value to keep. We use PyDI, built like the fusion exercise.

## What we did

**Input:** the cleaned sources (step 3, `filtered/`) and the final round-8 links (step 4).

**Output:** 35,996 universities in `results/universities_fused.csv`, 13,642 of them from at least two
sources. Only these can hold conflicts.

**Provenance.** Every record keeps its source in its ID (`ror_05njb9z20`), and every fused university
lists its records and sources. PyDI also records which source supplied each value, which let us trace
every error back.

**Trust.** Some strategies prefer one source: ROR 3, Wikidata 2, DEQAR 1. This order is our assumption:
a curation team maintains ROR, volunteers edit Wikidata, and DEQAR relies on reports from quality
assurance agencies.

**Lists and coordinates.** All strategies unite lists (alternative names, domains, ...) and take the
median of the coordinates.

**Gold standard.** To measure which values fusion should pick, we built a gold standard of 869
universities from at least two sources (`data/golden_set/fusion/`): 39 well-known universities, 384
with conflicting source values and 446 at random (`build_gold.py` draws them). It holds one or more
accepted values for name, country code, city, founding year and domains. **The accepted values were
proposed by AI agents after looking at the source records and have not been checked by a person.**
Rows marked `low` confidence are not used.

## What we tried

Four strategies built from PyDI's functions, plus one of our own, for the single-valued attributes:

| Strategy | Name | Country | City | Year | Mean |
|---|---|---|---|---|---|
| content-based (longest name and website, earliest year, vote otherwise) | .917 | .977 | .891 | .972 | .939 |
| voting | .947 | .977 | .891 | .965 | .945 |
| trust, Wikidata first | .938 | .976 | .867 | .963 | .936 |
| trust, ROR first | .977 | .994 | **.988** | **.979** | .985 |
| **voting, ties broken by trust (ours)** | **.978** | **.997** | **.988** | **.979** | **.986** |

- **Voting** cannot decide when two records disagree, and 10,992 of the 13,642 groups have only two.
- **Trust with ROR first** is the best of PyDI's strategies, but since every group contains a ROR
  record, it ignores the other sources wherever ROR has a value.
- **Our function** takes the value most records agree on and breaks ties by trust. It differs from
  "ROR first" only where Wikidata and DEQAR agree against ROR: that changes 284 names and five country
  codes, and on the gold standard it fixes one name and two country codes and breaks nothing.

**Final strategy:** our function for name and country code (the country name follows the code), trust
with ROR first for everything else. Our function would also change 72 cities and 107 founding years,
but there both are equally accurate, so we kept the simpler one.

## What worked and what did not

- **Worked:** fusion fills gaps. For universities that ROR also describes, the share of filled
  attributes rises from 0.581 to 0.638, mostly with what ROR lacks (student numbers and memberships from
  Wikidata, quality assurance data from DEQAR). Founding years go from 95.3% filled in ROR to 99.0%.
  Fusion adds 10,077 universities to ROR (39% more), all from Wikidata or DEQAR alone.
- **Errors left:** 51 of 4,341 gold values are wrong: 19 names, 3 country codes, 10 cities, 18 founding
  years, 1 domain. Mostly ROR gives a local-language name where another source has the English one, a
  system or campus name (*University of the West Indies System*), or another city (Seoul where
  Wikidata says Yongin). For 11 of the 18 wrong years no source has the right one.
- **Did not help:** changing the source order. Trust with Wikidata first fixes 22 of the 34 errors
  where another source was right, but breaks 195 values that are right now. No vote helps either: in
  none of those 34 cases do two sources agree on the right value.
- **Inherited errors:** a wrong link from step 4 puts two institutions into one entry, and values of
  one fill gaps of the other (*Télécom Lille* gets the website of *Telecom Nancy*).
- **Consistency:** country codes almost always agree within a group; names and cities often do not, so
  the choice matters. Websites agree least, partly because we compare them as text
  (`https://www.x.edu` vs `http://x.edu/en`); normalising them would be the next step.

An AI check of every fused university (`results/ai_check_fused.csv`, and `ai_check_fused_before_cutoff.csv`
for the run without the final cut-off) found that most remaining errors are non-universities, almost
all in entries from a single source, and that the cut-off clearly reduced entries that merge two
institutions. These are AI verdicts, not checked by a person.

## Files and how to run

| File | What it is |
|---|---|
| `fusion.py` | groups the linked records, compares the strategies on the gold standard, fuses everything with the final strategy |
| `build_gold.py` | draws the universities for the gold standard |
| `results/universities_fused.csv` | the fused dataset |
| `results/strategies.csv` | accuracy of each strategy on the gold standard |
| `results/density.csv`, `consistency.csv`, `group_sizes.csv` | how complete and consistent the data is |
| `results/fusion_errors.jsonl` | the wrong values left, for the error analysis |
| `results/ai_check_fused*.csv` | the AI check of every fused university |

```
python fusion.py
```
