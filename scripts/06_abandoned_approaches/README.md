# Abandoned approaches

Approaches we tried seriously and then dropped, with the reason. The code is kept so the numbers can
be checked. Smaller things we tried inside a step (other blockers, matchers, rules) are described in
that step's README.

| Folder | Approach | Step it belongs to |
|---|---|---|
| `01_selection/` | DBpedia and the THE ranking as sources (replaced by DEQAR) | 1, data collection |
| `01_selection/` | select Wikidata by *higher education institution* instead of *university* | 1, data collection |
| `02_filtering/` | AI agents decide for each record (no code) | 2, cleaning |
| `02_filtering/` | keep only names with the word "university" | 2, cleaning |
| `02_filtering/` | a local LLM decides for each record, and rescues removed records | 2, cleaning |
| `04_identity_resolution/` | a multilingual model for the embedding blocker | 4, identity resolution |

## 1. DBpedia and the THE ranking as sources (`01_selection/fetch_dbpedia.py`, `01_selection/build_the_rankings.py`)

**Idea.** Our project proposal planned four sources: Wikidata, DBpedia, ROR and the Times Higher Education
(THE) World University Rankings 2026. DBpedia would add a second open knowledge graph, and THE would add
ranks, scores and student figures.

**What we did** (first download on 3 October 2026). `fetch_dbpedia.py` downloads every resource of class
`dbo:University` from the DBpedia SPARQL endpoint, one query per attribute and page by page.
`build_the_rankings.py` turns the table data that THE's ranking page loads into one row per university.

| | DBpedia | THE ranking |
|---|---|---|
| universities | 27,728 | 3,118 |
| of those | 25,715 (92.7%) link to a Wikidata item | 2,191 ranked, 927 "reporters" without a rank |

**Why we dropped them.**
- DBpedia is extracted from Wikipedia, and 92.7% of its universities link to a Wikidata item. Its facts
  largely repeat Wikidata's, so it is not an independent source. Of the linked items, 13,021 are in our
  Wikidata selection, and the rest are Wikidata items of other classes, the same gap as in section 2.
- The THE ranking lists only 3,118 institutions, about a tenth of ROR's 30,131 education records, and its
  terms do not allow republishing the data.
- DEQAR replaced both: 8,979 institutions, with their quality assurance reports.

The downloads are not in the repository. The DBpedia endpoint returns today's data, and THE's data must
not be republished (the script's output is git-ignored).

```
python scripts/06_abandoned_approaches/01_selection/fetch_dbpedia.py        # results/dbpedia_universities.csv
python scripts/06_abandoned_approaches/01_selection/build_the_rankings.py   # results/the_rankings_2026.csv
```

## 2. A wider Wikidata selection (`01_selection/wider_wikidata.py`)

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
  cleaned Wikidata records are not universities, while among the new items it would be about 87%.
- Our cleaning rules were written for the types of the *university* class and do not cover the new
  types. Using them would need new rules, a new check of them, new mapping, matching and fusion runs
  and new evaluation sets, which did not fit before the deadline.
- The gain is small: only 3,762 of the kept items link to a ROR-only entry, and about half of those are
  universities.

The report mentions this in its limitations. The verdicts are AI judgements, not checked by a person, and
`results/wider_new_records.csv` is the download of 24 November 2026 (Wikidata changes daily).

```
python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py fetch   # about 20 minutes
python scripts/06_abandoned_approaches/01_selection/wider_wikidata.py check
```

## 3. Letting AI agents decide (no code)

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

## 4. Keep only names with the word "university" (`02_filtering/university_word_rule.py`)

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

## 5. A local LLM decides, or rescues removed records (`02_filtering/local_llm_cleaning.py`)

**Idea.** Section 3 failed on the cost of a paid model. A small model on our own GPU costs nothing, so
could it take the decision instead of the fixed rules? Qwen2.5 (3B and 7B weights, via Ollama, the same
family as identity resolution approach 9) gets the cleaning rules in short and one record, and answers keep
or drop. We asked each record twice: with the record only, and with text from the internet, which is the
title, description and start of the record's homepage, or its Wikidata description if it has no website.
The run took place on 27 November 2026 on a laptop GPU (RTX 5070, 8 GB), at about 9 records/s for 3B and
4-5 records/s for 7B.

**Test on 300 records with a known answer.**
- The 150 removed records we checked by hand: 13 of them are real universities.
- 150 kept records from the agents' random sample: 133 universities and 17 others, by the agents' verdict.

| | right on the 150 hand-checked removals | universities rescued | others brought back | right on the 150 kept records | universities dropped |
|---|---|---|---|---|---|
| our rules | 137 (91%) | 0 of 13 | 0 of 137 | 133 (89%) | 0 of 133 |
| 3B, record only | 122 (81%) | 4 | 19 | 112 (75%) | 31 (23%) |
| 3B, with homepage | 129 (86%) | 4 | 12 | 99 (66%) | 45 (34%) |
| 7B, record only | 132 (88%) | 2 | 7 | 93 (62%) | 55 (41%) |
| 7B, with homepage | 130 (87%) | 3 | 10 | 90 (60%) | 58 (44%) |

**Rescue: all 9,519 removed records.** Next, the model judged every record the rules removed, with the
record only. We compared its answers with the verdicts the AI agents gave 8,480 of these removals: 118
universities, 162 unsure and 8,200 not universities.

| | brought back | of the agents' 118 universities | agents' non-universities brought back |
|---|---|---|---|
| 3B | 1,152 (12%) | 32 | 780 |
| 7B | 387 (4%) | 16 | 247 |

**Why we dropped it.**
- **Worse than the rules on both sides.** The model throws out real colleges whose name lacks
  "university": *Davao de Oro State College*, *Recaredo Castillo College*, *Florida College*.
  It keeps campuses, units and systems whose name has it: branches of *Islamic Azad University*, *School of
  Mathematics, Peking University*, *Colorado State University System*.
- **The bigger model is stricter, not better.** It drops more of everything, including 41% of the kept
  universities.
- **The homepage text does not help.** It filters out a little more junk among the removals, but throws
  out more real universities among the kept records.
- **Rescuing does not pay off either.** For every university it brings back, it brings back about 15 (7B)
  to 24 (3B) non-universities. 869 of the 3B model's 1,152 rescues are rule-3 removals (faculties, campuses,
  branches).
- **A comparison, not knowledge.** In identity resolution the model compares two records that are both
  in the prompt. Here it would need to know the institution, and a small model knows little about
  thousands of small colleges.

The verdicts on the kept records and the agents' verdicts on the removals are AI judgements, not checked
by hand. Only the 150 hand-checked removals are a hand-made answer. `results/` holds the model's answers
per record (`llm_test_*.csv`, `llm_rescue_*.csv`) and the counts above (`evaluation_*.csv`). The raw
answers and the fetched web text are cached in `results/cache/local_llm_cleaning/` at the repository
root (not in git, like approach 9), so a rerun asks only what is missing.

```
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
python scripts/06_abandoned_approaches/02_filtering/local_llm_cleaning.py test qwen2.5:3b      # ~2 minutes
python scripts/06_abandoned_approaches/02_filtering/local_llm_cleaning.py rescue qwen2.5:3b    # ~20 minutes
```

## 6. A multilingual model for the embedding blocker (`04_identity_resolution/multilingual_blocking.py`)

**Idea.** One of the three blockers of identity resolution takes, for every record, the ten ROR records
with the nearest names in a sentence-embedding space, to catch names that are spelled differently. It uses
PyDI's default model, the English *all-MiniLM-L6-v2*. Many of our missed matches have names in two
languages (*Koninklijk Conservatorium Brussel* and *Royal Conservatory of Brussels*), so a multilingual
model should place them closer together. We tried *paraphrase-multilingual-MiniLM-L12-v2*, the model of
matching approach 3.

**What we did.** Lakpa first compared the two models on 23 November 2026, with our older labelled pairs
(git commit a68f02b), and found no gain. We redid the test on 28 November 2026 with the final labelled
pairs, on both runs and with the pipeline's settings (ten nearest names, similarity at least 0.5). As in
the first test, we also embedded the name together with the city and the country. PC (pair completeness)
is the share of the validation matches kept (142 Wikidata–ROR, 152 DEQAR–ROR), by the embedding blocker
alone and in the union with the pipeline's other two blockers (country + name word, same web domain).
The time is that of the embedding blocker on our CPU, model loading and embedding included.

Final run (cleaned data):

| Model | Text | Wikidata–ROR pairs | PC | PC in union | Time | DEQAR–ROR pairs | PC | PC in union | Time |
|---|---|---|---|---|---|---|---|---|---|
| **English (PyDI default, used)** | **name** | **191,828** | **0.838** | **0.993** | **65 s** | **65,725** | **0.789** | **0.987** | **41 s** |
| English | name + city + country | 194,205 | 0.915 | 1.0 | 75 s | 66,959 | 0.849 | 0.993 | 50 s |
| multilingual | name | 195,893 | 0.789 | 0.993 | 92 s | 67,574 | 0.783 | 0.987 | 67 s |
| multilingual | name + city + country | 195,924 | 0.923 | 1.0 | 118 s | 67,599 | 0.882 | 0.993 | 82 s |

First pass (sources as downloaded):

| Model | Text | Wikidata–ROR pairs | PC | PC in union | Time | DEQAR–ROR pairs | PC | PC in union | Time |
|---|---|---|---|---|---|---|---|---|---|
| **English (PyDI default, used)** | **name** | **220,647** | **0.838** | **0.993** | **138 s** | **87,153** | **0.789** | **0.987** | **51 s** |
| English | name + city + country | 224,549 | 0.915 | 1.0 | 97 s | 88,735 | 0.842 | 0.993 | 62 s |
| multilingual | name | 226,821 | 0.789 | 0.993 | 125 s | 89,690 | 0.783 | 0.987 | 83 s |
| multilingual | name + city + country | 226,820 | 0.923 | 1.0 | 138 s | 89,751 | 0.882 | 0.993 | 101 s |

- The rows in bold are the pipeline's blocker. They reproduce the report's blocking table exactly
  (candidate pairs, PC and union), in both runs.
- The PC values hardly differ between the runs, as the labelled pairs hold only records that survive the
  cleaning. The first-pass row in bold took longer than the others because it was the first model the
  script loaded.
- **The multilingual model keeps fewer matches on its own** (0.789 against 0.838 for Wikidata–ROR) and
  **exactly the same matches in the union**: no validation match is kept by one union and missed by the
  other (`results/multilingual_only_matches.csv` is empty).
- It takes 1.4 to 1.6 times as long in the final run.
- **The text matters more than the model.** Embedding name, city and country keeps 0.915 instead of
  0.838 on its own, and in the union every Wikidata–ROR validation match (1.0) and 151 of the 152
  DEQAR–ROR ones (0.993), one match more per dataset pair than the pipeline. We found this after the
  pipeline had run. Using it would mean new candidate pairs and scoring them again with all nine
  approaches (the fine-tuned model alone takes about two hours on our CPU), for one match per 150, so we
  kept the pipeline as it is.
- The pipeline logged 7,169 s for the English embedding blocker in the final run (report, blocking
  table). Here the same code on the same data and the same CPU took 65 s, so the two hours came from that
  run, not from the blocker.

**Why we dropped it.** In the union the multilingual model keeps exactly the same matches as the English
one, on its own it keeps fewer, and it is slower.

```
python scripts/06_abandoned_approaches/04_identity_resolution/multilingual_blocking.py   # about 25 minutes on our CPU
```
