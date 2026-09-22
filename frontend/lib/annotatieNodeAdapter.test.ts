import { describe, expect, it } from "vitest";

import { bronVan, regelsVan } from "./annotatie";
import { segmentAnker, type NodeElement, type NodeSegment, type NodeWeergave } from "./annotatieNode";
import {
  beslissingNaarNode, documentVanNode, elementVanNode, lidUitIri, nodeAnkersUitSelectie, nodeBronVan,
  tekstVanAnkers,
} from "./annotatieNodeAdapter";
import { vindPositie } from "./selectie";
import { blokkenVan } from "./wetstructuur";

const W = "urn:bwb:BWBR0004770:artikel:9";

function seg(bron_iri: string, type: string, nummer: string, tekst: string, volgorde: number): NodeSegment {
  return { bron_iri, type, nummer, tekst, volgorde, label: `${type} ${nummer}`, bron_hash: `h-${volgorde}` };
}

function weergave(segmenten: NodeSegment[], extra: Partial<NodeWeergave> = {}): NodeWeergave {
  return {
    schema_versie: 2, snapshot_id: "s1", segmenten, lagen: [], elementen: [], verwijzingen: [], dekking: {},
    doel: { bron_iri: W, type: "Artikel", bwb_id: "BWBR0004770", artikel: "9", citeertitel: "Invorderingswet 1990" },
    ...extra,
  };
}

function element(ankers: NodeElement["ankers"], extra: Partial<NodeElement> = {}): NodeElement {
  return {
    id: "e1", eigenaar_iri: ankers[0].bron_iri, laag_id: "l1", klasse: "Rechtssubject",
    tekst: tekstVanAnkers(ankers), toelichting: "", ankers, lifecycle: "voorgesteld", herkomst: "agent", ...extra,
  };
}

// Een lid met eigen tekst en twee onderdelen, waarvan één met een teken buiten het BMP (𝑥 telt als
// twee UTF-16-eenheden maar als één codepoint) – precies waar de twee stelsels uit elkaar lopen.
const LID1 = seg(`${W}:lid:1`, "Lid", "1", "De ontvanger kan 𝑥 invorderen:", 1);
const ONDA = seg(`${W}:lid:1:onderdeel:a`, "Onderdeel", "a", "bij dwangbevel 1° graden;", 2);
const ONDB = seg(`${W}:lid:1:onderdeel:b`, "Onderdeel", "b", "bij verrekening.", 3);
const LID2 = seg(`${W}:lid:2`, "Lid", "2", "Het tweede lid.", 4);

describe("nodeBronVan", () => {
  it("bouwt één regel per lid met de onderdelen eronder, gelijk aan regelsVan/bronVan", () => {
    const nb = nodeBronVan(weergave([ONDB, LID2, LID1, ONDA]));
    expect(nb.info.leden_teksten).toEqual([
      { lid: "1", tekst: "De ontvanger kan 𝑥 invorderen:\na. bij dwangbevel 1° graden;\nb. bij verrekening." },
      { lid: "2", tekst: "Het tweede lid." },
    ]);
    expect(nb.bron).toBe(bronVan(regelsVan(nb.info)));
  });

  it("legt elke node op de plek waar zijn tekst in de samengestelde bron staat", () => {
    const nb = nodeBronVan(weergave([LID1, ONDA, ONDB, LID2]));
    for (const p of nb.plekken) {
      expect(nb.bron.slice(p.begin, p.begin + p.segment.tekst.length)).toBe(p.segment.tekst);
    }
    expect(nb.plekken.map((p) => p.lid)).toEqual(["1", "1", "1", "2"]);
  });

  it("laat de onderdelen ingesprongen zien, ook als het lid zelf geen tekst heeft", () => {
    const nb = nodeBronVan(weergave([ONDA, ONDB]));
    expect(nb.info.leden_teksten[0].lid).toBe("1");
    const blokken = blokkenVan(regelsVan(nb.info));
    expect(blokken.map((b) => [b.nummer, b.niveau])).toEqual([["1.", 0], ["a.", 1], ["b.", 1]]);
    for (const p of nb.plekken) expect(nb.bron.slice(p.begin, p.begin + p.segment.tekst.length)).toBe(p.segment.tekst);
  });

  it("kent een bepaling zonder leden", () => {
    const art = seg(W, "Artikel", "9", "Een artikel zonder leden.", 0);
    const nb = nodeBronVan(weergave([art]));
    expect(nb.info.leden_teksten).toEqual([{ lid: "", tekst: "Een artikel zonder leden." }]);
    expect(nb.plekken[0].begin).toBe(0);
  });
});

describe("elementVanNode", () => {
  it("vertaalt codepoints naar UTF-16 zodat de weergave het anker exact terugvindt", () => {
    const view = weergave([LID1, ONDA]);
    const nb = nodeBronVan(view);
    // "invorderen" staat ná de 𝑥: codepoint 20, maar UTF-16-positie 21.
    const anker = segmentAnker(LID1, "De ontvanger kan 𝑥 ".length, "De ontvanger kan 𝑥 invorderen".length);
    expect(anker.tekst).toBe("invorderen");
    const el = elementVanNode(element([anker]), nb);
    expect(el.tekst).toBe("invorderen");
    expect(el.lid).toBe("1");
    expect(vindPositie(nb.bron, el.tekst, el.anker, [])).toBe(el.anker!.start);
    expect(nb.bron.slice(el.anker!.start, el.anker!.eind)).toBe("invorderen");
  });

  it("maakt van meerdere ankers één doorlopende markering over de onderdelen heen", () => {
    const nb = nodeBronVan(weergave([LID1, ONDA, ONDB]));
    const a = segmentAnker(ONDA, 0, "bij dwangbevel".length);
    const b = segmentAnker(ONDB, 0, "bij verrekening".length);
    const el = elementVanNode(element([a, b]), nb);
    expect(el.tekst).toBe("bij dwangbevel 1° graden;\nb. bij verrekening");
    expect(vindPositie(nb.bron, el.tekst.trim(), el.anker, [])).toBe(el.anker!.start);
  });

  it("geeft een verouderd of niet-passend anker geen plek in de tekst", () => {
    const nb = nodeBronVan(weergave([LID1]));
    const anker = { ...segmentAnker(LID1, 0, 2), bron_hash: "oud" };
    expect(elementVanNode(element([anker]), nb).anker).toBeNull();
    expect(elementVanNode(element([segmentAnker(LID1, 0, 2)], { verouderd: true }), nb).verouderd).toBe(true);
  });
});

describe("nodeAnkersUitSelectie", () => {
  it("splitst een selectie over twee onderdelen in twee ankers, zonder het nummer ertussen", () => {
    const nb = nodeBronVan(weergave([LID1, ONDA, ONDB]));
    const start = nb.bron.indexOf("dwangbevel");
    const eind = nb.bron.indexOf("verrekening") + "verrekening".length;
    const ankers = nodeAnkersUitSelectie(nb, start, eind);
    expect(ankers.map((a) => [a.bron_iri, a.tekst])).toEqual([
      [ONDA.bron_iri, "dwangbevel 1° graden"],
      [ONDB.bron_iri, "bij verrekening"],
    ]);
    expect(tekstVanAnkers(ankers)).toBe("dwangbevel 1° graden bij verrekening");
  });

  it("rekent terug naar codepoints en laat het lidvoorvoegsel buiten het anker", () => {
    const nb = nodeBronVan(weergave([LID1]));
    const ankers = nodeAnkersUitSelectie(nb, 0, nb.bron.indexOf("invorderen") + "invorderen".length);
    expect(ankers).toHaveLength(1);
    expect(ankers[0].start).toBe(0);
    expect(ankers[0].tekst).toBe("De ontvanger kan 𝑥 invorderen");
    expect(ankers[0].eind).toBe(Array.from("De ontvanger kan 𝑥 invorderen").length);
  });

  it("is de omgekeerde weg van elementVanNode voor aaneengesloten ankers", () => {
    // Alleen voor ankers zonder gat ertussen: de weergave toont één doorlopende markering, dus een
    // anker dat midden in een onderdeel ophoudt komt terug tot het einde van dat onderdeel. Dat
    // speelt alleen bij een fragmentcorrectie; klasse en toelichting laten de ankers ongemoeid.
    const nb = nodeBronVan(weergave([LID1, ONDA, ONDB]));
    const origineel = [segmentAnker(ONDA, 4, ONDA.tekst.length - 1), segmentAnker(ONDB, 0, 15)];
    const el = elementVanNode(element(origineel), nb);
    expect(nodeAnkersUitSelectie(nb, el.anker!.start, el.anker!.eind)).toEqual(origineel);
  });
});

describe("beslissingNaarNode", () => {
  const nb = nodeBronVan(weergave([LID1, ONDA]));

  it("geeft klasse en toelichting ongewijzigd door", () => {
    expect(beslissingNaarNode({ type: "edit", wijziging: { klasse: "Rechtsobject" } }, nb))
      .toEqual({ type: "edit", wijziging: { klasse: "Rechtsobject" } });
    expect(beslissingNaarNode({ type: "reject", review_reason: "tekst" }, nb))
      .toEqual({ type: "reject", review_reason: "tekst" });
  });

  it("maakt van een fragmentcorrectie met anker een set bronnode-ankers", () => {
    const start = nb.bron.indexOf("dwangbevel");
    const eind = start + "dwangbevel".length;
    const uit = beslissingNaarNode({
      type: "edit", review_reason: "tekst",
      wijziging: { tekst: "dwangbevel", anker: { lid: "1", start, eind, voor: "", na: "", bron_hash: "" } },
    }, nb);
    expect(uit.wijziging).toEqual({ tekst: "dwangbevel", ankers: [segmentAnker(ONDA, 4, 14)] });
  });

  it("zoekt een voorgesteld fragment zonder anker in de tekst op, of weigert", () => {
    expect(beslissingNaarNode({ type: "edit", wijziging: { tekst: "invorderen" } }, nb).wijziging?.tekst).toBe("invorderen");
    expect(() => beslissingNaarNode({ type: "edit", wijziging: { tekst: "staat er niet" } }, nb)).toThrow();
  });
});

describe("documentVanNode", () => {
  it("is pas afgerond als elke laag in beeld dat is", () => {
    const segs = [LID1, LID2];
    const laag = (id: string, status: string) => ({ id, bron_iri: `${W}:lid:${id}`, revisie: 1, status });
    const nb = nodeBronVan(weergave(segs));
    expect(documentVanNode(weergave(segs, { lagen: [laag("1", "geaccordeerd"), laag("2", "in_review")] }), nb).status).toBe("in_review");
    expect(documentVanNode(weergave(segs, { lagen: [laag("1", "geaccordeerd"), laag("2", "geaccordeerd")] }), nb).status).toBe("geaccordeerd");
    expect(documentVanNode(weergave(segs), nb).status).toBe("in_review");
  });
});

describe("lidUitIri", () => {
  it("haalt het lid uit een bron-IRI", () => {
    expect(lidUitIri(`${W}:lid:2a:onderdeel:b`)).toBe("2a");
    expect(lidUitIri(W)).toBe("");
  });
});
