"""`overzicht_annotaties`: welke teksten van een klasse er al gemarkeerd zijn, en waar.

Het antwoord op "welke rechtssubjecten ken je nog meer uit andere annotaties" is een lijst
verschillende teksten, niet 25 losse records in willekeurige volgorde – en "andere" betekent: niet
de bepaling waar het gesprek over gaat.
"""
from __future__ import annotations

import json

from agent.nodes.annotatie_lezen import overzichtfilters
from agent.tools.annotatie_tools import BEPALING_PAGINAS, dispatch_annotatie

L = "urn:bwb:BWBR0004770:artikel:{}:lid:1"


def _el(i, klasse, tekst, art):
    return {"id": f"e{i}", "klasse": klasse, "tekst": tekst, "eigenaar_iri": L.format(art),
            "geproduceerd_door": {"run": "groot"}}


class Poort:
    def __init__(self, elementen, per_pagina=100, status="ok"):
        self.elementen, self.per_pagina, self.status = elementen, per_pagina, status
        self.calls = []

    def zoeken(self, filters):
        self.calls.append(filters)
        o = filters.get("offset", 0)
        rest = self.elementen[o:o + self.per_pagina]
        meer = o + self.per_pagina < len(self.elementen)
        return {"status": self.status, "volledig": self.status == "ok", "resultaten": rest,
                "volgende_offset": o + self.per_pagina if meer else None}


def test_groepeert_per_tekst_en_laat_de_focus_weg():
    poort = Poort([_el(1, "Rechtssubject", "de ontvanger", 3), _el(2, "Rechtssubject", "De  ontvanger", 4),
                   _el(3, "Rechtssubject", "de belastingschuldige", 19), _el(4, "Rechtssubject", "de inspecteur", 9)])
    data = json.loads(dispatch_annotatie("overzicht_annotaties", {"jas_klassen": ["rechtssubjecten"],
                                         "uitgezonderd_bron_iri": "urn:bwb:BWBR0004770:artikel:9"}, poort))
    assert poort.calls[0]["jas_klassen"] == ["Rechtssubject"] and poort.calls[0]["limit"] == 100
    assert data["status"] == "ok" and data["volledig"] is True and data["bekeken"] == 4
    assert [(g["tekst"], g["aantal"]) for g in data["groepen"]] == [("de ontvanger", 2), ("de belastingschuldige", 1)]
    assert data["groepen"][0]["vindplaatsen"] == ["BWBR0004770 art. 3 lid 1", "BWBR0004770 art. 4 lid 1"]
    assert "groot" not in json.dumps(data), "geen batchrun in het overzicht"


def test_pagineert_en_zegt_wanneer_het_niet_alles_zag():
    poort = Poort([_el(i, "Voorwaarde", f"indien {i}", i) for i in range(1, 8)], per_pagina=1)
    data = json.loads(dispatch_annotatie("overzicht_annotaties", {"jas_klassen": ["Voorwaarde"]}, poort))
    assert len(poort.calls) == 5 and data["volledig"] is False and data["status"] == "partial"


def test_een_storing_is_geen_leeg_overzicht():
    data = json.loads(dispatch_annotatie("overzicht_annotaties", {}, Poort([], status="unavailable")))
    assert data["status"] == "unavailable" and "groepen" not in data


def test_welke_vraag_met_klasse_wordt_een_overzicht():
    focus = {"bron_iri": L.format(9)}
    assert overzichtfilters({"question": "Welke rechtssubjecten ken je nog meer uit andere annotaties?",
                             "focus": focus}) == {"jas_klassen": ["Rechtssubject"], "uitgezonderd_bron_iri": L.format(9)}
    assert overzichtfilters({"question": "Welke rechtssubjecten zijn er gemarkeerd?", "focus": focus}) \
        == {"jas_klassen": ["Rechtssubject"]}, "zonder 'andere' telt de focus gewoon mee"
    assert overzichtfilters({"question": "welke annotaties zijn er?"}) is None, "zonder klasse: gewoon zoeken"
    assert overzichtfilters({"question": "En welke zijn er nog meer?",
                             "zelfstandige_vraag": "Welke rechtssubjecten zijn er nog meer gemarkeerd?",
                             "focus": focus})["uitgezonderd_bron_iri"] == L.format(9)


class _Paginas:
    """Een api met `rijen` markeringen, in pagina's zo groot als de limiet; `fout_vanaf` geeft vanaf die offset een storing."""

    def __init__(self, rijen, fout_vanaf=None):
        self.rijen, self.fout_vanaf, self.vragen = rijen, fout_vanaf, []

    def zoeken(self, filters):
        self.vragen.append(filters)
        offset, limit = filters.get("offset", 0), filters.get("limit", 25)
        if self.fout_vanaf is not None and offset >= self.fout_vanaf:
            return {"status": "unavailable", "volledig": False, "reden": "api_niet_bereikbaar"}
        einde = offset + limit
        return {"status": "ok", "volledig": True, "filters": {"bron_iri": filters.get("bron_iri")},
                "volgende_offset": einde if einde < self.rijen else None,
                "resultaten": [{"id": f"e{i}", "klasse": "Rechtssubject", "tekst": "x"} for i in range(offset, min(einde, self.rijen))]}


def _zoek(port, **args):
    return json.loads(dispatch_annotatie("search_annotaties", {"limit": 25, **args}, port))


BEPALING = "urn:bwb:BWBR0019237:artikel:6"


def test_een_zoekopdracht_op_een_bepaling_is_in_een_keer_compleet():
    uit = _zoek(_Paginas(154), bron_iri=BEPALING)
    assert len(uit["resultaten"]) == 154 and uit["status"] == "ok" and uit["volledig"] is True
    assert uit["volgende_offset"] is None


def test_meer_dan_de_grens_blijft_zichtbaar_onvolledig():
    port = _Paginas(BEPALING_PAGINAS * 100 + 1)
    uit = _zoek(port, bron_iri=BEPALING)
    assert len(uit["resultaten"]) == BEPALING_PAGINAS * 100 and uit["volgende_offset"]
    assert len(port.vragen) == BEPALING_PAGINAS


def test_een_storing_op_een_latere_pagina_houdt_de_treffers_en_zegt_het():
    uit = _zoek(_Paginas(150, fout_vanaf=100), bron_iri=BEPALING)
    assert len(uit["resultaten"]) == 100 and uit["status"] == "partial" and uit["volledig"] is False


def test_een_storing_op_de_eerste_pagina_blijft_een_storing():
    uit = _zoek(_Paginas(150, fout_vanaf=0), bron_iri=BEPALING)
    assert uit["status"] == "unavailable" and uit["reden"] == "api_niet_bereikbaar"


def test_zoeken_op_een_regeling_en_zelf_bladeren_blijven_een_pagina():
    port = _Paginas(150)
    assert len(_zoek(port, bwb_id="BWBR0019237")["resultaten"]) == 25
    assert len(_zoek(port, bron_iri=BEPALING, offset=25)["resultaten"]) == 25
    assert len(port.vragen) == 2
