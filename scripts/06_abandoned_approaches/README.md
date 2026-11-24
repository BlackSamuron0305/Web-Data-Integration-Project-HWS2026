# Abandoned approaches

Approaches we tried seriously and then dropped, with the reason. The code is kept so the numbers can
be checked. Smaller things we tried inside a step (other blockers, matchers, rules) are described in
that step's README.

| Folder | Approach | Step it belongs to |
|---|---|---|
| `01_selection/` | select Wikidata by *higher education institution* instead of *university* | 1, data collection |
| `02_filtering/` | AI agents decide for each record (no code) | 2, cleaning |
| `02_filtering/` | keep only names with the word "university" | 2, cleaning |

## 1. A wider Wikidata selection (`01_selection/wider_wikidata.py`)

**Idea.** Step 1 takes every Wikidata item whose type is *university* (Q3918) or a subclass. Universities
that Wikidata types otherwise are missing: 8,089 of the cleaned ROR records point to a Wikidata item
outside our selection, for example Williams College (*liberal arts college*) or École des Ponts
(*grande école*). The wider class *higher education institution* (Q38723) should catch them.

**What we did** (24 November 2026, after the pipeline was finished). We downloaded the items of the
wider class that we did not have yet, with only the attributes the Wikidata cleaning rules need, ran
cleaning rules 1-4 on them and counted the overlap with ROR. Then AI agents judged a random sample of
200 of the items that pass the rules, 100 with and 100 without a ROR id.

| | Items |
|---|---|
| new items in the wider class | 79,364 |
| without an English name | 7,220 |
| removed by cleaning rules 1-4 | 22,463 |
| kept by cleaning rules 1-4 | 52,903 (the cleaned Wikidata today: 19,605) |
| kept and linked to an entry that is ROR-only in the fused result | 3,762 |

| AI-checked sample of the kept items | University | Not a university | Unsure |
|---|---|---|---|
| with a ROR id (5,284 kept) | 49 | 47 | 4 |
| without a ROR id (47,619 kept) | 9 | 86 | 5 |

Scaled up, that is about 2,600 + 4,300 = 6,900 universities among the 52,903 kept items, about one in
eight. The rest are mostly affiliated colleges in India (24,283 of the kept items are Indian), primary
and secondary schools in Pakistan, Italian technical high schools (*istituto tecnico*) and theological
schools.

**Why we dropped it.**
- It would add about 46,000 non-universities for about 7,000 universities. Today about 11% of the
  cleaned Wikidata records are not universities; among the new items it would be about 87%.
- Our cleaning rules were written for the types of the *university* class and do not cover the new
  types. Using them would need new rules, a new check of them, new mapping, matching and fusion runs
  and new evaluation sets, which did not fit before the deadline.
- The gain is small: only 3,762 of the kept items link to a ROR-only entry, and about half of those are
  universities.

The report mentions this in its limitations. The verdicts are AI judgements, not checked by a person;
`results/wider_new_records.csv` is the download of 24 November 2026 (Wikidata changes daily).

```
python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py fetch   # about 20 minutes
python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py check
```

## 2. Letting AI agents decide (no code)

**Idea.** Instead of writing rules, let AI agents (Claude with subagents) look at each record and
decide whether it is a university, then remove everything judged "not a university".

**Why we dropped it.**
- The agents were too often unsure. An unsure record cannot be removed safely, so it stayed in the
  data, and many of the errors we wanted to remove stayed with it. In the random samples of kept
  records, up to 10% of the verdicts were "unsure" (ROR).
- We hit our usage limits fast. The three sources hold 61,807 records, far more than we could check
  this way, so the method does not scale to the full data.

The agents are still useful for **checking** the fixed rules on samples
(`scripts/02_filtering/validation/`), but not for making the decision itself.

## 3. Keep only names with the word "university" (`02_filtering/university_word_rule.py`)

**Idea.** The simplest possible rule: a record stays only if its name contains "univers" (university,
universidad, université, Universität, ...).

| | Wikidata | ROR | DEQAR |
|---|---|---|---|
| records | 22,697 | 30,131 | 8,979 |
| removed by the rule | 8,530 (38%) | 16,121 (54%) | 5,385 (60%) |
| removed records with an AI check | 2,476 | 4,387 | 2,269 |
| of those real universities | 369 | 413 | 367 |

**Why we dropped it.** We did not benefit from it. It removes a third to more than half of every
source, far more than there is junk. Many real higher-education institutions have no "university" in
their name: colleges, institutes of technology, academies, Hochschulen, grandes écoles. Already among
the records that were checked, more than 1,100 real universities would have been removed. Junk with
"university" in the name, such as campuses and faculties named after their university, would have
stayed.

```
python scripts/06_abandoned_approaches/02_filtering/university_word_rule.py
```
