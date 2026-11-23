# Approaches we tried

Everything we tried on the way to the final pipeline, in the order we tried it: the idea, what
happened and what we decided. The final pipeline itself is in `scripts/` (see the root `README.md`).
Approaches that are not part of it keep their code here, **archived as it was**: the paths inside
still point to the old folder layout, so these scripts are documentation, not meant to be re-run.
The journal `IDENTITY_RESOLUTION_REASONING.txt` (repo root) has the full numbers.

| # | Approach | Result | Decision | Code |
|---|---|---|---|---|
| 1 | First version: labels taken straight from the ID links, unchecked | F1 96-99%, but only because the test pairs were easy | dropped | commit `6679e95` (`data/gold_standard/`, `results/matching_experiments.csv`) |
| 2 | Round 1: labelled pairs = ID links + random non-matches | precision 1.000 for every matcher, 133,694 links for 22,697 records | dropped | `scripts/03_identity_resolution/01_labels` (round 1) |
| 3 | Round 2: checked labels with 50% corner cases | honest evaluation (F1 0.93-0.94 on test) | **kept** | `scripts/03_identity_resolution/01_labels` |
| 4 | Blocking: standard keys, sorted neighbourhood, tokens, domain, embedding, union | union of country + name word, domain and embedding keeps 97-99% of matches | **union kept** | `scripts/03_identity_resolution/02_blocking` |
| 5 | Matchers: one name measure, rules, learned (LR, RF, GB) | learned matchers best (F1 0.95-0.97 on validation) | **learned kept** | `03_rule_based`, `04_ml_based` |
| 6 | Global matching: none, greedy one-to-one, stable, maximum bipartite | "none" looked best on 300 pairs but built groups of 4,509 records | **greedy kept** | `05_final` |
| 7 | Round 3: translate common words, "part word" feature (campus, faculty) | F1 change below 0.007 | kept in the features, no effect | `scripts/03_identity_resolution/common.py` |
| 8 | Rounds 4-6: hand-check lists of non-universities, removed before (4) or after (5) matching, duplicates before (6) | before: 76 new links of 78 records whose partner was removed (orphans), most of the checked ones wrong; after: 383 links gone, no new errors, but the records stay in the data | dropped for the final pipeline | `rounds_4-6_filter_before_or_after_matching/` |
| 9 | Round 7: flag, match, remove flagged records, match again | no gain over matching once (test F1 -0.007 / +0.007) | dropped | `round_7_flag_match_remove_rematch/` |
| 10 | Cleaning ROR through the Wikidata ID links (a ROR record goes if its Wikidata partner was removed) | worked, but uses the ID links, which are our answer key | dropped (not allowed) | `ror_cleaning_via_id_links/` |
| 11 | Wikidata parent links (P361 / P749) to find parts of universities | no better than a name rule; would need a new download | dropped | none kept |
| 12 | DEQAR ETER identifier as a sign of a real university | ETER ids also on alliances, nursing schools, academy institutes | dropped | none kept |
| 13 | Round 8: clean every source with five fixed rules before schema mapping and matching | 1-2% of removed records are real universities, 8-15% of kept ones still are not; test scores do not drop; 1,628 links to removed records gone | **kept** | `scripts/02_filtering`, `rules.md` |
| 14 | Stricter final cut-off (0.45 / 0.35 up to 0.9) | 0.7 / 0.55: 42% / 38% fewer wrong links (ID links), 2-3% of right links lost | **0.7 / 0.55 kept** | `scripts/03_identity_resolution/05_final/cutoff_check.py` |
| 15 | More name rules on the junk that is left (e.g. "only in ROR and no higher-education word") | e.g. dropping the ROR-only entries without a higher-education word would remove 1,461 non-universities but also 2,729 universities (LLM check of all fused entries) | dropped: name rules are at their limit | recount: `scripts/05_checks/report_numbers.py` |
| 16 | Fusion: content-based, voting, trust (ROR or Wikidata first), voting with ties by trust (ours) | ROR first 98.5%; voting with ties by trust 98.6% (fixes 1 name and 2 country codes, breaks none) | **ties by trust for name and country code, ROR first otherwise** | `scripts/04_data_fusion/fusion.py` |

Not tried: an LLM matcher (needs a paid API) and character 3-gram blocking (2.1 billion candidate pairs).

## Folders

### `rounds_4-6_filter_before_or_after_matching/`
The first answer to "the matcher links campuses and schools to universities". Per source,
`additional_filtering/<source>/filter.py` flagged candidates by words and types, an AI pre-check
judged each flag (`hand_check.csv`, column `university`), `duplicates.py` found duplicate candidates
(`duplicate_check.csv`, partly through the ID links) and `apply.py` wrote filtered copies of the
data. Round 4 matched the filtered data: a record removed in one source left its counterpart without
partner, and the matcher linked it to something wrong (76 new links, e.g. the Wikidata record of the
branch "Islamic Azad University of Nishapur" to "Neyshabur University of Medical Sciences"). Rounds 5
and 6 removed the links to non-universities after matching instead (383 links gone, no new errors).
`compare_filtering.py` produced `results/filtering_effect.csv`. The hand check of the lists was never
done; the large filtered CSV/XML copies are not kept (they were outputs of `apply.py`).

### `round_7_flag_match_remove_rematch/`
`flag_filter.py` took the records the Wikidata filter flagged (`results/wikidata_flagged.csv`),
carried the flags over to ROR and DEQAR through links with a score of at least 0.9 from a first
matching run, removed all flagged records and matched again; `compare.py` compared the result with
matching once (`results/compare.csv`, removed records in `results/removed.csv`). No gain.

### `ror_cleaning_via_id_links/`
An early version of the ROR filter (commit 6663086): a ROR record was removed when its one-to-one ID
partner in Wikidata had been removed by the Wikidata rules. The ID links are the answer key of
identity resolution and must not be used inside the pipeline, so the final ROR filter uses only ROR's
own names and types.
