"""Proef: vindt zoeken in de tekst (cql.textAndIndexes) de stukken die zoeken in de titel mist? Live tegen de SRU van
KOOP, zonder model of graaf. Draaien: `uv run python -I proef.py` vanuit tools/graph-qa. Uitkomst: README.md ernaast."""
import re, sys, httpx
B='c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk'
DOEL={"kst-32740-1-n1","kst-33004-3","kst-33402-61","kst-33754-7","kst-31066-192","kst-31066-202","kst-31066-203","kst-31066-246"}
def q(cql, n=100):
    x=httpx.get("https://repository.overheid.nl/sru",params={"query":cql,"maximumRecords":n},timeout=60).text
    tot=re.findall(r"<sru:numberOfRecords>(\d+)",x); d=re.findall(r"message>([^<]*)",x)
    ids=[re.findall(r"identifier>([^<]*)",r)[0] for r in re.findall(r"<sru:record>.*?</sru:record>",x,re.S)]
    return (tot[0] if tot else "?"), d[:1], ids
for naam,cql in [
 ("titel any een bankrekeningnummer", B+' AND dt.title all "bankrekeningnummer"'),
 ("tekst = \"één bankrekeningnummer\"", B+' AND cql.textAndIndexes="één bankrekeningnummer"'),
 ("tekst adj één bankrekeningnummer", B+' AND cql.textAndIndexes adj "één bankrekeningnummer"'),
 ("tekst all één bankrekeningnummer", B+' AND cql.textAndIndexes all "één bankrekeningnummer"'),
 ("tekst = \"één rekeningnummer\"", B+' AND cql.textAndIndexes="één rekeningnummer"'),
 ("tekst all uitbetaling bankrekeningnummer toeslagen", B+' AND cql.textAndIndexes all "uitbetaling bankrekeningnummer toeslagen"'),
 ("tekst POBR1", B+' AND cql.textAndIndexes=POBR1'),
 ("tekst all fiscale agenda bankrekeningnummer", B+' AND cql.textAndIndexes all "fiscale agenda bankrekeningnummer"'),
 ("tekst adj één bankrekeningnummer + 2011-2016 oudste", B+' AND cql.textAndIndexes adj "één bankrekeningnummer" AND dt.date>=2011-01-01 AND dt.date<=2016-12-31 sortBy dt.date/sort.ascending dt.identifier/sort.ascending'),
]:
    tot,d,ids=q(cql)
    pos={i:ids.index(i)+1 for i in DOEL if i in ids}
    print(f"{naam:55} N={tot} {d} gevonden={len(pos)}/{len(DOEL)} {sorted(pos.items(), key=lambda x:x[1])}")
