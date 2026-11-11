"""De tekst van een officiële publicatie van KOOP, per alinea (ADR-013): Kamerstukken, Staatsblad en Staatscourant.

Alle drie volgen hetzelfde schema (op-consolidated); alleen de wortel verschilt (`stuk`, `staatsblad`, `staatscourant`).
Daarom één lezer, voor elke leestool die een KOOP-publicatie leest. Wat er in staat:

- een alinea (`al`), een wijzigingsopdracht (`wat`: "In artikel 1.1.5 worden …"), een overweging (`considerans.al`),
  de aanhef (`wij`, `wie`) en de dagtekening, elk een rij met de kop erboven;
- een kop per divisie, artikel (`Artikel I – Wijziging`), lid (`lid 2`) en wijzigingsonderdeel (`A`); een nummer
  (`nr`, `li.nr`) staat vóór de tekst die erop volgt, zoals in de bron;
- voetnoten, CALS-tabellen en de eigen inhoudsopgave zoals bij Kamerstukken;
- illustraties en ondertekeningen tellen in `overgeslagen`: ze vallen nooit stil weg.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from bronmodel.extern import externe_vindplaats

from ..resultaat import compact

#: Elementen die geen lopende tekst zijn; ze worden geteld en genoemd, nooit stil weggelaten.
#: De XML van KOOP gebruikt CALS-tabellen (`table`): zonder die sleutel kwamen tabelcellen als losse alinea's mee, zoals
#: de inhoudsopgave en de cijfers van een budgettabel zonder hun kolommen (acceptatie 8 nov 2026: 43 van de 63 alinea's
#: van kst-33755-3).
_OVERGESLAGEN = {"tabel": "tabel", "table": "tabel", "illustratie": "illustratie", "noot": "voetnoot",
                 "ondertekening": "ondertekening", "koning": "ondertekening", "ondertek": "ondertekening"}
#: De wortel van een publicatie, per soort.
#: `staatsbl` is de wortel van een Staatsblad in het oude schema van KOOP (rond 2005; ronde 1 Kamerstukken, 11 nov 2026).
_WORTELS = ("stuk", "staatsblad", "staatscourant", "staatsbl")
#: Elementen waarvan de tekst een rij is.
#: `afkondig` en `slotform` zijn de afkondiging en de slotformule in het oude schema.
_TEKSTBLOK = {"al", "wat", "considerans.al", "wij", "wie", "dagtekening", "afkondig", "slotform"}
#: Elementen met een kop zoals een artikel: label, nr en titel.
#: `art` en `wart` zijn artikel en wijzigingsartikel in het oude schema (kop met alleen `nr`: "ARTIKEL I").
_ARTIKEL = {"artikel", "wijzig-artikel", "art", "wart"}
#: Een lid, of een wijzigingsonderdeel (`wijzig-lid`, oud `wlid`: kop met de letter).
_LID = {"lid", "wijzig-lid", "wlid"}
_ONDERDEEL = {"wijzig-lid", "wlid"}
#: Een tussenkop; oud `tuskop`.
_TUSSENKOP = {"tussenkop", "tuskop"}
_ROMEINS_RE = re.compile(r"[IVXLCDM]+|[A-Z]")


def _platte_tekst(e: ET.Element, overgeslagen: dict[str, int], noten: list[ET.Element] | None = None) -> str:
    """De tekst van een element zonder opmaak. Een voetnoot gaat naar `noten` (als die er is), anders telt hij mee in
    `overgeslagen`: hij hoort niet in de lopende tekst, maar valt ook niet stil weg."""
    delen: list[str] = [e.text or ""]
    for kind in e:
        if kind.tag == "noot" and noten is not None:
            noten.append(kind)
        elif kind.tag in _OVERGESLAGEN:
            overgeslagen[_OVERGESLAGEN[kind.tag]] = overgeslagen.get(_OVERGESLAGEN[kind.tag], 0) + 1
        else:
            delen.append(_platte_tekst(kind, overgeslagen, noten))
        delen.append(kind.tail or "")
    return "".join(delen)


def _voetnoot(noot: ET.Element) -> tuple[str, str, list[str]]:
    """(nummer, tekst, verwijst_naar) van een `<noot>`. Alleen een `extref soort="document"` met een geldige externe
    vindplaats wordt een verwijzing (Lex kan die met de leestool volgen); een URL blijft tekst."""
    nr = " ".join((noot.findtext("noot.nr") or "").split())
    delen = list(noot.iter("noot.al")) or [k for k in noot if k.tag != "noot.nr"]
    tekst = " ".join(" ".join(_platte_tekst(a, {}).split()) for a in delen).strip()
    naar: list[str] = []
    for ref in noot.iter("extref"):
        vp = externe_vindplaats(ref.get("doc") or "") if ref.get("soort") == "document" else None
        if vp is not None and vp.id not in naar:
            naar.append(vp.id)
    return nr, tekst, naar


def _is_inhoudsopgave(tabel: ET.Element) -> bool:
    """De eigen inhoudsopgave van een stuk: een tabel zonder titel die met de cel "Inhoudsopgave" begint. Ze telt apart:
    `inhoud` doet hetzelfde werk, en haar regels zijn geen tekst van het stuk."""
    if tabel.find("title") is not None:
        return False
    eerste = next((" ".join(_platte_tekst(a, {}).split()) for a in tabel.iter("al")), "")
    return eerste.lower() == "inhoudsopgave"


def _cals(tabel: ET.Element, noten: list[ET.Element]) -> tuple[list[str], list[list[str]], int]:
    """(kolomkoppen, rijen met cellen, aantal samengevoegde cellen) van een CALS-tabel, zoals KOOP ze schrijft.

    Een cel die meer kolommen beslaat (`namest`/`nameend`) staat in haar eerste kolom, de rest blijft leeg; een cel die
    meer rijen beslaat (`morerows`) staat alleen in haar eerste rij. Een weergavekeuze, geen herinterpretatie: elke
    waarde staat er letterlijk en één keer, en het aantal samengevoegde cellen zegt het resultaat. Noten in een cel gaan
    naar `noten` (de tabelnoten komen na de rijen)."""
    kolommen: list[str] = []
    rijen: list[list[str]] = []
    samen = 0
    for groep in tabel.iter("tgroup"):
        specs = [c for c in groep if c.tag == "colspec"]
        n = max(int(groep.get("cols") or 0), len(specs))
        index = {c.get("colname"): i for i, c in enumerate(specs) if c.get("colname")}

        def rij_van(rij: ET.Element) -> list[str]:
            nonlocal samen
            cellen, vrij = [""] * n, 0
            for cel in (e for e in rij if e.tag == "entry"):
                begin = index.get(cel.get("namest") or cel.get("colname") or "", vrij)
                eind = index.get(cel.get("nameend") or "", begin)
                if eind > begin or (cel.get("morerows") or "0") != "0":
                    samen += 1
                if begin < n:
                    cellen[begin] = " ".join(_platte_tekst(cel, {}, noten).split())
                vrij = eind + 1
            return cellen

        kop = [rij_van(r) for d in groep if d.tag == "thead" for r in d if r.tag == "row"]
        if kop and not kolommen:
            kolommen = [" ".join(c for c in kolom if c) for kolom in zip(*kop)]
        rijen += [c for d in groep if d.tag == "tbody" for r in d if r.tag == "row" if any(c := rij_van(r))]
    return kolommen, rijen, samen


def _zacht(woord: str) -> str:
    """"ARTIKEL" → "Artikel", "WIJZIGING" → "Wijziging"; een Romeins cijfer of één letter blijft staan."""
    if woord.isupper() and len(woord) > 1 and not _ROMEINS_RE.fullmatch(woord):
        return woord[:1] + woord[1:].lower()
    return woord


def alineas(xml: bytes) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, int]]:
    """(kop van het stuk, rijen in documentvolgorde, overgeslagen per soort) uit de XML van een Kamerstuk."""
    kop, rijen, overgeslagen, _ = lees(xml)
    return kop, rijen, overgeslagen


def lees(xml: bytes, *, met_onderdeel: bool = False) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, int], dict[int, tuple[list[dict[str, Any]], int]]]:
    """(kop van het stuk, rijen in documentvolgorde, overgeslagen per soort, tabellen) uit de XML van een officiële publicatie.

    Een rij is een alinea, of een voetnoot direct na de alinea waar hij in staat (`soort: "voetnoot"`, met `noot` en
    `verwijst_naar`); de alinea zelf houdt haar letterlijke tekst en noemt haar noten (`noten`). Een tabel is één rij
    (`soort: "tabel"`, de titel als tekst, met de omvang); haar inhoud staat in `tabellen[nr]`: de kop (de titel met de
    kolommen als `cellen`), per tabelrij `{soort: "tabelrij", cellen, tekst}` en de tabelnoten, met het aantal
    samengevoegde cellen. Eén nummering per stuk (`nr`), want het blok `extern` voegt pagina's samen op `nr`.

    Met `met_onderdeel` draagt een rij in een wijzigingsonderdeel (`wijzig-lid`) het veld `onderdeel`: zo kiest een
    leestool de onderdelen die één artikel wijzigen."""
    root = ET.fromstring(xml)
    stuk = next((w for w in (root if root.tag in _WORTELS else None, *(root.find(f".//{n}") for n in _WORTELS))
                 if w is not None), None)
    if stuk is None:
        raise ValueError("geen stuk in het document")
    overgeslagen: dict[str, int] = {}
    uit: list[dict[str, Any]] = []
    tabellen: dict[int, tuple[list[dict[str, Any]], int]] = {}
    teller = [0]

    def volgende() -> int:
        teller[0] += 1
        return teller[0]

    def voetnootrijen(noten: list[ET.Element], kop: str) -> list[dict[str, Any]]:
        rijen: list[dict[str, Any]] = []
        for nr, ntekst, naar in (_voetnoot(n) for n in noten):
            if not ntekst:  # een lege noot valt niet stil weg
                overgeslagen["voetnoot"] = overgeslagen.get("voetnoot", 0) + 1
            else:
                rijen.append(compact({"nr": volgende(), "soort": "voetnoot", "noot": nr, "kop": kop, "tekst": ntekst,
                                      "verwijst_naar": naar}))
        return rijen

    def kop_van(divisie: ET.Element) -> str:
        kop = divisie.find("kop")
        if kop is None:
            return ""
        return " ".join(" ".join(_platte_tekst(k, {}).split()) for k in kop if k.tag in {"nr", "titel"}).strip()

    def artikelkop(artikel: ET.Element) -> str:
        """"Artikel I – Wijziging", "Enig artikel", "Artikel 2": label en nr, met de titel erachter. Een label of titel
        in hoofdletters ("ARTIKEL", "WIJZIGING") krijgt alleen een beginhoofdletter; een nummer blijft zoals het staat."""
        kop = artikel.find("kop")
        if kop is None:
            return ""
        deel = {k.tag: " ".join(_platte_tekst(k, {}).split()) for k in kop if k.tag in {"label", "nr", "titel"}}
        label, nr, titel = (_zacht(deel.get(t, "")) if t != "nr" else deel.get(t, "") for t in ("label", "nr", "titel"))
        # Het oude schema zet het hele label in `nr` ("ARTIKEL I", "ARTIKEL 12"): het woord krijgt een beginhoofdletter.
        nr = " ".join(_zacht(w) if i == 0 and len(nr.split()) > 1 else w for i, w in enumerate(nr.split()))
        hoofd = " ".join(x for x in (label, nr) if x)
        if titel:
            return f"{hoofd} – {titel}" if nr else f"{hoofd} {titel}".strip()
        return hoofd

    def lidnr(lid: ET.Element) -> ET.Element | None:
        """Het element met het nummer van een lid: `lidnr`, in het oude schema `kop/nr` (een `wlid`) of een `nr` als
        eerste kind (een `lid`)."""
        if (e := lid.find("lidnr")) is not None or (e := lid.find("kop/nr")) is not None:
            return e
        eerste = next(iter(lid), None)
        return eerste if eerste is not None and eerste.tag == "nr" else None

    def lidkop(lid: ET.Element) -> str:
        """"lid 2" bij een lid, de letter bij een wijzigingsonderdeel ("A")."""
        e = lidnr(lid)
        nr = " ".join(_platte_tekst(e, {}).split()) if e is not None else ""
        if not nr:
            return ""
        # "C." in de bron is onderdeel C: zonder punt in de kop ("Artikel XI › C", meting bekendmakingen B03).
        return nr.rstrip(".") if lid.tag in _ONDERDEEL else f"lid {nr.rstrip('.')}"

    def loop(e: ET.Element, koppen: tuple[str, ...], zonder: ET.Element | None = None) -> None:
        # Een `tussenkop` ("Artikel I (artikel 30hb …)") geldt voor de alinea's die erna komen in dezelfde divisie: in de
        # artikelsgewijze toelichting zegt juist die kop bij welk artikel een alinea hoort. Eerst viel hij stil weg.
        tussen, voor = "", ""
        for kind in e:
            if kind is zonder:
                continue
            hier = (*koppen, tussen) if tussen else koppen
            if kind.tag in {"table", "tabel"} and _is_inhoudsopgave(kind):
                overgeslagen["inhoudsopgave"] = overgeslagen.get("inhoudsopgave", 0) + 1
            elif kind.tag in {"table", "tabel"} and kind.find(".//tgroup") is not None:
                # Alleen een CALS-tabel (met `tgroup`) is te lezen als tabel; iets anders telt in `overgeslagen`.
                kop, nr, noten = " › ".join(hier), volgende(), []
                titel = (" ".join(_platte_tekst(kind.find("title"), {}).split()) if kind.find("title") is not None
                         else "") or "Tabel zonder titel"
                kolommen, cellen, samen = _cals(kind, noten)
                inhoud_t = [compact({"nr": nr, "soort": "tabel", "kop": kop, "tekst": titel, "cellen": kolommen})]
                inhoud_t += [{"nr": volgende(), "soort": "tabelrij", "cellen": c, "tekst": " | ".join(c)} for c in cellen]
                inhoud_t += voetnootrijen(noten, kop)
                tabellen[nr] = (inhoud_t, samen)
                breed = max([len(kolommen), *(len(c) for c in cellen)], default=0)
                # `tot_nr`: het laatste nr van de tabel; een passage over de tabel heen toont dan de titel, en wie de
                # rijen wil, opent de tabel.
                uit.append({"nr": nr, "soort": "tabel", **({"kop": kop} if kop else {}), "tekst": titel,
                            "tot_nr": teller[0],
                            "omvang": f"{len(cellen)} {'rij' if len(cellen) == 1 else 'rijen'}, {breed} "
                                      f"{'kolom' if breed == 1 else 'kolommen'}"})
            elif kind.tag in _OVERGESLAGEN:
                overgeslagen[_OVERGESLAGEN[kind.tag]] = overgeslagen.get(_OVERGESLAGEN[kind.tag], 0) + 1
            elif kind.tag in _TUSSENKOP:
                tussen = " ".join(_platte_tekst(kind, overgeslagen).split())
            elif kind.tag in {"divisie", "nota-toelichting"}:
                kop = kop_van(kind)
                loop(kind, (*hier, kop) if kop else hier)
            elif kind.tag in _ARTIKEL:
                kop = artikelkop(kind)
                loop(kind, (*hier, kop) if kop else hier)
            elif kind.tag in _LID:
                kop = lidkop(kind)
                begin = len(uit)
                # Het nummer staat al in de kop; in het oude schema is het een `nr`, dat anders vóór de tekst kwam.
                loop(kind, (*hier, kop) if kop else hier, zonder=lidnr(kind) if kop else None)
                if met_onderdeel and kind.tag in _ONDERDEEL:
                    # Het wijzigingsonderdeel ("Artikel I – Wijziging › A") waar de rij bij hoort; een genest onderdeel
                    # houdt het zijne.
                    for r in uit[begin:]:
                        r.setdefault("onderdeel", " › ".join((*hier, kop)))
            elif kind.tag in {"nr", "li.nr"}:
                # Het nummer van een opsomming of een wijziging ("a.", "1.", "–") hoort vóór de tekst die volgt.
                voor = " ".join(_platte_tekst(kind, {}).split())
            elif kind.tag == "uitgifte":
                # "Uitgegeven de negende november 2026": de datum van uitgifte, met de ondertekening als overgeslagen.
                for deel in kind:
                    if deel.tag == "datum" and (tekst := " ".join(_platte_tekst(deel, overgeslagen).split())):
                        uit.append(compact({"nr": volgende(), "kop": " › ".join(hier), "tekst": tekst}))
                    elif deel.tag in _OVERGESLAGEN:
                        overgeslagen[_OVERGESLAGEN[deel.tag]] = overgeslagen.get(_OVERGESLAGEN[deel.tag], 0) + 1
            elif kind.tag in _TEKSTBLOK:
                noten: list[ET.Element] = []
                tekst = " ".join(_platte_tekst(kind, overgeslagen, noten).split())
                if tekst and voor:
                    tekst, voor = f"{voor} {tekst}", ""
                kop = " › ".join(hier)
                gelezen = [_voetnoot(n) for n in noten]
                if tekst:
                    uit.append(compact({"nr": volgende(), "kop": kop, "tekst": tekst,
                                        "noten": [nr for nr, _, _ in gelezen if nr]}))
                uit.extend(voetnootrijen(noten, kop))
            elif kind.tag not in {"kop", "stuknr", "titel", "intitule", "lidnr", "metadata"}:
                loop(kind, hier)

    loop(stuk, ())
    titel_e = stuk.find("titel") if stuk.find("titel") is not None else stuk.find("intitule")
    titel = " ".join(_platte_tekst(titel_e, {}).split()) if titel_e is not None else ""
    return {"documenttitel": titel}, uit, overgeslagen, tabellen


