# Results of an earlier version, kept for the report

`group_sizes_early_version.csv`: group size distribution of an early version of `final.py` (git commit
14daf45, file `scripts/03_identity_resolution/05_final/results/group_sizes_r2.csv`). That version picked
the global matching with the best validation F1 and so used no one-to-one matching for DEQAR–ROR; one
group held 4,509 records. Since then `final.py` always uses greedy one-to-one matching. The current code
cannot produce this file any more, so it is kept here as it was.
