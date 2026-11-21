# Cleaning the three sources

This folder holds the data-preparation step that runs **before** schema mapping
and identity resolution: it removes every record that is not a university in
the sense of [`rules.md`](../../rules.md) (repo root).

Pipeline of the project:

1. collect the data (`scripts/01_data_collection/`)
2. **clean each source (this folder)**
3. schema mapping on the cleaned data (the MapForce output without the removed records)
4. identity resolution on the cleaned mapping (`scripts/03_identity_resolution/`, round 8)

**Why clean before matching**, even though the matching scores get a little
worse: the project is about universities, so removing non-universities is part
of the data preparation. A matcher that works on campuses, seminaries and
research institutes produces correct links between wrong things. Cleaning
cannot be perfect with general rules, but every rule is simple, fixed,
documented and tested.

## Files

| Path | What it is |
|---|---|
| `common.py` | the rules shared by all sources (name rules, duplicate rule) and the writing of the outputs |
| `<source>/filter.py` | one script per source: shared rules + what that source's data offers |
| `<source>/validation/ai_checks.csv` | records checked by AI agents, with verdict and explanation |
| `validate.py` | compares the current filters with all checks per round, writes `validation_summary.csv` |
| `wikidata/README.md` | the detailed story of the Wikidata filter (the first one) |

Each filter reads `data/<source>/original/` (downloaded CSV and MapForce XML,
never changed) and writes `data/<source>/filtered/`:

| File | What it is |
|---|---|
| CSV (same name as the original) | the cleaned records |
| XML (same name as the original) | the schema-mapped records without the removed ones (input of identity resolution) |
| `removed.csv` | every removed record with rule and reason |

Run: `python <source>/filter.py` for wikidata, ror, deqar, then `python validate.py`.

The links between the sources (`ror_id`, `wikidata_id`) are the answer key of
identity resolution. Rules 1-4 do not use them; Rule 5 still counts them as
filled fields when it picks which of two duplicates stays (open point).

## The rules

Every rule is a **fixed condition**: if it matches, the record goes, every
time. There is no case-by-case decision and no review list. Rules run in the
order of `rules.md` (1 level, 2 recognized, 3 own organisation, 4 education,
5 duplicates); the first match decides.

### Shared rules (`common.py`), used for all three sources

Words in the **name** that show a record is not a university of its own, each
with a few exceptions that the checks showed to be necessary:

| Rule | Name rule | Main exceptions |
|---|---|---|
| 1 | seminary, theology, Bible, divinity, madrasa, darul uloom | – |
| 1 | community college, junior college | – |
| 1 | high school, secondary school, school board / district | "High School of …" (Polish and Bosnian higher schools) |
| 1 | infantry, training centre, cadet | academies, naval schools (officer academies award degrees) |
| 1 | vocational, technical college / institute, training institute | Serbian "schools of vocational studies", Polish "higher vocational schools", "applied sciences" |
| 1 | polytechnic, only in India, Bangladesh, Pakistan, Nepal, Sri Lanka, Nigeria, Ghana, Kenya, Zimbabwe, Malaysia, China | "polytechnic university" |
| 1 | Japanese college of technology (kosen), only in Japan | – |
| 1 | elementary / primary / middle / charter school, kindergarten, K-12 | – |
| 1 | technikum, technical school, professional college, vocational school, kolej | – |
| 1 | vocational training, adult and continuing education (incl. French "institut de formation") | – |
| 1 | "college" in Ukraine, Russia, Belarus, Kazakhstan, Moldova, Uzbekistan (short-cycle) | academies, institutes, universities |
| 3 | campus | "Main Campus" (the university itself), "Hochschule Campus Wien" type names |
| 3 | branch, unit | – |
| 3 | faculty of … (only if the source names a parent; independent faculties stay) | "institut facultaire" |
| 3 | centre / center for, research unit, laboratory | "centre for higher / technological education", "academic studies" |
| 3 | school / college / department … of … University | "University College", "higher school", "deemed university" |
| 3 | Islamic Azad / Payame Noor + branch | the main university record |
| 3 | department of …, Spanish "higher technical school of … engineering" | – |
| 4 | university system, system of universities | – |
| 4 | consortium, alliance, association, society | "Education Society's College" (India), "University of … Association" |
| 4 | research institute, research centre, academy of sciences, and the same words in other languages | names with university, college, school, graduate, educational |
| 4 | library, museum, clinic | names with university, college, school |
| 5 | same cleaned name + country + website domain = duplicate (city ignored; no website = never a duplicate) | – |

### Source-specific additions

- **Wikidata** (`wikidata/filter.py`): the Wikidata type labels ("junior college
  in Japan", "Catholic seminary", "faculty", "research institute", ...), only
  when no higher-education label stands next to them; a small protection for
  general Christian universities wrongly labelled "seminary". Details in
  `wikidata/README.md`.
- **ROR** (`ror/filter.py`): a ROR type "healthcare", "facility" or
  "government" next to "education" removes the record if the name has no
  higher-education word.
- **DEQAR** (`deqar/filter.py`): DEQAR names parent institutions. A school,
  college, institute, department or centre whose parent is a university (not an
  alliance) is part of that university, e.g. the Spanish "Higher Polytechnic
  School" of a university. Not applied in France, where the parent is usually a
  grouping of universities (ComUE) and the grandes écoles are institutions of
  their own.

## Result

| | Wikidata | ROR | DEQAR |
|---|---|---|---|
| records | 22,697 | 30,131 | 8,979 |
| removed, Rule 1 (level) | 2,162 | 3,230 | 801 |
| removed, Rule 2 (recognized) | 14 | – | – |
| removed, Rule 3 (part of another institution) | 807 | 601 | 1,290 |
| removed, Rule 4 (not mainly education) | 84 | 374 | 113 |
| removed, Rule 5 (duplicates) | 25 | 7 | 11 |
| **kept** | **19,605** | **25,919** | **6,764** |

Biggest groups: Wikidata 580 Japanese junior colleges and 366 Catholic
seminaries (type labels); ROR 1,129 vocational/technical colleges (mostly
Chinese vocational colleges and US technical colleges), 700 community and
junior colleges, 472 school districts; DEQAR 574 faculties of universities
(mostly Spain), 310 schools of universities, 289 vocational and adult-education
centres (France, Belgium), 271 Ukrainian colleges.

## Validation

The verdicts come from AI agents (Claude subagents) that judged each record
against `rules.md` with their own knowledge. **No person has checked them
yet.** In total about 12,700 records were checked (4,087 Wikidata, 5,694 ROR,
2,942 DEQAR): every removed record of the first rules, every record removed
by a rule added later, and random samples of the kept records before and after
the rule changes.

`python validate.py` (numbers with the final rules):

| | Wikidata | ROR | DEQAR |
|---|---|---|---|
| checked removed records | 2,470 | 4,108 | 1,902 |
| of those real (wrong removals) | 36 (1.5%) | 44 (1.1%) | 38 (2.0%) |
| fresh random sample of kept records | 387 | 496 | 469 |
| junk in that sample | 11.4% | 15.3% | 8.1% |
| unsure in that sample | 3.4% | 10.1% | 7.5% |
| estimated junk left | ~2,200 | ~4,000 | ~550 |

So about 98-99% of what is removed is really junk, and roughly 8-15% of what is
kept still is. The remaining junk is mostly what names cannot show: US
community colleges called "X College", campuses and schools of a university
with a plain name, research institutes with a plain name, diploma-level
schools.

How the rules were found: each rule was first tested on the checked records
(how many junk records and how many real universities it would remove) and
only kept when it removed much junk and few real universities. Rules whose
exceptions let too much junk back in were narrowed again (see the history in
`wikidata/README.md` for the first source). The rules added late were tuned on
the records the agents had already checked, so their numbers on those records
are somewhat optimistic; the fresh samples (round 3a) were drawn after the
rules were fixed for ROR and DEQAR.

## Open questions for the team

1. Accredited theological universities: now out (Rule 1 "theological schools").
2. Campuses accredited on their own (Rutgers-Newark, Penn State Altoona): now in
   unless the name shows "campus".
3. Closed institutions: parked, all stay.
4. The AI verdicts should be spot-checked by a person before the report says
   "checked by hand".
