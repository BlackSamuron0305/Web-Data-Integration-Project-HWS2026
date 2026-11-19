# Rules: which records stay

Scope: recognized higher education institutions that primarily award
bachelor's degrees or higher (ISCED 6-8), including specialized and
applied-science institutions.

A record stays only if it passes every rule below.

## Rule 1: It is a higher education institution

It awards degrees at bachelor's level or higher (ISCED 6-8).

Stays:
- universities (public and private)
- universities of applied sciences (Fachhochschule, Hochschule, hogeschool)
- polytechnics
- art academies
- music academies and conservatories
- other specialized institutions at bachelor's level or higher (for example
  medical, technical, business or sports universities)

Goes:
- community colleges
- junior colleges
- seminaries and theological schools
- vocational and technical schools below bachelor's level
- high schools and secondary schools
- primary schools, kindergartens and language schools

## Rule 2: It is recognized

It is officially recognized as a higher education institution.

- DEQAR: always passes, because every record has been through an external
  quality review.
- Wikidata and ROR: there is no recognition field, so a record passes if it
  passes Rule 1 by its type or name and is not on the exclusion list.

## Rule 3: It is an organisation of its own

Goes:
- faculties, schools and departments inside a university
- campuses and branches of a university
- institutes, centres and labs that belong to a university

A record with a parent institution (`parent_ror_id` in ROR,
`parent_institutions` in DEQAR) is checked against this rule.

## Rule 4: Its main purpose is education

Goes:
- research institutes that do not award degrees
- hospitals, including university hospitals
- libraries, museums and archives
- associations, networks and consortia of universities
- companies, publishers and government agencies

## Rule 5: It appears only once in its own source

If one source holds two records for the same institution, the duplicate goes
and one record stays.

- Two records are the same institution if they have the same cleaned name, the
  same country and the same website domain.
- The location is ignored: the same name, country and domain in two different
  cities is still one institution (the city is often written once as the town
  and once as the region, or one record is a campus).
- The same name with a different domain is two institutions (for example
  Wheaton College in Illinois and Wheaton College in Massachusetts).
- A record without a website or without a country is never a duplicate.
- The record with the most filled fields stays; on a tie, the older record
  (lower id) stays.

## How the rules are applied

- Every rule is a fixed condition: if it matches, the record goes, every time.
  There are no case-by-case decisions and no review lists.
- The rules run in order 1 to 5; the first rule that matches decides.
- Each source has one script in `scripts/filtering/<source>/` that writes one
  cleaned dataset and one list of removed records with rule and reason.

## Open

- Active or closed: not decided yet. Closed and inactive records stay for now.
