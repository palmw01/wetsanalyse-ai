"""De ene tekstfunctie: wat in de bron staat, komt in de graaf (D3, GR-04 en GR-06).

De divisie las geen tabel, niemand las een tussenkop, en een artikel droeg zijn opschrift niet.
"""
from __future__ import annotations

from pathlib import Path

from app.collect import collect
from app.parser import ToestandParser

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TABEL = ("<table><tgroup cols=\"2\"><tbody><row><entry><al>Afk.</al></entry><entry><al>Betekenis</al></entry></row>"
         "</tbody></tgroup></table>")


def _vervang(tmp_path: Path, bron: str, oud: str, nieuw: str) -> Path:
    tekst = (FIXTURES / bron).read_text(encoding="utf-8")
    assert oud in tekst
    pad = tmp_path / bron
    pad.write_text(tekst.replace(oud, nieuw, 1), encoding="utf-8")
    return pad


def test_een_divisie_leest_tussenkop_en_tabel(tmp_path: Path) -> None:
    pad = _vervang(tmp_path, "sample_circulaire.xml", "<tekst>\n            <al>Deze leidraad ziet op",
                   f"<tekst>\n            <tussenkop>Afkortingen</tussenkop>{TABEL}\n            <al>Deze leidraad ziet op")
    divisie = ToestandParser().parse(pad).divisies[0]
    assert divisie.tekst.startswith("Afkortingen Deze leidraad ziet op")
    assert divisie.tekst.endswith("Afk. | Betekenis")
    assert "een onderdeel met" not in divisie.tekst  # het onderdeel blijft van het onderdeel


def test_een_artikel_draagt_zijn_opschrift_en_een_lid_zijn_tussenkop(tmp_path: Path) -> None:
    oud = "<al>Deze wet geldt bij de invordering van rijksbelastingen.</al>"
    pad = _vervang(tmp_path, "sample_toestand.xml", oud, f"<tussenkop>Algemeen</tussenkop>{oud}")
    kop = '<label>Artikel</label>\n    <nr status="officieel">1</nr>'
    tekst = pad.read_text(encoding="utf-8")
    assert kop in tekst
    pad.write_text(tekst.replace(kop, f"{kop}<titel>Werkingssfeer</titel>", 1), encoding="utf-8")
    batch, _ = collect(ToestandParser().parse(pad))
    artikel = next(a for a in batch.nodes["Artikel"] if a.get("titel"))
    assert artikel["titel"] == "Werkingssfeer" and artikel["label"] == "Artikel 1"
    lid = next(x for x in batch.nodes["Lid"] if "Deze wet geldt" in x["tekst"])
    assert lid["tekst"].startswith("Algemeen Deze wet geldt")
