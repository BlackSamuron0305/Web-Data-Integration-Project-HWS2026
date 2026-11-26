# Step 5: Data fusion

This step turns the linked records into one entry per university. Each group of linked records from
step 4 becomes one entry; a record without a partner becomes an entry of its own. Where the records of
a group disagree, fusion picks which value to keep. We use PyDI, built like the fusion exercise.

## What we did

**Input:** the cleaned sources (step 3, `filtered/`) and the links of the final run of step 4
(`04_identity_resolution/global_matching_and_test/results/correspondences_*_final.csv`).

**Output:** 35,551 universities in `results/universities_fused.csv`, 13,981 of them from at least two
sources (11,225 from two, 2,756 from all three). Only these can hold conflicts.

**Provenance.** Every record keeps its source in its ID (`ror_05njb9z20`), and every fused university
lists its records and sources. PyDI also records which source supplied each value, which let us trace
every error back.

**Trust.** Some strategies prefer one source: ROR 3, Wikidata 2, DEQAR 1. This order is our assumption:
a curation team maintains ROR, volunteers edit Wikidata, and DEQAR relies on reports from quality
assurance agencies.

**Lists and coordinates.** The strategies below unite lists (alternative names, domains, ...) and take
the median of the coordinates. For domains we also compare other list functions (see below).

**Gold standard** (`data/golden_set/fusion/fusion_gold.xml`): 80 universities from at least two
sources, 64 whose sources disagree on a value and 16 at random (`build_gold.py` drew them and wrote
`gold_candidates.csv`: first 50, then 30 more). Like the exercise's `gold.xml` it uses our target schema
(`target.xsd`) and the ROR ID of each university. It holds name, country code, city, founding year and
domains; other accepted names are in `alternativeNames` and also count as correct. The schema has one city
and one founding year, so these have exactly one correct value. The values are kept and checked in
`fusion_gold.csv`, and `gold_to_xml.py` writes the XML from it and validates it. The values were looked
up in external sources, never in ROR, Wikidata or DEQAR (column `sources`), and checked by hand (columns
`checked_by`, `hand_note`); the check corrected six values. After the final links, 78 of the 80 are still in a
group with two or more sources and are evaluated.

**Two halves.** As in the lecture (choose the function on a validation part of the ground truth), the 80
are split at random into two halves of 40 with the same mix of conflict and random draws (column `half`
in `gold_candidates.csv`): on *choose* we pick the function per attribute, on *test* we measure how
accurate that choice is. Each half has 39 evaluated universities, so one value moves an accuracy by .026.

## What we tried

Four strategies built from PyDI's functions, plus one of our own, for the single-valued attributes
(`results/strategies.csv`; it also has the whole gold standard and the conflict and random draws).

**Strict and tolerant comparison.** As in the exercise, we compare names and cities with the gold
standard twice. *Strict*: the fused value is written exactly like an accepted value. *Tolerant*: case,
accents, punctuation and word order do not count, and up to a fifth of the words may differ (PyDI's
`tokenized_match` with threshold 0.8, as in the exercise; letters such as *ł* and *ø* count as *l* and
*o*). Country codes, years and domains are compared the same way in both. The tolerant comparison only
changes what we count as an error, not the fused data; we use it to choose the final strategy.

Accuracy on the *choose* half (strict / tolerant where it differs):

| Strategy | Name | Country | City | Year | Mean |
|---|---|---|---|---|---|
| content-based (longest name and website, earliest year, vote otherwise) | .821 / .974 | .949 | .615 / .667 | .564 | .737 / .788 |
| voting | .872 / .974 | .949 | .615 / .667 | **.692** | .782 / .821 |
| trust, Wikidata first | .897 / .974 | .949 | .615 / .667 | .641 | .776 / .808 |
| trust, ROR first | .846 / **1.000** | **1.000** | .667 / .692 | .667 | .795 / .840 |
| **voting, ties broken by trust (ours)** | .846 / **1.000** | **1.000** | **.692** / **.718** | **.692** | **.808** / **.853** |

The tolerant comparison raises names the most: most strict misses are the same name written differently
(*Mingdao* for *MingDao*, a hyphen for a dash, *Wroclaw* for *Wrocław*). One accepted match is generous:
*University College of Tourism and Ecology* passes because the gold standard also accepts *College of
Tourism and Ecology*, five of its six words.

- **Voting** cannot decide when two records disagree, and 11,225 of the 13,981 groups have only two.
- **Trust with ROR first:** every group contains a ROR record, so it ignores the other sources
  wherever ROR has a value.
- **Our function** takes the value most records agree on and breaks ties by trust.

**Domains** (a list; `results/list_functions.csv`). A fused list counts as correct when it holds an
accepted domain and nothing else (a subdomain of an accepted domain may come along). The earlier check,
"at least one accepted domain", let union score 1.0 every time, because union keeps everything.

| Function for domains | Choose | Test | Domains per university | Universities left without domain |
|---|---|---|---|---|
| union | .897 | .897 | 1.16 | 104 |
| in at least 2 sources (`intersection_k_sources`, k = 2) | .846 | .872 | 0.90 | 1,440 |
| **trust, ROR first** | **.949** | **.949** | 1.00 | 104 |
| trust, Wikidata first | .923 | **.949** | 1.03 | 104 |

- **Union** keeps the wrong domain whenever one source has one (*aeht.eu* for WSHiG Poznań).
- **In at least 2 sources** drops every domain the sources do not share, so 1,440 universities lose
  their domain altogether, and it is the least accurate.
- **Trust** takes one source's list. The errors left with ROR first are mostly ROR subdomains
  (*eng.mdu.edu.tw*, *eng.bspu.ru*) where the other source has the main domain.

Alternative names, acronyms and coordinates are not in the gold standard, so we cannot score functions
for them; they keep union and the median.

**Final strategy** ("best per attribute" in `strategies.csv`): for each attribute the function that is
most accurate on the *choose* half (tolerant comparison), the first listed on a tie: trust with ROR first
for names, country codes and domains, our function for cities, voting for founding years; everything else
uses trust with ROR first. On the *test* half:

| | Name | Country | City | Year | Domains | Mean of the four single-valued |
|---|---|---|---|---|---|---|
| strict | .897 | .974 | .769 | .763 | .949 | .851 |
| tolerant | .949 | .974 | .821 | .763 | .949 | **.877** |

The test half is a fair estimate because it played no part in the choice. It also shows how little 39
universities can tell apart: on the test half our function alone (.896) would have done slightly better,
because voting, chosen for founding years over our function only by the order of the list (both .692 on
the *choose* half), is three values worse there.

## What worked and what did not

- **Worked:** fusion fills gaps (`results/density.csv`: share of filled values per attribute; the row
  *all attributes* is the mean over the 21 attributes of the target schema, an attribute a source lacks
  counting as empty). Compared with ROR, the largest source:

  | | Universities | Density |
  |---|---|---|
  | ROR | 25,919 | 0.581 |
  | fused, universities with a ROR record | 25,919 | 0.639 |
  | fused, all | 35,551 | 0.564 |

  For ROR's universities density rises, mostly with what ROR lacks (student numbers and memberships from
  Wikidata, quality assurance data from DEQAR). Over the whole fused table it is lower than ROR's, because
  the 9,632 universities fusion adds (37% more than ROR) come from Wikidata or DEQAR alone and have
  sparser records.
- **Errors left** (`results/fusion_errors.jsonl`, test half, tolerant comparison): 21 values are wrong:
  9 founding years, 7 cities, 2 names, 2 domain lists, 1 country code. Most wrong cities are the same place
  at another level or under another name (*Pok Fu Lam* for Hong Kong, *Nazrēt* for Adama, *Mariupol* for
  Kyiv, where the university moved in 2022) or in a spelling the tolerant comparison does not catch
  (*Bireun*/*Bireuen*, *Ansan-si*/*Ansan*). In four of the wrong years voting took Wikidata's year over
  ROR's correct one, which our function would have avoided; three times both sources agree on a year the
  gold standard does not accept (Dagestan State Pedagogical University 1917, Universitas Hasyim Asy'ari
  2013, Tokyo Future University 2006). The country code (SJ for NO) and the wrong domains come from ROR.
- **Inherited errors:** a wrong link from step 4 puts two institutions into one entry, and values of
  one fill gaps of the other (*Télécom Lille* gets the website of *Telecom Nancy*). The gold standard
  catches one: the ROR record of *Sendai Seiyo Gakuin College* (a junior college, 2009) is linked to the
  Wikidata item of *Sendai Seiyo Gakuin University* (opened 2024), and voting takes 2024. Likewise the
  Wikidata item linked to *Kazan Law Institute* (1974) gives 1931, which the lookup traced to a
  different institute of the same name.
- **Consistency:** country codes almost always agree within a group; names and cities often do not, so
  the choice matters. Websites agree least, partly because we compare them as text
  (`https://www.x.edu` vs `http://x.edu/en`); normalising them would be the next step.

## Files and how to run

| File | What it is |
|---|---|
| `fusion.py` | groups the linked records, compares the strategies on the gold standard, fuses everything with the final strategy |
| `build_gold.py` | draws the 80 universities for the gold standard and splits them into two halves |
| `gold_to_xml.py` | writes `fusion_gold.csv` as `fusion_gold.xml` in the target schema and validates it |
| `gold_candidates.csv` | the 80 drawn, with the values of each source, why each was drawn and its half |
| `results/universities_fused.csv` | the fused dataset |
| `results/strategies.csv` | accuracy of each strategy on the gold standard |
| `results/list_functions.csv` | accuracy of each list function for domains |
| `results/density.csv` | share of filled values per attribute and over all attributes, per source and after fusion |
| `results/consistency.csv`, `group_sizes.csv` | how often the sources agree; universities by number of sources |
| `results/fusion_errors.jsonl` | the wrong values left, for the error analysis |

```
python gold_to_xml.py   # only after fusion_gold.csv changed
python fusion.py
```
