# Step 2: Cleaning the three sources

This step removes every record that is not a university and writes cleaned copies of the sources. A
university, for us, awards degrees at bachelor's level or higher and is an organisation of its own,
not a campus, faculty or branch. The exact definition is in [`rules.md`](rules.md).

## Why we clean, and why before matching

We found the problem late. The first matching pass (step 4, rounds 1-3) produced links such as
*Pacific University Health Professions Campus* to *Pacific University Oregon*: correct-looking links
between things that are not universities of their own. A look at random samples showed that a large
share of the ROR and DEQAR records are not universities at all (schools, school districts, hospitals,
faculties, vocational centres).

We clean **before** schema mapping and matching, even though the matching scores get a little worse:
the project is about universities, so removing everything else is part of preparing the data. A matcher
that works on campuses and seminaries only produces correct links between wrong things.

## What we did

Every rule is a **fixed condition**: if it matches, the record goes, every time. There are no
case-by-case decisions and no review lists, so the cleaning can be repeated and explained. No fixed rule
is perfect, so the aim was "remove as much junk as possible while losing as few real universities as
possible".

A record stays only if it passes five rules, in this order (the first rule that matches decides):

1. it awards degrees at bachelor's level or higher (not a community college, seminary, school, ...);
2. it is recognised (not a diploma mill or a never-opened institution);
3. it is an organisation of its own (not a campus, branch, faculty or department);
4. its main purpose is education (not a research institute, hospital, library or association);
5. it appears only once in its source (same cleaned name + country + website domain = duplicate).

### Shared name rules (`common.py`)

Words in the **name** that show a record is not a university of its own, each with the exceptions the
checks showed to be necessary:

| Rule | The name contains | Main exceptions |
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
| 3 | faculty of … (only if the source names a parent) | "institut facultaire" |
| 3 | centre / center for, research unit, laboratory | "centre for higher / technological education", "academic studies" |
| 3 | school / college / department … of … University | "University College", "higher school", "deemed university" |
| 3 | Islamic Azad / Payame Noor + branch | the main university record |
| 3 | department of …, Spanish "higher technical school of … engineering" | – |
| 4 | university system, system of universities | – |
| 4 | consortium, alliance, association, society | "Education Society's College" (India), "University of … Association" |
| 4 | research institute, research centre, academy of sciences (also in other languages) | names with university, college, school, graduate, educational |
| 4 | library, museum, clinic | names with university, college, school |
| 5 | same cleaned name + country + website domain (city ignored; no website = never a duplicate) | – |

### What each source adds (`<source>/filter.py`)

- **Wikidata:** the type labels. They are cleaned first (trimmed, lower-cased, noise such as
  "building" or "open-access publisher" dropped). Labels such as "junior college", "Catholic seminary",
  "faculty", "campus", "research institute" remove a record, but only if no higher-education label
  stands next to it. Applied literally, they would have removed the University of Warwick ("campus"),
  King's College London ("constituent college") and the University of Florence ("archives"). Two small
  exceptions protect general Christian universities that Wikidata also labels "seminary" (Indiana
  Wesleyan, Lipscomb, Abilene Christian).
- **ROR:** a type "healthcare", "facility" or "government" next to "education" removes the record if
  the name has no higher-education word.
- **DEQAR:** DEQAR names parent institutions. A school, college, institute, department or centre whose
  parent is a university (not an alliance) is part of it, e.g. the Spanish "Higher Polytechnic School"
  of a university. Not applied in France, where the parent is usually a grouping of universities
  (ComUE) and the grandes écoles are institutions of their own.

The links between the sources (`ror_id`, `wikidata_id`) are the answer key of identity resolution, so
rules 1-4 never use them. Rule 5 still counts them as filled fields when it picks which of two
duplicates stays.

## Result

| | Wikidata | ROR | DEQAR |
|---|---|---|---|
| records | 22,697 | 30,131 | 8,979 |
| removed, rule 1 (level) | 2,162 | 3,230 | 801 |
| removed, rule 2 (recognised) | 14 | – | – |
| removed, rule 3 (part of another institution) | 807 | 601 | 1,290 |
| removed, rule 4 (not mainly education) | 84 | 374 | 113 |
| removed, rule 5 (duplicate) | 25 | 7 | 11 |
| **kept** | **19,605** | **25,919** | **6,764** |

Biggest groups removed: Wikidata 580 Japanese junior colleges and 366 Catholic seminaries; ROR 1,129
vocational and technical colleges, 700 community and junior colleges, 472 school districts; DEQAR 574
faculties (mostly Spain), 310 schools of universities, 289 vocational and adult-education centres
(France, Belgium), 271 Ukrainian colleges.

## How we checked it

AI agents (Claude subagents) judged about 12,700 records against `rules.md` (4,087 Wikidata, 5,694
ROR, 2,942 DEQAR): every record removed by the first rules, every record removed by a rule added later,
and random samples of the kept records before and after the rule changes. **No person has checked these
verdicts yet.** `validation/validate.ipynb` compares the current rules with them:

| | Wikidata | ROR | DEQAR |
|---|---|---|---|
| checked removed records | 2,470 | 4,108 | 1,902 |
| of those real universities (wrong removals) | 36 (1.5%) | 44 (1.1%) | 38 (2.0%) |
| fresh random sample of kept records | 387 | 496 | 469 |
| junk in that sample | 11.4% | 15.3% | 8.1% |
| unsure in that sample | 3.4% | 10.1% | 7.5% |
| estimated junk left | ~2,200 | ~4,000 | ~550 |

So about 98-99% of what is removed really is junk, and roughly 8-15% of what is kept still is. The junk
left is mostly what a name cannot show: US community colleges called "X College", campuses and research
institutes with a plain name, diploma-level schools.

A hand check of 50 random removed records per source is prepared in
`data/<source>/filtered/hand_check_removed.csv` (column `hand_verdict`); **it is not filled in yet**.
`validation/hand_check_summary.py` counts the result once it is.

## How we found the rules, and what did not work

Each rule was first tested on the checked records (how much junk and how many real universities it
would remove) and only kept if it removed much junk and few universities. We started with Wikidata,
then moved the name rules into `common.py` and reused them for ROR and DEQAR, where some got narrower
exceptions and a few were added (K-12 schools, vocational training, research institutes in other
languages, departments).

Tried and dropped:

- **Name rules that removed too many real universities:** "polytechnic" in every country (more than
  half were real), "hospital" (mostly medical colleges), "military school" / "naval school" (officer
  academies award degrees), "no website and no students".
- **Wikidata's "part of" / "parent organisation" links (P361, P749):** on their own they removed as many
  real universities as junk (the University of London, former institutions pointing to their
  successor). The best variant was only as good as a name rule and would have needed a new download.
- **A wider duplicate rule:** the agents found 36 more duplicates with the same name and country, but
  almost all have different websites (old and new, .org and .com), and no rule caught them without also
  merging different institutions.
- **Cleaning ROR through the ID links** (remove a ROR record if its Wikidata partner was removed): it
  worked, but it uses the answer key, so it is not allowed.
- **Removing non-universities only before or only after matching, from hand-check lists**
  (identity-resolution rounds 4-6): before matching, a record removed in one source left its partner
  in another without a match, and the matcher gave it a wrong one (76 new links, e.g. *Islamic Azad
  University of Nishapur* to *Neyshabur University of Medical Sciences*). After matching, the links
  were gone but the non-universities stayed in the data.
- **AI agents deciding each record, and keeping only names with "university":** see
  `scripts/06_abandoned_approaches/`.

The rules added late were tuned on records the agents had already checked, so their numbers on those
records are somewhat optimistic. The fresh samples of kept records were drawn after the rules were
fixed.

## Open questions

1. Accredited theological universities that award real degrees: now out (rule 1).
2. Campuses accredited on their own (Rutgers-Newark, Penn State Altoona): now in unless the name says
   "campus".
3. Diploma-level polytechnics: out in the countries listed above, in everywhere else.
4. Affiliated colleges whose degrees a university awards (India, Nepal): now in.
5. Closed institutions: all stay for now.

## Files and how to run

| File | What it is |
|---|---|
| `rules.md` | the definition of a university (rules 1-5) |
| `common.py` | the shared name rules, the duplicate rule and the writing of the outputs |
| `<source>/filter.py` | one script per source: the shared rules plus what that source offers |
| `validation/<source>/ai_checks.csv` | the AI-checked records with verdict and explanation |
| `validation/validate.ipynb` | compares the current rules with all AI checks (tables per round, summary, plot) |
| `validation/hand_check_summary.py` | summary of the hand check of removed records, written to `validation/results/` |

Each filter reads `data/<source>/original/` and writes `data/<source>/filtered/`: the cleaned CSV
(same name as the original) and `removed.csv` (every removed record with rule and reason). The filters
write no XML; MapForce maps the cleaned CSV in step 3.

```
python wikidata/filter.py
python ror/filter.py
python deqar/filter.py
```

then run `validation/validate.ipynb`.
