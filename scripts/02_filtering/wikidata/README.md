# Cleaning the Wikidata dataset

This folder turns `data/wikidata/original/wikidata_universities.csv` (22,697 records) into a
dataset that holds only the institutions we want, before schema mapping and
identity resolution. The rules are defined in [`rules.md`](../../../rules.md) in the
repo root. This file explains how they are applied to Wikidata, why, and how
well it works.

| File | What it is |
|---|---|
| `filter.py` | the one script: cleans the type labels and applies Rules 1-5 |
| `validation/ai_checks.csv` | 4,087 checked records with a verdict (junk / real / unsure) |
| `data/wikidata/filtered/wikidata_universities.csv` | the cleaned dataset (19,605 records) |
| `data/wikidata/filtered/Wikidata_Mapping.xml` | the schema-mapped records without the removed ones (input of identity resolution) |
| `data/wikidata/filtered/removed.csv` | every removed record with the rule and the reason |

Run `python filter.py`, then `python ../validate.py` (compares the output of all
three filters with the AI verdicts). The files in `data/wikidata/original/` are
never changed.

## Result in one look

| | Records |
|---|---|
| Input | 22,697 |
| Removed, Rule 1 (below bachelor's level) | 2,162 |
| Removed, Rule 2 (not recognized) | 14 |
| Removed, Rule 3 (part of another institution) | 807 |
| Removed, Rule 4 (not mainly education) | 84 |
| Removed, Rule 5 (duplicate) | 25 |
| **Kept** | **19,605** |

Validation (details below): about 98% of what is removed is really junk, and
about 11% of what is kept is still junk.

**Later change:** the name rules and the duplicate rule moved to
`scripts/02_filtering/common.py` and are now shared with ROR and DEQAR; while
cleaning those two sources some name rules got narrower exceptions and a few
rules were added (K-12 schools, vocational training, research institutes in
other languages, departments, ...). The overview of all three sources is in
`scripts/02_filtering/README.md`; this file keeps the history of the first source.

## What we did and why

### 1. Every rule is a fixed condition

A record goes if a condition matches, every time; otherwise it stays. There are
no case-by-case decisions and no review lists. This keeps the cleaning
repeatable and easy to explain. The price is that no fixed rule is perfect, so
we aimed for "remove as much junk as possible while losing as few real
universities as possible" rather than for a perfect dataset.

### 2. Clean the type labels first

All records were downloaded as instances of "university" (Q3918) or one of its
subclasses, so every record already claims to be some kind of university. The
`types` column lists the Wikidata labels of each record, but they were messy:
stray spaces, mixed case, duplicates and many labels that say nothing about the
kind of institution (e.g. "open-access publisher", "building", "cultural
property"). The script trims and lower-cases them and drops those noise labels.

### 3. Rules 1-4 on the labels

Each rule has a list of labels that remove a record:

- **Rule 1, level:** junior colleges, community colleges and Japanese colleges
  of technology always go. Seminaries and theological schools go unless the
  record also has a university label. School-level labels (high school,
  vocational school, ...) go unless there is a higher-education label.
- **Rule 2, recognized:** diploma mills, unaccredited institutions, fake and
  never-opened (proposed, abandoned) institutions always go.
- **Rule 3, own organisation:** faculty, campus, branch, department, constituent
  college, but only when no higher-education label stands next to it.
- **Rule 4, education:** research institute, hospital, library, museum,
  university system, consortium, government agency, again only without a
  higher-education label.

*Why "only without a higher-education label":* applied literally, the labels
would have removed the University of Warwick ("campus"), King's College London
("constituent college") and the University of Florence ("archives").

### 4. Check the removals and protect wrongly labelled universities

AI agents checked all 1,600 records the label rules removed (round 1). 20 were
real universities, almost all general Christian universities that Wikidata also
labels "seminary" or "Bible college" because a seminary is one of their parts
(e.g. Indiana Wesleyan, Lipscomb, Abilene Christian). Two exceptions bring 13 of
them back without bringing back any real seminary:

- an arts label (conservatory, music school, ...) beats a religious label;
- a religious label does not remove a record whose name contains "University",
  has no religious word, whose label is not "catholic seminary" and that has a
  student count in Wikidata.

These exceptions are tuned to Wikidata and are not part of `rules.md`, because
they would not carry over to other sources.

### 5. Check the kept records and add name rules

AI agents then checked the kept records (round 2): all 1,587 records with a
warning sign and a random sample of 300 without one. The labels missed a lot:
Wikidata calls most faculties, campuses, branches and research centres
"university" as well. Their names, however, give them away. We tested candidate
name rules on the checked records and kept the ones that remove much junk and
few real universities:

| Name rule (name contains …) | Rule | Removed |
|---|---|---|
| school / college / department of X + "university" | 3 | 281 |
| seminary, theology, Bible, divinity, madrasa, jamia | 1 | 189 |
| campus (not "global campus", "campus university") | 3 | 148 |
| Islamic Azad / Payame Noor + branch name | 3 | 101 |
| faculty of, faculté de, Fakultät, fakultas, … | 3 | 97 |
| centre/center for, research unit, laboratory | 3 | 84 |
| branch, unit | 3 | 76 |
| system, consortium, university alliance, association, society | 4 | 48 |
| infantry, training centre, cadet | 1 | 42 |
| community college, junior college | 1 | 26 |
| high school, secondary school | 1 | 12 |

(Counts with the final filter; the "military school" part of the infantry rule
was dropped in step 6.)

Rejected because they removed too many real universities: "polytechnic" in all
countries (more than half real), "hospital" (most are medical colleges),
"university, place" patterns, "no website and no students", and "the linked
ROR record has a parent".

### 6. Second round of name rules after the validation

The validation (below) showed what junk was left and which name rules misfire.
Each change was tested on the checked records first:

| Change | Effect |
|---|---|
| **New:** "polytechnic" in India, Bangladesh, Pakistan, Nepal, Sri Lanka, Nigeria, Ghana, Kenya, Zimbabwe, Malaysia (Rule 1) | removes 263; all 16 checked ones were junk. Polytechnics there award diplomas below bachelor's level (e.g. diploma after class 10, ND/HND) |
| **New:** "vocational", "technical college", "technical institute", "training institute" (Rule 1) | removes 125; 17 checked junk, 2 real |
| **Dropped:** "military school", "naval school" from the infantry rule | 20 fewer removals; saves officer academies that award degrees (Peru, Colombia) |
| Not changed: "jamia", "system/association" in names starting "University of" | an exception would bring back more junk (15 and 8) than real universities (1 and 3) |

Also tested and not used: Wikidata's "part of" / "parent organization" links
(P361, P749). On their own they removed as many real universities as junk
(federal universities like the University of London, former institutions
pointing to their successor); the best variant (parent is a university in our
data and the record has no ROR link) was only as good as a name rule, and using
it would mean downloading Wikidata again for the whole pipeline.

### 7. Duplicates (Rule 5)

Same cleaned name, same country and same website domain = one institution; the
city is ignored (it is often the town in one record and the region in the
other). A record without website or country is never a duplicate. The record
with the most filled fields stays. An agent check of 82 groups with the same
name and country found 36 more real duplicates, but almost all have different
websites (old and new site, .org and .com) or none, and no general rule caught
them without also merging different institutions (e.g. a university and its
closed predecessor of the same name). Rule 5 was left as it is.

### 8. No use of the links to ROR

Records that Wikidata links to ROR are almost always real universities, but the
links between the sources are the answer key of identity resolution, so the
filter does not use them. An earlier warning column `has_ror_link` was dropped
for that reason.

## Validation

All verdicts come from AI agents (Claude subagents) that judged each record
against `rules.md` with their own knowledge and a few web searches. **No person
has checked them yet.** The agents were strict in some places a person might not
be (see "Open questions").

| Round | What was checked | Records |
|---|---|---|
| 1 | every record removed by the first label rules | 1,600 |
| 2a | every kept record with a warning sign (suspicious word or label) | 1,587 |
| 2b | random sample of kept records without a warning sign | 300 |
| 3a | **fresh** random sample of the final kept records (never seen before) | 400 |
| 3b | **fresh** random sample of records removed by the name rules | 200 |

Results with the final `filter.py` (`python ../validate.py`):

- **Removed records:** of the round-3b records that are still removed, 9 of 196
  (4.6%) were real universities; with the final, shared rules it is 4 of 177
  (2.3%). In round 1, 7 of 1,600 are still real after the exceptions in step 4.
  Overall 36 of the 2,470 checked removed records are real (1.5%).
- **Kept records:** of the round-3a records that are still kept, 44 of 387
  (11.4%) are junk and 13 (3.4%) unsure, so roughly 2,200 junk records are
  still in the 19,605 kept.
- **Over all checked records:** 83% of the records judged junk are removed, 3%
  of the records judged real are removed.

Note: the second round of name rules (step 6) was designed after looking at
rounds 2 and 3, so its numbers on those rounds are somewhat optimistic.

What the remaining junk looks like: polytechnics and vocational colleges whose
name does not say so (e.g. Chinese vocational colleges), schools, campuses and
departments whose name does not show it, a few diploma mills and Bible colleges.

What the name rules still get wrong: "jamia" also means "university" (Jamia
Hamdard), "system" and "association" are part of some university names
(University of Rizal System, University of Turkish Aeronautical Association),
and a few stand-alone medical schools are named "X University School of
Medicine".

## Open questions

These are definitions, not bugs; the agents decided them differently, and the
team should settle them:

1. Accredited theological universities that award real degrees (e.g. Protestant
   Theological University, Sankt Georgen): in or out? Now mostly out.
2. Campuses that are accredited on their own (e.g. Rutgers-Newark, Penn State
   Altoona): in or out? Now in unless the name or label shows a campus.
3. Diploma-level polytechnics: now out in the ten countries listed in step 6,
   in everywhere else (e.g. Indonesian polytechnics, which mostly offer
   bachelor-level applied degrees).
4. Affiliated colleges whose degrees are awarded by a university (India,
   Nepal): in or out? Now in.
5. Closed or historical institutions: parked, all stay for now.
