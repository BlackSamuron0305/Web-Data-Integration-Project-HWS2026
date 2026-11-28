# Step 3: Schema mapping

This step translates the three sources into one common XML format, so identity resolution and fusion
can treat them alike. We built one MapForce mapping per source.

## What we did

**Target schema (`target.xsd`).** One class, *institution*, with an ID and 21 attributes. No source has
all attributes, so every attribute is optional. The ID keeps the source and its key
(`ror_00003ef66`), so every record can be traced back to where it came from.

| Attributes | In which sources |
|---|---|
| name, alternative names, country, country code, city, website, domains, founding year | all three |
| acronyms, latitude, longitude | Wikidata, ROR |
| parent institutions | ROR, DEQAR |
| institution types, memberships, students | Wikidata only |
| region, status | ROR only |
| closure year, history, QA reports, last QA report | DEQAR only |

Twelve attributes are in at least two sources, which is what matching and fusion need.

**The mappings (`<source>/original/*_Mapping.mfd`).** Each one turns the source CSV into XML using a
small library of our own functions (`functions.mfd`):

- lists (alternative names, acronyms, domains, ...) are split at `|` and trimmed;
- names and countries keep the source spelling; matching cleans them later;
- a domain function turns `https://www2.unesp.br/` into `unesp.br`, for Wikidata, DEQAR and the 13,470
  ROR records that have a website but no domain; domains are lower-cased;
- DEQAR has country names but no codes: a lookup table of 135 country names (12 set by hand) adds them;
- ROR gives parents as ROR ids: a lookup table replaces them by names, except for the 20% of parents
  outside our data.

`build_lookup_tables.py` builds the two lookup tables (`ror/ror_names.csv`, `deqar/country_codes.csv`)
from the downloaded CSV files.

**Two runs.** `<source>/original/` maps the downloaded data (the first matching pass);
`<source>/filtered/` maps the cleaned data from step 2 with the same mapping
(`*_Mapping_filtered.mfd`). The filtered XML is the input of identity resolution and fusion.

## What did not work at first, and how we fixed it

Our first MapForce attempt had several errors, so we rebuilt the mappings and checked their output by
hand until it was correct:

- names were lower-cased, stray spaces stayed, some lists were not split, and the parent institutions
  were lost;
- MapForce could not read list items of the generic `xs:any` type; after defining the list items in the
  schema and mapping values directly to them, they appeared in the XML;
- a filter against empty groups such as `<web/>` checked only one field and deleted whole groups with
  founding years and websites in them;
- the domain function removed `www.` anywhere in the text (`wwww.meduniv.lviv.ua` became
  `wmeduniv.lviv.ua`), so we rebuilt it.

## How we checked it

We checked the output files by hand until they were correct. They pass schema validation and have no
stray spaces or unsplit lists.

Lessons and known issues:

- A valid file is not necessarily a correct one: the files that lost founding years and websites were
  valid XML.
- A field with several cities or countries stays one text value, because the schema allows one of each
  (587 city and 102 country fields in Wikidata, 23 DEQAR records).
- Namibia lost its country code `NA` in the cleaned files, because pandas reads "NA" as a missing value. We
  found it in the output and fixed it (the filters now read only empty cells as missing) and regenerated the XML.

## Files and how to run

| File | What it is |
|---|---|
| `target.xsd` | the target schema |
| `functions.mfd` | the functions the three mappings share |
| `<source>/original/*_Mapping.mfd`, `*_Mapping.xml` | mapping of the downloaded data and its output |
| `<source>/filtered/*_Mapping_filtered.mfd`, `*_Mapping.xml` | mapping of the cleaned data and its output |
| `ror/ror_names.csv`, `deqar/country_codes.csv` | the lookup tables |
| `build_lookup_tables.py` | builds the lookup tables |

```
python build_lookup_tables.py
```

then open each `.mfd` in MapForce and run it. For the final pipeline only the three
`*_Mapping_filtered.mfd` are needed.
