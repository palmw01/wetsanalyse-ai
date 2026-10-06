"""De korte samenvatting die Lex na een annotatie geeft: hoogstens vier zinnen, alles uit data.

Geen modelaanroep. Elke zin volgt uit wat de keten echt deed – hoeveel elementen, welke klassen
overheersen, waar de jurist een keuze heeft, wat uit vaste regels kwam – zodat de samenvatting nooit
iets beweert wat niet in de voorstellen staat. Toon en vorm volgen `docs/schrijfrichtlijn-lex.md`:
je-vorm, zakelijk, geen emoji.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from ..annotatie import aanduiding_in_woorden

MAX_ZINNEN = 4
# Een besluit dat niet van het model kwam (verklaringen.yaml, sectie `besluit`).
_VASTE_REGEL = {"regel", "specificiteit"}
_GETAL = {1: "één", 2: "twee", 3: "drie", 4: "vier", 5: "vijf", 6: "zes", 7: "zeven", 8: "acht",
          9: "negen", 10: "tien", 11: "elf", 12: "twaalf"}


def _getal(n: int) -> str:
    return _GETAL.get(n, str(n))


def _hoofdletter(zin: str) -> str:
    return zin[:1].upper() + zin[1:]


def vindplaats(doel: dict[str, Any]) -> str:
    """'artikel 9 lid 1 van de Invorderingswet 1990' of 'bepaling 25.1' – zoals in de bron genoemd."""
    aanduiding = doel.get("artikel") or doel.get("nummer") or ""
    plek = aanduiding_in_woorden(str(aanduiding), str(doel.get("lid") or ""),
                                 "Divisie" if doel.get("type") == "Divisie" else "")
    plek = plek.replace("art. ", "artikel ", 1)
    titel = str(doel.get("citeertitel") or "").strip()
    return f"{plek} van de {titel}" if titel else plek


def _door(v: dict[str, Any]) -> str:
    return str(((v.get("trace") or {}).get("beslissing") or {}).get("door") or "")


def samenvatting(voorstellen: list[dict[str, Any]], doel: dict[str, Any]) -> str:
    """Hoogstens `MAX_ZINNEN` zinnen over deze annotatieronde."""
    n = len(voorstellen)
    plek = vindplaats(doel)
    if not n:
        return f"Ik heb {plek} geanalyseerd en geen JAS-elementen gevonden."
    zinnen = [f"Ik heb {plek} geanalyseerd en {_getal(n)} JAS-{'element' if n == 1 else 'elementen'} gevonden."]

    # Welke klassen overheersen – alleen zinvol vanaf drie elementen. Hoogstens twee, elk minstens
    # twee keer; staat geen klasse er twee keer, dan de eerste.
    if n >= 3:
        telling = Counter(str(v.get("klasse") or "") for v in voorstellen if v.get("klasse")).most_common()
        top = [k for k, c in telling[:2] if c >= 2]
        if not top and telling:
            top = [telling[0][0]]
        if top:
            zinnen.append("De markeringen zijn vooral " + " en ".join(top) + ".")

    keuze = sum(v.get("aandacht") == "geel" or _door(v) == "terugval" for v in voorstellen)
    if keuze == 1:
        zinnen.append("Eén voorstel heeft een plausibel alternatief en verdient daarom extra aandacht.")
    elif keuze:
        zinnen.append(f"{_hoofdletter(_getal(keuze))} voorstellen hebben een plausibel alternatief en verdienen "
                      "daarom extra aandacht.")
    else:
        zinnen.append("Geen voorstel vraagt om een keuze van jou.")

    # Wie besliste: vaste regels tegenover het model. Een terugval is geen keuze van het model en
    # staat al in de vorige zin; die telt hier niet mee.
    besluiten = [_door(v) for v in voorstellen]
    if any(besluiten):
        vast = sum(d in _VASTE_REGEL for d in besluiten)
        model = sum(d == "model" for d in besluiten)
        if vast == n:
            zinnen.append("Alle voorstellen volgen rechtstreeks uit vaste regels.")
        elif model == n:
            zinnen.append("Alle voorstellen koos het model.")
        elif vast:
            zinnen.append(f"{_hoofdletter(_getal(vast))} {'voorstel volgt' if vast == 1 else 'voorstellen volgen'} "
                          "rechtstreeks uit vaste regels" + (f", {_getal(model)} koos het model." if model else "."))
        elif model:
            zinnen.append(f"{_hoofdletter(_getal(model))} {'voorstel' if model == 1 else 'voorstellen'} "
                          "koos het model.")
    return " ".join(zinnen[:MAX_ZINNEN])
