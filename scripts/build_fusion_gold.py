"""Builds the gold standard for data fusion: 45 well-known universities that are contained in
all three datasets, with the expected value of five attributes.

The expected values were compiled by hand from general knowledge of the institutions
(commonly cited founding year, English and official local name, city, main web domain);
they are not taken from one of the three sources. The anchor is the ROR record of the
university, the group of records that describe it in the three datasets comes from the
correspondences of Phase II.

Run (after phase2_final.py): python scripts/build_fusion_gold.py
"""
import pandas as pd

from common import DATA, load_target, norm_text
from phase3_fusion import PAIRS, constrained_groups

# query name in ROR, country code, city, other accepted spellings of the city, founding year,
# main domain, other accepted domains, other accepted names
GOLD = [
    ("University of Vienna", "AT", "Vienna", "Wien", 1365, "univie.ac.at", "", "Universität Wien"),
    ("Heidelberg University", "DE", "Heidelberg", "", 1386, "uni-heidelberg.de", "",
     "Universität Heidelberg|University of Heidelberg|Ruprecht-Karls-Universität Heidelberg"),
    ("Technical University of Munich", "DE", "Munich", "München", 1868, "tum.de", "", "Technische Universität München"),
    ("University of Bologna", "IT", "Bologna", "", 1088, "unibo.it", "", "Università di Bologna|Alma Mater Studiorum University of Bologna"),
    ("Charles University", "CZ", "Prague", "Praha", 1348, "cuni.cz", "", "Univerzita Karlova"),
    ("Uppsala University", "SE", "Uppsala", "", 1477, "uu.se", "", "Uppsala universitet"),
    ("University of Copenhagen", "DK", "Copenhagen", "København|Kobenhavn", 1479, "ku.dk", "", "Københavns Universitet"),
    ("University of Oslo", "NO", "Oslo", "", 1811, "uio.no", "", "Universitetet i Oslo"),
    ("ETH Zurich", "CH", "Zurich", "Zürich", 1855, "ethz.ch", "", "Swiss Federal Institute of Technology in Zurich|Eidgenössische Technische Hochschule Zürich"),
    ("University of Zurich", "CH", "Zurich", "Zürich", 1833, "uzh.ch", "", "Universität Zürich"),
    ("Leiden University", "NL", "Leiden", "", 1575, "universiteitleiden.nl", "leidenuniv.nl", "Universiteit Leiden"),
    ("University of Amsterdam", "NL", "Amsterdam", "", 1632, "uva.nl", "", "Universiteit van Amsterdam"),
    ("Trinity College Dublin", "IE", "Dublin", "", 1592, "tcd.ie", "", "University of Dublin"),
    ("University of Helsinki", "FI", "Helsinki", "", 1640, "helsinki.fi", "", "Helsingin yliopisto"),
    ("Jagiellonian University", "PL", "Kraków", "Krakow|Cracow", 1364, "uj.edu.pl", "", "Uniwersytet Jagielloński"),
    ("University of Warsaw", "PL", "Warsaw", "Warszawa", 1816, "uw.edu.pl", "", "Uniwersytet Warszawski"),
    ("Lund University", "SE", "Lund", "", 1666, "lu.se", "", "Lunds universitet"),
    ("University of Barcelona", "ES", "Barcelona", "", 1450, "ub.edu", "", "Universitat de Barcelona"),
    ("University of Lisbon", "PT", "Lisbon", "Lisboa", 1290, "ulisboa.pt", "ul.pt", "Universidade de Lisboa"),
    ("National and Kapodistrian University of Athens", "GR", "Athens", "Athina", 1837, "uoa.gr", "", "University of Athens"),
    ("Masaryk University", "CZ", "Brno", "", 1919, "muni.cz", "", "Masarykova univerzita"),
    ("University of Tartu", "EE", "Tartu", "", 1632, "ut.ee", "", "Tartu Ülikool"),
    ("Vilnius University", "LT", "Vilnius", "", 1579, "vu.lt", "", "Vilniaus universitetas"),
    ("University of Ljubljana", "SI", "Ljubljana", "", 1919, "uni-lj.si", "", "Univerza v Ljubljani"),
    ("University of Zagreb", "HR", "Zagreb", "", 1669, "unizg.hr", "", "Sveučilište u Zagrebu"),
    ("Eötvös Loránd University", "HU", "Budapest", "", 1635, "elte.hu", "", "Eötvös Loránd Tudományegyetem"),
    ("University of Padua", "IT", "Padua", "Padova", 1222, "unipd.it", "", "Università degli Studi di Padova"),
    ("Polytechnic University of Milan", "IT", "Milan", "Milano", 1863, "polimi.it", "", "Politecnico di Milano"),
    ("Humboldt University of Berlin", "DE", "Berlin", "", 1810, "hu-berlin.de", "", "Humboldt-Universität zu Berlin"),
    ("Ludwig-Maximilians-Universität München", "DE", "Munich", "München", 1472, "lmu.de", "uni-muenchen.de",
     "LMU Munich|University of Munich|Ludwig Maximilian University of Munich"),
    ("Aarhus University", "DK", "Aarhus", "Århus", 1928, "au.dk", "", "Aarhus Universitet"),
    ("Ghent University", "BE", "Ghent", "Gent", 1817, "ugent.be", "", "Universiteit Gent"),
    ("Delft University of Technology", "NL", "Delft", "", 1842, "tudelft.nl", "", "Technische Universiteit Delft"),
    ("University of Cambridge", "GB", "Cambridge", "", 1209, "cam.ac.uk", "", ""),
    ("Sapienza University of Rome", "IT", "Rome", "Roma", 1303, "uniroma1.it", "", "Sapienza Università di Roma|La Sapienza"),
    ("TU Wien", "AT", "Vienna", "Wien", 1815, "tuwien.ac.at", "tuwien.at",
     "Technische Universität Wien|Vienna University of Technology"),
    ("University of Graz", "AT", "Graz", "", 1585, "uni-graz.at", "", "Universität Graz"),
    ("University of Innsbruck", "AT", "Innsbruck", "", 1669, "uibk.ac.at", "", "Universität Innsbruck"),
    ("Utrecht University", "NL", "Utrecht", "", 1636, "uu.nl", "", "Universiteit Utrecht"),
    ("University of Groningen", "NL", "Groningen", "", 1614, "rug.nl", "", "Rijksuniversiteit Groningen"),
    ("Stockholm University", "SE", "Stockholm", "", 1878, "su.se", "", "Stockholms universitet"),
    ("University of Gothenburg", "SE", "Gothenburg", "Göteborg", 1891, "gu.se", "", "Göteborgs universitet"),
    ("University of Bergen", "NO", "Bergen", "", 1946, "uib.no", "", "Universitetet i Bergen"),
    ("University of Turku", "FI", "Turku", "", 1920, "utu.fi", "", "Turun yliopisto"),
]


def main():
    data = load_target()
    corrs = pd.concat([pd.read_csv(DATA / "correspondences" / f"corr_{a}_{b}.csv") for a, b in PAIRS])
    accepted, _ = constrained_groups(corrs)
    partner = {}
    for r in accepted.itertuples(index=False):
        partner.setdefault(r.id1, set()).add(r.id2)
        partner.setdefault(r.id2, set()).add(r.id1)
    ror = data["ror"]
    rows, missing = [], []
    for name, cc, city, city_alt, year, domain, dom_alt, name_alt in GOLD:
        hits = ror[(ror["name_norm"] == norm_text(name)) & (ror["country_code"] == cc)]
        anchor = None
        for rid in hits["id"]:
            members, todo = {rid}, [rid]
            while todo:
                for p in partner.get(todo.pop(), ()):
                    if p not in members:
                        members.add(p)
                        todo.append(p)
            if {m.split("_", 1)[0] for m in members} == {"wikidata", "ror", "deqar"}:
                anchor = rid
        if anchor is None:
            missing.append(name)
            continue
        rows.append(dict(anchor_id=anchor, name=name, name_alternatives=name_alt, country_code=cc, city=city,
                         city_alternatives=city_alt, founding_year=year, domain=domain,
                         domain_alternatives=dom_alt))
    pd.DataFrame(rows).to_csv(DATA / "gold_standard" / "fusion_gold.csv", index=False)
    print(len(rows), "entities;", "not in all three datasets:", missing)


if __name__ == "__main__":
    main()
