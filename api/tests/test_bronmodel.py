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
