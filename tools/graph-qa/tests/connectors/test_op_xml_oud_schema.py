"""Het oude schema van KOOP (rond 2005) in `agent/tools/op_xml.py`.

In ronde 1 van de Kamerstukken-iteratie (11 nov 2026) kregen de 210 alinea's van kst-30322-3 geen kop. Het stuk zet zijn
tussenkoppen in `<tuskop>`, en daardoor gaf `inhoud: true` 0 rijen; K07 en K16 kostten samen 1,47M tokens. Het Staatsblad
uit die tijd heeft de wortel `staatsbl` en de koppen `art`, `wart`, `wlid` en een `lid` met `nr`. De fragmenten hieronder
volgen kst-30322-3 en stb-2004-700, ingekort.
"""
from __future__ import annotations

from agent.tools.op_xml import lees

KAMERWRK = """<?xml version="1.0" encoding="utf-8"?>
<kamerwrk kamer="2" publtype="meto">
  <kop><titel>Tweede Kamer der Staten-Generaal</titel></kop>
  <frontm><onderw><nummer>30 322</nummer><naam>Versterking fiscale rechtshandhaving</naam></onderw></frontm>
  <body><stuk>
    <ltrlabel>Nr. </ltrlabel><nummer>3</nummer>
    <titel>MEMORIE VAN TOELICHTING</titel>
    <tuskop letat="vet">ALGEMEEN</tuskop>
    <tuskop letat="vet">1. Inleiding</tuskop>
    <al>In de brief van 3 juni 2004 is een pakket maatregelen aangekondigd.</al>
    <witreg></witreg>
    <al>Voor dat onderzoek is de Belastingdienst gevraagd.</al>
    <tuskop letat="vet">Leeswijzer</tuskop>
    <al>In hoofdstuk 2 worden de resultaten weergegeven.</al>
  </stuk></body>
</kamerwrk>""".encode()

STAATSBL = """<?xml version="1.0" encoding="utf-8"?>
<staatsbl publtype="stbl" soort="wetwijz">
  <kop><titel status="off">Staatsblad</titel></kop>
  <frontm>
    <stb><stbjaar>2004</stbjaar><stbnr>700</stbnr></stb>
    <intitule><soort>Wet</soort></intitule>
    <aanhef><wie>Wij Beatrix</wie><consider><al>Alzo Wij in overweging genomen hebben</al></consider>
      <afkondig>Zo is het, dat Wij goedvinden en verstaan:</afkondig></aanhef>
  </frontm>
  <body>
    <wart id="a1">
      <kop><nr>ARTIKEL I</nr></kop>
      <al>De Wet op de jeugdzorg wordt als volgt gewijzigd:</al>
      <wlid><kop><nr>A</nr></kop><al>In artikel 2 wordt ingevoegd: en de rechter.</al></wlid>
      <wlid><kop><nr>B</nr></kop><al>Artikel 10 wordt als volgt gewijzigd:</al>
        <wond><nr>1.</nr><al>In het eerste lid vervalt de zinsnede.</al></wond></wlid>
    </wart>
    <art>
      <kop><nr>ARTIKEL II</nr></kop>
      <lid><nr>1.</nr><al>Deze wet treedt in werking met ingang van 1 januari 2005.</al></lid>
      <lid><nr>2.</nr><al>In afwijking van het eerste lid geldt artikel I, onderdeel B, later.</al></lid>
    </art>
  </body>
  <backm><nawerk><slotform>Lasten en bevelen dat deze in het Staatsblad zal worden geplaatst.</slotform>
    <ondertek><gegeven>Gegeven te</gegeven><koning>Beatrix</koning></ondertek></nawerk></backm>
</staatsbl>""".encode()


def test_een_tuskop_is_een_tussenkop():
    kop, rijen, _, _ = lees(KAMERWRK)
    assert kop == {"documenttitel": "MEMORIE VAN TOELICHTING"}
    assert [(r.get("kop"), r["tekst"][:12]) for r in rijen] == [
        ("1. Inleiding", "In de brief "), ("1. Inleiding", "Voor dat ond"), ("Leeswijzer", "In hoofdstuk")]


def test_een_oud_staatsblad_heeft_artikelen_leden_en_onderdelen():
    _, rijen, overgeslagen, _ = lees(STAATSBL, met_onderdeel=True)
    paren = [(r.get("kop"), r["tekst"]) for r in rijen]
    assert paren[:3] == [(None, "Wij Beatrix"), (None, "Alzo Wij in overweging genomen hebben"),
                         (None, "Zo is het, dat Wij goedvinden en verstaan:")], "de aanhef, met de afkondiging"
    assert ("Artikel I", "De Wet op de jeugdzorg wordt als volgt gewijzigd:") in paren, "ARTIKEL I krijgt een beginhoofdletter"
    assert ("Artikel I › B", "1. In het eerste lid vervalt de zinsnede.") in paren, "een wlid is een onderdeel"
    assert {r["onderdeel"] for r in rijen if r.get("kop", "").startswith("Artikel I ›")} == {"Artikel I › A", "Artikel I › B"}
    assert ("Artikel II › lid 1", "Deze wet treedt in werking met ingang van 1 januari 2005.") in paren, \
        "het nummer van een lid staat in de kop en niet nog eens vóór de tekst"
    assert paren[-1] == (None, "Lasten en bevelen dat deze in het Staatsblad zal worden geplaatst.")
    assert overgeslagen == {"ondertekening": 1}
