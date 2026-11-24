# Step 1: Data collection

We download three open sources about universities and save each one unchanged as a CSV file in
`data/<source>/original/`. The later steps never change these files.

## What we did

| Source | Where from | What we kept | Records |
|---|---|---|---|
| Wikidata | SPARQL endpoint `query.wikidata.org` | every item that is a *university* (Q3918) or one of its subclasses | 22,697 |
| ROR | data dump v2.13 on Zenodo | records whose types include *education* and that are not withdrawn (of 141,528) | 30,131 |
| DEQAR | nightly CSV from `eqar.eu` | all higher-education institutions; rows that repeat one institution per location merged into one | 8,979 |

## Why these three

- They are kept up by different people (volunteers, a curation team, quality assurance agencies), so
  they really are independent sources.
- Together they cover the whole world, and they overlap enough to match: many Wikidata and DEQAR
  records already name their ROR record.
- Each adds something the others lack: Wikidata the institution types, student numbers and
  memberships; ROR regions and status (active or not); DEQAR the quality assurance reports, closure
  years and histories.

## What worked and what did not

- Downloading by the class *university* was simple and gave records that at least claim to be a
  university. The price: universities that Wikidata types differently (a *liberal arts college*, a
  *grande école*) are missing. We later tried the wider class *higher education institution*; it would
  have added about 46,000 non-universities for about 7,000 universities, so we dropped it (see
  `scripts/06_abandoned_approaches/`).
- None of the sources holds only universities. ROR's *education* also has schools, school districts and
  hospitals, DEQAR lists faculties and vocational centres, and Wikidata's subclasses include seminaries
  and Japanese junior colleges. We kept everything here and remove it in step 2, with written rules.

## Files and how to run

| File | What it does |
|---|---|
| `fetch_wikidata.py` | queries Wikidata and writes `data/wikidata/original/wikidata_universities.csv` |
| `fetch_ror.py` | downloads the ROR dump (or reads a given zip) and writes `data/ror/original/ror_education.csv` |
| `fetch_deqar.py` | downloads the DEQAR list (or reads a given CSV) and writes `data/deqar/original/deqar_institutions.csv` |
| `common.py` | helpers shared by the three scripts |

```
python fetch_wikidata.py
python fetch_ror.py   [path/to/ror-data.zip]
python fetch_deqar.py [path/to/deqar-institutions.csv]
```

The downloads from October 2026 are already in `data/`, so this step only needs to run again for new
data. Wikidata changes daily, so a new download gives slightly different numbers.
