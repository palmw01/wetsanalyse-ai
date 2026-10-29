"""Contracttests voor dezelfde bronresolver die API en agent gebruiken."""
import pytest
from bronmodel import BronFout, BronKeuze, bouw_snapshot, bron_query, eigenaar, onderdelen_om_te_kiezen, valideer_ankers
from rdflib.plugins.sparql.parser import parseQuery

BWB = "BWBR0004770"
ROOT = "urn:bwb:" + BWB


def fixture():
    def node(suffix, kind, parent="", number="", text=""):
        return {"node": ROOT + suffix, "type": "urn:bwb-ns:" + kind,
                "parent": ROOT + parent if parent else "", "nummer": number, "tekst": text}
    # XML-id-based lid 1 and empty nested container deliberately exercise real source identities.
    return [node("", "Regeling"),
            {**node(":artikel:9", "Artikel", "", "9"), "parent": ROOT},
            node(":id:lid-een", "Lid", ":artikel:9", "1", "De ontvanger 😀 handelt."),
            node(":artikel:9:lid:2", "Lid", ":artikel:9", "2", "De ontvanger handelt."),
            node(":id:a", "Onderdeel", ":id:lid-een", "a.", "Eerste onderdeel."),
            node(":id:aa", "Onderdeel", ":id:lid-een", "aa."),
            node(":id:aa1", "Onderdeel", ":id:aa", "1°.", "Genest onderdeel.")]


def snapshot(**kwargs):
    return bouw_snapshot(fixture(), bwb_id=BWB, **kwargs)


def test_ongenummerde_onderdelen_hebben_presentatie_buiten_bronidentiteit():
    from bronmodel import bronlabel
    rows = fixture()
    rows[4].update(nummer="–", label="Onderdeel –", tekst="negatieve voorlopige aanslag: de aanslag tot een negatief bedrag;")
    rows += [{**rows[4], "node": ROOT + ":id:ander", "tekst": "positieve aanslag: een positief bedrag;"}]
    before = bouw_snapshot(rows, bwb_id=BWB, bron_iri=ROOT + ":id:a")
    with_terms = [{**r, "begrip": "negatieve voorlopige aanslag"} if r["node"] == ROOT + ":id:a" else r for r in rows]
    # Meerdere expliciete begrippen op één node mogen geen dubbelzinnige bron opleveren.
    with_terms.append({**with_terms[4], "begrip": "aanslag"})
    after = bouw_snapshot(with_terms, bwb_id=BWB, bron_iri=ROOT + ":id:a")
    assert before["snapshot_id"] == after["snapshot_id"]
    assert before["nodes"] == after["nodes"]
    assert before["segmenten"] == after["segmenten"]
    assert "negatieve voorlopige aanslag" in after["doel"]["label"]
    assert after["presentatie"][ROOT + ":id:a"] == "Onderdeel — negatieve voorlopige aanslag; aanslag"
    assert before["presentatie"][ROOT + ":id:a"] != before["presentatie"][ROOT + ":id:ander"]
    assert bronlabel({"type": "Onderdeel", "nummer": "a.", "label": "Onderdeel a.", "tekst": "Definitie: tekst"}) == "Onderdeel a."
    assert bronlabel({"type": "Onderdeel", "nummer": "•", "label": "Onderdeel •", "tekst": ""}) == "Onderdeel •"


def test_bronlabel_zet_het_nummer_achter_elk_kaal_label_en_nooit_dubbel():
    """Bewuste keuze (ook Lid en Divisie, anders dan het oude `samenhang._label`): wat de detailkop al deed."""
    from bronmodel import bronlabel
    assert bronlabel({"type": "Hoofdstuk", "label": "Hoofdstuk", "nummer": "V"}) == "Hoofdstuk V"
    assert bronlabel({"type": "Lid", "label": "Lid", "nummer": "1"}) == "Lid 1"
    assert bronlabel({"type": "Divisie", "label": "Divisie", "nummer": "1.1.2"}) == "Divisie 1.1.2"
    assert bronlabel({"type": "Artikel", "label": "Artikel 9", "nummer": "9"}) == "Artikel 9"
    assert bronlabel({"type": "Divisie", "label": "1.1.2", "nummer": "1.1.2"}) == "1.1.2"
    lang = bronlabel({"type": "Onderdeel", "nummer": "–", "label": "Onderdeel –", "tekst": "a " * 200})
    assert len(lang) == len("Onderdeel — ") + 100 and lang.endswith("…")


def test_lid_selection_keeps_xml_identity_and_subtree_without_sibling():
    s = snapshot(artikel="9", lid="1")
    assert s["doel"]["bron_iri"] == ROOT + ":id:lid-een"
    assert [n["bron_iri"] for n in s["segmenten"]] == [ROOT + ":id:lid-een", ROOT + ":id:a", ROOT + ":id:aa1"]
    assert s["snapshot_id"] == snapshot(artikel="9")["snapshot_id"]


def test_literal_unicode_offsets_and_lca():
    s = snapshot(artikel="9")
    n = next(n for n in s["nodes"] if n["bron_iri"].endswith(":id:lid-een"))
    start = n["tekst"].index("😀")
    a = {"bron_iri": n["bron_iri"], "start": start, "eind": start + 1,
         "tekst": "😀", "bron_hash": n["bron_hash"]}
    assert valideer_ankers(s, [a]) == n["bron_iri"]
    assert eigenaar(s["nodes"], [ROOT + ":id:a", ROOT + ":id:aa1"]) == n["bron_iri"]
    with pytest.raises(BronFout):
        valideer_ankers(s, [{**a, "eind": start + 2}])


def test_missing_lid_never_broadens_scope():
    with pytest.raises(BronFout):
        snapshot(artikel="9", lid="7")


def test_duplicate_numbers_require_real_node_choice():
    rows = fixture() + [{"node": ROOT + ":andere:9", "type": "urn:bwb-ns:Divisie",
                         "parent": ROOT, "nummer": "9"}]
    with pytest.raises(BronFout):
        bouw_snapshot(rows, bwb_id=BWB, artikel="9")


def test_sparql_is_scoped_and_safe():
    query = bron_query(BWB)
    parseQuery(query)
    assert "GRAPH <urn:bwb:graph:BWBR0004770>" in query
    with pytest.raises(BronFout):
        bron_query('BWBR1> } SERVICE <https://example.org> {')


def test_source_changed_snapshot_changes_without_changing_unrelated_node_hash():
    before = snapshot(artikel="9", lid="1")
    rows = fixture()
    rows[3]["tekst"] = "Gewijzigde tekst in lid twee."
    after = bouw_snapshot(rows, bwb_id=BWB, artikel="9", lid="1")
    assert before["snapshot_id"] != after["snapshot_id"]
    assert before["segmenten"] == after["segmenten"]


def test_paged_mcp_resolution_and_full_label():
    from bronmodel import resolve
    rows = fixture()
    rows[0]["citeertitel"] = "Invorderingswet 1990"
    rows += [{"node": ROOT + f":extra:{i}", "type": "urn:bwb-ns:Artikel",
              "parent": ROOT, "nummer": str(i + 100), "tekst": "Aanvullend."} for i in range(110)]
    calls = []
    def query(q):
        import re
        offset = int(re.search(r"OFFSET (\d+)", q)[1])
        calls.append(offset)
        return rows[offset:offset + 100]
    result = resolve(query, bwb_id=BWB, artikel="9", lid="1")
    assert calls == [0, 100]
    assert result["doel"]["label"] == "Invorderingswet 1990 – Artikel 9, Lid 1"
    assert len(result["nodes"]) == 117
    assert len(result["segmenten"]) == 3


def test_een_structuurdeel_heet_naar_nummer_en_opschrift():
    """De importer schrijft bij een hoofdstuk alleen "Hoofdstuk" als label; nummer en opschrift staan apart.
    De kop wordt "Hoofdstuk V – Invorderingsrente" – zonder dat de snapshot-id verandert."""
    rows = fixture() + [
        {"node": ROOT + ":hoofdstuk:V", "type": "urn:bwb-ns:Hoofdstuk", "parent": ROOT, "nummer": "V",
         "label": "Hoofdstuk", "titel": "Invorderingsrente"},
        {"node": ROOT + ":hoofdstuk:V:afdeling:1", "type": "urn:bwb-ns:Afdeling", "parent": ROOT + ":hoofdstuk:V",
         "nummer": "1", "label": "Afdeling", "titel": "Algemeen"}]
    rows[0]["citeertitel"] = "Invorderingswet 1990"
    h = bouw_snapshot(rows, bwb_id=BWB, bron_iri=ROOT + ":hoofdstuk:V")
    assert h["doel"]["label"] == "Invorderingswet 1990 – Hoofdstuk V – Invorderingsrente"
    a = bouw_snapshot(rows, bwb_id=BWB, bron_iri=ROOT + ":hoofdstuk:V:afdeling:1")
    assert a["doel"]["label"] == "Invorderingswet 1990 – Hoofdstuk V, Afdeling 1 – Algemeen"
    # De nodes zelf blijven zoals de importer ze schreef: de bronidentiteit verandert niet.
    assert next(n for n in h["nodes"] if n["bron_iri"].endswith(":hoofdstuk:V"))["label"] == "Hoofdstuk"
    assert bouw_snapshot(rows, bwb_id=BWB, artikel="9")["doel"]["label"] == "Invorderingswet 1990 – Artikel 9"


def test_foreign_law_with_same_prefix_rejected():
    rows = fixture() + [{"node": ROOT + "1:artikel:3", "type": "urn:bwb-ns:Artikel", "parent": ROOT}]
    with pytest.raises(BronFout, match="bronvreemde"):
        bouw_snapshot(rows, bwb_id=BWB)


def test_artikel_met_leden_geeft_de_leden_als_keuze():
    opties = onderdelen_om_te_kiezen(snapshot(artikel="9"))
    assert [(o["bron_iri"], o["artikel"], o["lid"], o["type"]) for o in opties] == [
        (ROOT + ":id:lid-een", "9", "1", "Lid"), (ROOT + ":artikel:9:lid:2", "9", "2", "Lid")]
    # Het fragment is de eerste eigen tekst in de subtree, letterlijk.
    assert opties[0]["fragment"] == "De ontvanger 😀 handelt."


def test_een_lid_is_al_een_werkeenheid():
    assert onderdelen_om_te_kiezen(snapshot(artikel="9", lid="1")) == []


def test_onbekend_lid_biedt_de_bestaande_leden():
    with pytest.raises(BronKeuze) as fout:
        snapshot(artikel="9", lid="7")
    assert [o["lid"] for o in fout.value.opties] == ["1", "2"]
    assert fout.value.ouder.endswith("Artikel 9") and "lid 7" in str(fout.value)


def test_dubbelzinnig_nummer_toont_het_pad():
    rows = fixture() + [{"node": ROOT + ":bijlage:1", "type": "urn:bwb-ns:Bijlage", "parent": ROOT,
                         "nummer": "1", "label": "Bijlage 1"},
                        {"node": ROOT + ":bijlage:1:artikel:9", "type": "urn:bwb-ns:Artikel",
                         "parent": ROOT + ":bijlage:1", "nummer": "9", "tekst": "In de bijlage."}]
    with pytest.raises(BronKeuze) as fout:
        bouw_snapshot(rows, bwb_id=BWB, artikel="9")
    assert sorted(o["label"] for o in fout.value.opties) == ["Artikel 9", "Bijlage 1, Artikel 9"]
    assert fout.value.ouder == ""


def _leidraad():
    return [{"node": ROOT, "type": "urn:bwb-ns:Regeling"},
            {"node": ROOT + ":d:9", "type": "urn:bwb-ns:Divisie", "parent": ROOT, "nummer": "9"},
            {"node": ROOT + ":d:9.1", "type": "urn:bwb-ns:Divisie", "parent": ROOT + ":d:9", "nummer": "9.1",
             "tekst": "Eerste regel."},
            {"node": ROOT + ":d:9.2", "type": "urn:bwb-ns:Divisie", "parent": ROOT + ":d:9", "nummer": "9.2",
             "tekst": "Tweede regel."}]


def test_beleidsregel_lid_is_de_subbepaling():
    s = bouw_snapshot(_leidraad(), bwb_id=BWB, artikel="9", lid="2")
    assert s["doel"]["bron_iri"] == ROOT + ":d:9.2"
    assert [o["nummer"] for o in onderdelen_om_te_kiezen(bouw_snapshot(_leidraad(), bwb_id=BWB, artikel="9"))] == ["9.1", "9.2"]


def test_beleidsregel_zonder_die_subbepaling_biedt_de_bestaande():
    with pytest.raises(BronKeuze) as fout:
        bouw_snapshot(_leidraad(), bwb_id=BWB, artikel="9", lid="5")
    assert [o["nummer"] for o in fout.value.opties] == ["9.1", "9.2"]


def test_reeks_moet_onder_een_bepaling_hangen():
    from bronmodel import gedeelde_bepaling
    nodes = snapshot(artikel="9")["nodes"]
    leden = [ROOT + ":id:lid-een", ROOT + ":artikel:9:lid:2"]
    assert gedeelde_bepaling(nodes, leden)["bron_iri"] == ROOT + ":artikel:9"
    for fout in ([leden[0], leden[0]],                     # dubbel
                 [leden[0], ROOT + ":bestaat:niet"],        # onbekend
                 [leden[0], ROOT + ":id:a"],                # lid en onderdeel: andere ouder
                 [ROOT + ":id:a", ROOT + ":id:aa"]):        # onderdelen zijn niet kiesbaar
        with pytest.raises(BronFout):
            gedeelde_bepaling(nodes, fout)


def test_annotatie_eenheden_volgen_de_keuzekaart():
    from bronmodel import annotatie_eenheden
    rows = fixture() + [{"node": ROOT + ":hoofdstuk:2", "type": "urn:bwb-ns:Hoofdstuk", "parent": ROOT},
                        {"node": ROOT + ":artikel:10", "type": "urn:bwb-ns:Artikel",
                         "parent": ROOT + ":hoofdstuk:2", "nummer": "10", "tekst": "Zonder leden."}]
    nodes = bouw_snapshot(rows, bwb_id=BWB)["nodes"]
    leden = [ROOT + ":id:lid-een", ROOT + ":artikel:9:lid:2"]
    assert annotatie_eenheden(nodes, ROOT + ":artikel:9") == leden            # per lid
    assert annotatie_eenheden(nodes, ROOT + ":artikel:10") == [ROOT + ":artikel:10"]
    assert annotatie_eenheden(nodes, ROOT + ":id:lid-een") == [ROOT + ":id:lid-een"]
    assert annotatie_eenheden(nodes, ROOT + ":id:a") == [ROOT + ":id:a"]
    hele = annotatie_eenheden(nodes, ROOT)                                    # de hele regeling
    assert sorted(hele) == sorted([*leden, ROOT + ":artikel:10"]) and len(hele) == 3
    assert annotatie_eenheden(nodes, ROOT + ":hoofdstuk:2", onderliggend=False) == []
    leidraad = bouw_snapshot(_leidraad(), bwb_id=BWB)["nodes"]
    assert annotatie_eenheden(leidraad, ROOT) == [ROOT + ":d:9.1", ROOT + ":d:9.2"]
    with pytest.raises(BronFout):
        annotatie_eenheden(nodes, ROOT + ":bestaat:niet")
