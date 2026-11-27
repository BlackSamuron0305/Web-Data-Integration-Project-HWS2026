# Step 5: Data fusion

This step turns the linked records into one entry per university. Each group of linked records from
step 4 becomes one entry; a record without a partner becomes an entry of its own. Where the records of
a group disagree, fusion picks which value to keep. We use PyDI, built like the fusion exercise.

## What we did

**Input:** the cleaned sources (step 3, `filtered/`) and the links of the final run of step 4
(`04_identity_resolution/global_matching_and_test/results/correspondences_*_final.csv`).

**Output:** 35,551 universities, 13,981 of them from at least two sources (11,225 from two, 2,756 from
all three). Only these can hold conflicts. The attributes are the 21 of the target schema from step 3:
fusion decides which value each one gets, not which attributes there are. The dataset is written twice,
with the same universities and values:

- `results/universities_fused.csv`, for the analyses, with the records and sources of each university
- `results/universities_fused.xml`, in the target schema (`target.xsd`) and validated against it. The
  schema has no place for the records and sources, so the XML has only the ID and the 21 attributes.
  The ID is the ROR ID wherever there is a ROR record, as in the gold standard, so the two match by ID.
  A university without one has a single record and keeps its ID. The CSV's `_id` is PyDI's choice, the
  DEQAR ID in all 4,238 groups with a DEQAR record.

**Provenance.** Every record keeps its source in its ID (`ror_05njb9z20`), and every fused university
lists its records and sources. PyDI also records which source supplied each value, which let us trace
every error back.

**Trust.** Some strategies prefer one source: ROR 3, Wikidata 2, DEQAR 1. This order is our assumption:
a curation team maintains ROR, volunteers edit Wikidata, and DEQAR relies on reports from quality
assurance agencies.

**Lists and coordinates.** The strategies below unite lists (alternative names, domains, ...) and take
the median of the coordinates. For domains and coordinates we also compare other functions (see below).

**Gold standard** (`data/golden_set/fusion/fusion_gold.xml`): 80 universities from at least two
sources, 64 whose sources disagree on a value and 16 at random (`build_gold.py` drew them and wrote
`gold_candidates.csv`: first 50, then 30 more). Like the exercise's `gold.xml` it uses our target schema
(`target.xsd`) and the ROR ID of each university. It holds name, country code, city, founding year and
domains; other accepted names are in `alternativeNames` and also count as correct. The schema has one city
and one founding year, so these have exactly one correct value. The values are kept and checked in
`fusion_gold.csv`, and `gold_to_xml.py` writes the XML from it and validates it. The values were looked
up in external sources, never in ROR, Wikidata or DEQAR (column `sources`), and checked by hand (columns
`checked_by`, `hand_note`); the check corrected six values. After the final links, 78 of the 80 are still in a
group with two or more sources and are evaluated. The gold standard has no website of its own: a fused
website counts as correct when its host is one of the accepted domains.

**Coordinates in the gold standard** (columns `latitude` to `coordinates_note` of `fusion_gold.csv`). A
geocoder searched each university by its names in an open map, and a result was kept only if it is a
university or college (three times a library or bus stop named after the campus) whose name resembles a
gold name and whose address contains the gold city. 69 of the 80 have a point, the other 11 were not found
or only as another institution. Each kept point was then checked by hand (`coordinates_source` links it,
`coordinates_checked_by` names who checked it). The map and Wikidata are not independent: map objects often
link to a Wikidata item, and points are sometimes copied between the two.

**Two halves.** As in the lecture (choose the function on a validation part of the ground truth), the 80
are split at random into two halves of 40 with the same mix of conflict and random draws (column `half`
in `gold_candidates.csv`): on *choose* we pick the function per attribute, on *test* we measure how
accurate that choice is. Each half has 39 evaluated universities, so one value moves an accuracy by 0.026.

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
| content-based (longest name and website, earliest year, vote otherwise) | 0.821 / 0.974 | 0.949 | 0.615 / 0.667 | 0.564 | 0.737 / 0.788 |
| voting | 0.872 / 0.974 | 0.949 | 0.615 / 0.667 | **0.692** | 0.782 / 0.821 |
| trust, Wikidata first | 0.897 / 0.974 | 0.949 | 0.615 / 0.667 | 0.641 | 0.776 / 0.808 |
| trust, ROR first | 0.846 / **1.000** | **1.000** | 0.667 / 0.692 | 0.667 | 0.795 / 0.840 |
| **voting, ties broken by trust (ours)** | 0.846 / **1.000** | **1.000** | **0.692** / **0.718** | **0.692** | **0.808** / **0.853** |

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
| union | 0.897 | 0.897 | 1.16 | 104 |
| in at least 2 sources (`intersection_k_sources`, k = 2) | 0.846 | 0.872 | 0.90 | 1,440 |
| **trust, ROR first** | **0.949** | **0.949** | 1.00 | 104 |
| trust, Wikidata first | 0.923 | **0.949** | 1.03 | 104 |

- **Union** keeps the wrong domain whenever one source has one (*aeht.eu* for WSHiG Poznań).
- **In at least 2 sources** drops every domain the sources do not share, so 1,440 universities lose
  their domain altogether, and it is the least accurate.
- **Trust** takes one source's list. The errors left with ROR first are mostly ROR subdomains
  (*eng.mdu.edu.tw*, *eng.bspu.ru*) where the other source has the main domain.

**Websites** (column `website` of `strategies.csv`). Compared like domains: a website is right when its
host (without scheme, `www.` and path) is an accepted domain, so the English site *eng.mdu.edu.tw* counts
as wrong. Our function votes on the hosts. It is the same in both comparisons:

| Strategy | Choose | Test |
|---|---|---|
| content-based (longest website) | 0.897 | 0.872 |
| voting | 0.923 | 0.923 |
| trust, Wikidata first | 0.923 | 0.923 |
| **trust, ROR first** | **0.949** | **0.949** |
| voting, ties broken by trust (ours) | **0.949** | **0.949** |

Trust with ROR first is listed before our function and is kept, so the fused websites are the same as
before. The two errors left on the test half are the ROR subdomains that also make two domain lists wrong
(*eng.mdu.edu.tw*, *eng.bspu.ru*).

**Coordinates** (`results/coordinate_functions.csv`). Only ROR and Wikidata have coordinates, so the median
of a group is the midpoint of two points. A fused point is right within 1 km of the gold point (strict:
the campus) or within 5 km (tolerant: the same part of the city), limits fixed before the evaluation.
33 universities of the *choose* half and 34 of the *test* half have a gold point.

| Function | Choose, 1 km | Choose, 5 km | Test, 1 km | Test, 5 km | Median distance, test |
|---|---|---|---|---|---|
| median | 0.273 | 0.758 | 0.353 | 0.794 | 1.52 km |
| trust, ROR first | 0.091 | 0.697 | 0.265 | 0.765 | 2.17 km |
| **trust, Wikidata first** | **0.606** | **0.818** | **0.765** | **0.912** | **0.14 km** |

**Sensitivity.** Does the result depend on the two limits? The same shares for stricter and looser limits
(choose / test, the choice itself stays at 5 km):

| Within | median | trust, ROR first | trust, Wikidata first |
|---|---|---|---|
| 100 m | 0.000 / 0.000 | 0.000 / 0.000 | **0.152 / 0.382** |
| 500 m | 0.030 / 0.176 | 0.000 / 0.147 | **0.545 / 0.735** |
| 1 km | 0.273 / 0.353 | 0.091 / 0.265 | **0.606 / 0.765** |
| 5 km | 0.758 / 0.794 | 0.697 / 0.765 | **0.818 / 0.912** |
| 10 km | **0.879** / 0.882 | 0.818 / 0.882 | **0.879 / 0.941** |
| median distance | 1.75 / 1.52 km | 3.30 / 2.17 km | **0.33 / 0.14 km** |

Wikidata first is best at every limit on both halves (tied with the median at 10 km on the *choose* half).
Below 500 m ROR and the median almost never hit, as expected from city points. At 100 m the gold point
itself (a campus building found in a map) limits what any source can reach.

ROR places a university at its city: in 86% of the 3,228 cities with two or more ROR universities they all
share one point (all 166 in Tokyo). Wikidata mostly has the campus, so its point beats both ROR's and the
midpoint, which mixes the two. Fusion now takes Wikidata's point where it has one, which moves about 10,300
fused points. One caution: the map the gold points come from is not independent of Wikidata (see above),
so the lead of Wikidata may be overstated.

Alternative names and acronyms are not in the gold standard, so we cannot score functions for them. They
keep union.

**Final strategy** ("best per attribute" in `strategies.csv`): for each attribute the function that is
most accurate on the *choose* half (tolerant comparison), the first listed on a tie: trust with ROR first
for names, country codes, domains and websites, our function for cities, voting for founding years and
trust with Wikidata first for coordinates. Everything else uses trust with ROR first. On the *test* half
(coordinates: see above):

| | Name | Country | City | Year | Domains | Website | Mean of the four single-valued |
|---|---|---|---|---|---|---|---|
| strict | 0.897 | 0.974 | 0.769 | 0.763 | 0.949 | 0.949 | 0.851 |
| tolerant | 0.949 | 0.974 | 0.821 | 0.763 | 0.949 | 0.949 | **0.877** |

The test half is a fair estimate because it played no part in the choice. It also shows how little 39
universities can tell apart: on the test half our function alone (0.896) would have done slightly better,
because voting, chosen for founding years over our function only by the order of the list (both 0.692 on
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
- **Errors left** (`results/fusion_errors.csv`, test half, tolerant comparison): 21 values are wrong:
  9 founding years, 7 cities, 2 names, 2 domain lists, 1 country code. Most wrong cities are the same place
  at another level or under another name (*Pok Fu Lam* for Hong Kong, *Nazrēt* for Adama, *Mariupol* for
  Kyiv, where the university moved in 2022) or in a spelling the tolerant comparison does not catch
  (*Bireun*/*Bireuen*, *Ansan-si*/*Ansan*). In four of the wrong years voting took Wikidata's year over
  ROR's correct one, which our function would have avoided; three times both sources agree on a year the
  gold standard does not accept (Dagestan State Pedagogical University 1917, Universitas Hasyim Asy'ari
  2013, Tokyo Future University 2006). The country code (SJ for NO) and the wrong domains come from ROR.
  The file also lists the two wrong websites (see *Websites*).
- **Inherited errors:** a wrong link from step 4 puts two institutions into one entry, and values of
  one fill gaps of the other (*Télécom Lille* gets the website of *Telecom Nancy*). The gold standard
  catches one: the ROR record of *Sendai Seiyo Gakuin College* (a junior college, 2009) is linked to the
  Wikidata item of *Sendai Seiyo Gakuin University* (opened 2024), and voting takes 2024. Likewise the
  Wikidata item linked to *Kazan Law Institute* (1974) gives 1931, which the lookup traced to a
  different institute of the same name.
- **Consistency:** country codes almost always agree within a group; names and cities often do not, so
  the choice matters. Websites agree least, partly because we compare them as text
  (`https://www.x.edu` vs `http://x.edu/en`); normalising them would be the next step.

## The fused dataset, attribute by attribute

35,551 universities: 25,919 with a ROR record and 9,632 from Wikidata or DEQAR alone. 13,981 combine two
or three sources, and only these can hold conflicts between sources. The dataset is written as CSV, with
the records (`_fusion_sources`) and sources (`sources`) of each university, and as XML in the target
schema, where the ID is the ROR ID wherever there is a ROR record.

The source columns give the share of that source's records with a value (Wikidata 19,605, ROR 25,919,
DEQAR 6,764 records), *Fused* the share of the 35,551 (`results/density.csv`, – : the source has no such
attribute). *Choose → test* is the accuracy on the two halves of the gold standard, compared tolerantly.

| Attribute | Wikidata | ROR | DEQAR | Fused | Conflict resolution | Why |
|---|---|---|---|---|---|---|
| name | 100% | 100% | 100% | 100% | trust, ROR first | 1.0 → 0.949. ROR curates its names, and voting cannot decide between two records |
| alternativeNames | 57% | 72% | 66% | 68% | union | not in the gold standard. Every true alias helps, and there is no single right one |
| acronyms | 14% | 57% | – | 45% | union | as alternativeNames |
| countryCode | 96% | 100% | 99% | 98% | trust, ROR first | 1.0 → 0.974. The codes agree in 99.5% of the groups |
| country | 97% | 100% | 99% | 98% | trust, ROR first | not scored. It comes from the same record as the code, so the two always belong together |
| region | – | 99.5% | – | 73% | the only value | one source, no conflict |
| city | 85% | 100% | 77% | 91% | voting, ties broken by trust (ours) | 0.718 → 0.821, best of the five. Voting fails on groups of two, ROR first ignores two sources that agree against ROR |
| latitude, longitude | 71% | 100% | – | 83% | trust, Wikidata first | within 5 km 0.818 → 0.912 (gold points geocoded, checked by hand). ROR gives the city's point, the median a midpoint in neither source |
| website | 78% | 97% | 92% | 87% | trust, ROR first | 0.949 → 0.949. The longest website is worst (0.897 → 0.872) |
| domains | 78% | 97% | 91% | 87% | trust, ROR first | 0.949 → 0.949. Union (0.897) keeps wrong domains, "in at least 2 sources" (0.846) leaves 1,440 without one |
| foundingYear | 84% | 91% | 73% | 85% | voting | 0.692 → 0.763. Tied with our function and chosen by the order of the list, our function reaches 0.842 on the test half |
| closureYear | – | – | 13% | 2% | the only value | one source, no conflict |
| history | – | – | 15% | 3% | the only value | one source, no conflict |
| institutionTypes | 100% | – | – | 55% | the only value | one source, no conflict |
| numberOfStudents | 17% | – | – | 10% | the only value | one source, no conflict |
| memberships | 25% | – | – | 14% | the only value | one source, no conflict |
| parentInstitutions | – | 8% | 19% | 9% | union | not in the gold standard. The sources mean different things: ROR parent organisations, DEQAR also federations and alliances (*Arqus*, *Université Bretagne Loire*) |
| status | – | 100% | – | 73% | the only value | one source, no conflict |
| numberOfQAReports, lastQAReportDate | – | – | 59% | 11% | the only value | one source, no conflict |

**Trust** is our assumption (ROR 3, Wikidata 2, DEQAR 1), not estimated from data. We tested two orders
(ROR first, Wikidata first) and let the gold standard choose per attribute. How far the data back the
order: see *Limitations*.

**Conflicts inside one source** are settled before fusion. The links are one to one, so no group holds two
records of the same source (none of the 35,551 does). Where a Wikidata item has
several best-ranked founding dates, step 1 keeps the earliest (`fetch_wikidata.py`). Duplicates inside a
source are rare: 26 pairs of Wikidata items share name, country and city (mostly a predecessor and its
successor, such as the two *University of Paris* items), 3 pairs in ROR and 3 in DEQAR.

**Why not another approach:**

| Alternative | Why not |
|---|---|
| one strategy for all attributes | no strategy is best everywhere: ROR first wins names, our function cities, Wikidata first coordinates |
| voting alone | 11,225 of the 13,981 groups have two records, so every disagreement is a tie |
| content-based (longest name, earliest year) | worst for years (0.564): the earliest year is often that of a predecessor |
| trust alone (always ROR) | ignores Wikidata and DEQAR where they agree against ROR, and gives the city's point for coordinates |
| union or intersection for domains | union keeps wrong domains, intersection leaves 1,440 universities without one |
| most recent value | no source dates its individual facts |
| learned source trust (truth discovery) | 39 universities per half are too few to estimate it reliably |

## Limitations

The numbers come from `submission/final-report/scripts/report_numbers.py`. They use the whole gold standard,
including the *test* half, so none of them was used to change the method.

- **Trust set by hand.** Where exactly one of two sources is right on the gold standard (names, country
  codes, cities, founding years, websites), ROR beats DEQAR 18 to 10 (sign test p = 0.19) and Wikidata 35 to
  17 (p = 0.02), while Wikidata and DEQAR are close, 10 to 12 (p = 0.83). The data back ROR first, not the
  order of the other two. That order rarely decides anything, because every group holds a ROR record and
  ROR almost always has a value.
- **Ties between strategies.** Voting won founding years over our function only by the order of the list.
  A tie rule fixed in advance for a reason (for example the simpler function) would have been better.
- **Sources are not independent witnesses.** Voting and our function count agreeing sources as separate
  confirmations. The sources store each other's IDs (75% of ROR records hold a Wikidata ID) but do not copy
  wholesale: linked websites are written exactly alike in only 20% (Wikidata–ROR) and 11% (DEQAR–ROR) of
  the pairs, though 87% and 84% share the host, and only 0.3% of Wikidata–ROR points lie within 100 m of
  each other. Their errors are shared, though: where two sources are both wrong on the gold standard, they
  give the same wrong value 15 times in 34, mostly a shared convention (Stockholm for the Karolinska
  Institutet in Solna, Dublin for Dún Laoghaire) or the same earlier founding date.
- **What a founding year is.** The gold standard keeps one main year per university, chosen case by case in
  the hand check (`hand_note`), and lists other documented dates (earlier roots, university status) in
  `founding_year_alternatives`. 54 of the 80 universities have such dates, and 3 of the 9 wrong years on
  the test half are one of them (0.842 instead of 0.763 if they counted). Step 1 also keeps the earliest of
  several Wikidata founding dates.
- **parentInstitutions mixes meanings.** ROR gives parent organisations, DEQAR also federations and
  European University alliances (*Arqus*, *Université Bretagne Loire*), and 469 of the 2,186 parent values
  in the cleaned ROR data (21%, 20% in the downloaded data, as the report says) are still a ROR ID, because
  the name lookup of step 3 holds only education records (`00davry38` is the Tecnológico Nacional de México). Fusion unites them, and the gold standard does not score them.

## Files and how to run

| File | What it is |
|---|---|
| `fusion.py` | groups the linked records, compares the strategies on the gold standard, fuses everything with the final strategy |
| `build_gold.py` | draws the 80 universities for the gold standard and splits them into two halves |
| `gold_to_xml.py` | writes `fusion_gold.csv` as `fusion_gold.xml` in the target schema and validates it |
| `fused_to_xml.py` | writes `universities_fused.csv` as `universities_fused.xml` in the target schema and validates it (`fusion.py` calls it) |
| `gold_candidates.csv` | the 80 drawn, with the values of each source, why each was drawn and its half |
| `results/universities_fused.csv` | the fused dataset, with its provenance |
| `results/universities_fused.xml` | the fused dataset in the target schema |
| `results/strategies.csv` | accuracy of each strategy on the gold standard |
| `results/list_functions.csv` | accuracy of each list function for domains |
| `results/coordinate_functions.csv` | accuracy of each function for coordinates, and the median distance to the gold point |
| `results/density.csv` | share of filled values per attribute and over all attributes, per source and after fusion |
| `results/consistency.csv`, `group_sizes.csv` | how often the sources agree; universities by number of sources |
| `results/fusion_errors.csv` | the wrong values left (one row per value, with what each source offered), for the error analysis |

```
python gold_to_xml.py    # only after fusion_gold.csv changed
python fusion.py         # also writes the XML
python fused_to_xml.py   # only the XML again, from the CSV
```
