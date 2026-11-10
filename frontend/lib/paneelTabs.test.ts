import { describe, expect, it } from "vitest";

import { MAX_TABS, bewaarVorm, leesBewaard, openTab, sleutelVan, sluitTab, tabLabel, type PaneelInhoud } from "./paneelTabs";

const bron = (n: number): PaneelInhoud => ({ soort: "context", ctx: { soort: "bron", bron_iri: `urn:bwb:BWBR0004770:artikel:${n}`, titel: `Artikel ${n}, Invorderingswet 1990` } });
const artefact = (run: string): PaneelInhoud => ({ soort: "artefact", artefact: { soort: "begrip", werkgebied_id: "wg1", run_id: run, titel: "Termijn" } as never });
const annotatie: PaneelInhoud = { soort: "annotatie", doel: { bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:2", label: "Lid 2" }, tab: "graaf", extra: [],
  graaf: { keten: true, kennisgraaf: { groot: true } as never } };

describe("paneelTabs", () => {
  it("opent achteraan en maakt actief; dezelfde bron is één tab", () => {
    let s = openTab({ tabs: [] }, bron(9), "een antwoord");
    s = openTab(s, bron(10));
    s = openTab(s, bron(9));
    expect(s.tabs.map((t) => t.sleutel)).toEqual([sleutelVan(bron(9)), sleutelVan(bron(10))]);
    expect(s.actief).toBe(sleutelVan(bron(9)));
    expect(s.tabs[0].vanuit).toBe("een antwoord");
  });

  it("heeft één tab voor het artefact van een werkgebied; een bepaling is één tab, of je haar leest of annoteert", () => {
    let s = openTab({ tabs: [] }, artefact("r1"));
    s = openTab(s, artefact("r2"));
    const lezen: PaneelInhoud = { soort: "context", ctx: { soort: "bron", bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:2", titel: "Lid 2" } };
    s = openTab(s, lezen);
    s = openTab(s, annotatie);
    expect(s.tabs.map((t) => t.sleutel)).toEqual(["artefact", "bron:urn:bwb:BWBR0004770:artikel:9:lid:2"]);
    expect(s.tabs[1].inhoud.soort).toBe("annotatie");
    // Meer bepalingen tegelijk in beoordeling: elk een eigen tab.
    s = openTab(s, { ...annotatie, doel: { bron_iri: "urn:bwb:BWBR0004770:artikel:10" } } as PaneelInhoud);
    expect(s.tabs).toHaveLength(3);
    expect((s.tabs[0].inhoud as Extract<PaneelInhoud, { soort: "artefact" }>).artefact.run_id).toBe("r2");
  });

  it("laat de oudste niet-actieve vallen boven het maximum", () => {
    let s = { tabs: [] } as ReturnType<typeof openTab>;
    for (let n = 1; n <= MAX_TABS + 2; n++) s = openTab(s, bron(n));
    expect(s.tabs).toHaveLength(MAX_TABS);
    expect(s.tabs[0].sleutel).toBe(sleutelVan(bron(3)));
    expect(s.actief).toBe(sleutelVan(bron(MAX_TABS + 2)));
  });

  it("sluit een tab; was hij actief, dan wordt de buur actief", () => {
    let s = openTab(openTab(openTab({ tabs: [] }, bron(1)), bron(2)), bron(3));
    s = { ...s, actief: sleutelVan(bron(2)) };
    const na = sluitTab(s, sleutelVan(bron(2)));
    expect(na.actief).toBe(sleutelVan(bron(3)));
    expect(na.buur?.sleutel).toBe(sleutelVan(bron(3)));
    const laatste = sluitTab({ ...na, actief: sleutelVan(bron(3)) }, sleutelVan(bron(3)));
    expect(laatste.actief).toBe(sleutelVan(bron(1)));
    const inactief = sluitTab(laatste, "bestaat-niet");
    expect(inactief).toBe(laatste);
  });

  it("noemt de tab kort en de tooltip voluit, met waar hij geopend werd", () => {
    const [t] = openTab({ tabs: [] }, bron(9), "een antwoord").tabs;
    expect(tabLabel(t)).toEqual({ kort: "Artikel 9", vol: "Artikel 9, Invorderingswet 1990 · geopend vanuit een antwoord" });
    expect(tabLabel(openTab({ tabs: [] }, annotatie).tabs[0])).toEqual({ kort: "Artikel 9, lid 2", vol: "Artikel 9, lid 2, BWBR0004770 · annotatie" });
  });

  it("bewaart zonder de kennisgraaf en leest streng terug", () => {
    const s = openTab(openTab({ tabs: [] }, bron(9)), annotatie);
    const bewaard = JSON.parse(JSON.stringify(bewaarVorm(s)));
    expect(bewaard.tabs[1].inhoud.graaf).toEqual({ keten: true });
    const terug = leesBewaard(bewaard);
    expect(terug?.tabs.map((t) => t.sleutel)).toEqual(["bron:urn:bwb:BWBR0004770:artikel:9", "bron:urn:bwb:BWBR0004770:artikel:9:lid:2"]);
    expect(terug?.actief).toBe("bron:urn:bwb:BWBR0004770:artikel:9:lid:2");
    expect(leesBewaard({ tabs: [{ inhoud: { soort: "context", ctx: { soort: "bron" } } }] })).toBeUndefined();
    expect(leesBewaard("kapot")).toBeUndefined();
  });

  it("een bepaling met de samenhang van een antwoord: zelfde tab, bewaard zonder de kennisgraaf", () => {
    const metGraaf: PaneelInhoud = { soort: "context", ctx: { soort: "bron", bron_iri: "urn:bwb:BWBR0004770:artikel:9", titel: "Artikel 9",
      weergave: "graaf", samenhang: { extra: [{ bron_iri: "urn:bwb:BWBR0004770:artikel:10" }],
        graaf: { keten: true, bereik: "kennisgraaf", kennisgraaf: { groot: true } as never } } } };
    expect(sleutelVan(metGraaf)).toBe(sleutelVan(bron(9)));
    const bewaard = JSON.parse(JSON.stringify(bewaarVorm(openTab({ tabs: [] }, metGraaf))));
    expect(bewaard.tabs[0].inhoud.ctx.samenhang.graaf).toEqual({ keten: true, bereik: "kennisgraaf" });
    expect(leesBewaard(bewaard)?.tabs[0].inhoud).toMatchObject({ ctx: { weergave: "graaf" } });
  });
});
