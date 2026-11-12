import { describe, expect, it } from "vitest";

import { CLIENT_COMMANDOS, NAAM_RE, beschikbaar, connectorOpties, menuRegels, ontleed, type Stand } from "./commandos";
import type { ConnectorStand } from "./connectorsMenu";
import { ACTIES, MODULES, suggestiesVan, werkgebiedSuggesties, type Onderwerp, type Suggestie } from "./vraagLex";

const geenBronnen: ConnectorStand = { beschikbaar: [] };
const bronnen: ConnectorStand = {
  beschikbaar: [
    { naam: "kamerstukken", label: "Kamerstukken", brontype: "kamerstuk", beschikbaarheid: "aan" },
    { naam: "rechtspraak", label: "Rechtspraak", brontype: "uitspraak", beschikbaarheid: "aan" },
    { naam: "bekendmakingen", label: "Staatsblad en Staatscourant", brontype: "bekendmaking", beschikbaarheid: "niet_aangeboden" },
  ],
  gesprek: ["kamerstukken"],
};
const stand = (suggesties: Suggestie[], over: Partial<Stand> = {}): Stand =>
  ({ suggesties, connectors: geenBronnen, bezig: false, geblokkeerd: false, ...over });

const deelvraag: Onderwerp = { soort: "deelvraag", werkgebied_id: "wg1", id: "dv1", label: "Wanneer?" };
const begrip: Onderwerp = { soort: "begrip", werkgebied_id: "wg1", id: "b1", label: "termijn" };
const bepaling: Extract<Onderwerp, { soort: "bepaling" }> = { soort: "bepaling", bron_iri: "urn:bwb:BWBR0004770:artikel:9:lid:1", label: "Artikel 9, lid 1" };

/** Alle suggesties van alle soorten (behalve de markering, die alleen vragen heeft). */
function alleSuggesties(): Suggestie[][] {
  return [werkgebiedSuggesties(), suggestiesVan(deelvraag), suggestiesVan(begrip), suggestiesVan(bepaling),
    suggestiesVan({ ...bepaling, annotatie: true }),
    ...(["bron", "kandidaat"] as const).map((s) => MODULES[s].suggesties({ soort: s, werkgebied_id: "wg1", id: "x", label: "" }))];
}

describe("het register", () => {
  it("elk commando is een suggestie uit het ene register: een actie uit graph-qa, een doel of een klaargezette vraag", () => {
    for (const lijst of alleSuggesties()) {
      for (const s of lijst.filter((x) => x.commando)) {
        expect(s.actie ? (ACTIES as readonly string[]).includes(s.actie) : !!s.doel || !!s.invullen).toBe(true);
      }
    }
  });

  it("namen zijn kleine letters met streepjes en per context uniek; een suggestie overstemt geen clientcommando", () => {
    const client = CLIENT_COMMANDOS.map((c) => c.naam);
    for (const c of client) expect(c).toMatch(NAAM_RE);
    expect(new Set(client).size).toBe(client.length);
    for (const lijst of alleSuggesties()) {
      const namen = lijst.flatMap((s) => (s.commando ? [s.commando.naam] : []));
      for (const n of namen) {
        expect(n).toMatch(NAAM_RE);
        expect(client).not.toContain(n);
      }
      // Dezelfde naam twee keer in één context mag alleen voor dezelfde handeling (de bronnen bij een deelvraag).
      const perNaam = new Map<string, string>();
      for (const s of lijst.filter((x) => x.commando)) {
        const sleutel = s.actie ?? s.tekst;
        expect(perNaam.get(s.commando!.naam) ?? sleutel).toBe(sleutel);
        perNaam.set(s.commando!.naam, sleutel);
      }
    }
  });

  it("de commando's van een context zijn de suggesties van die context, dan de clientcommando's", () => {
    const namen = beschikbaar(stand(werkgebiedSuggesties())).map((c) => c.naam);
    expect(namen.slice(0, 3)).toEqual(["dossier", "thema", "deelvragen"]);
    expect(namen).toContain("annoteer");
    expect(namen.slice(-2)).toEqual(["nieuw", "help"]);
    // Zonder bron om om te zetten geen /bron.
    expect(namen).not.toContain("bron");
    expect(beschikbaar(stand([], { connectors: bronnen })).map((c) => c.naam)).toEqual(["nieuw", "bron", "help"]);
    // Bij een deelvraag de handelingen op de deelvraag, niet die van het werkgebied.
    const bijDeelvraag = beschikbaar(stand(suggestiesVan(deelvraag))).map((c) => c.naam);
    expect(bijDeelvraag).toEqual(["scherper", "splits", "bronnen", "bepaling", "annoteer", "dekking", "nieuw", "help"]);
  });
});

describe("ontleden", () => {
  it("alleen een / als eerste teken is een commando", () => {
    expect(ontleed("/dee")).toEqual({ naam: "dee", rest: "", metSpatie: false });
    expect(ontleed("/bron kamer")).toEqual({ naam: "bron", rest: "kamer", metSpatie: true });
    expect(ontleed("/")).toEqual({ naam: "", rest: "", metSpatie: false });
    expect(ontleed(" /dee")).toBeNull();
    expect(ontleed("wat betekent artikel 9/1?")).toBeNull();
    expect(ontleed("/Dee")).toBeNull();
  });
});

describe("het menu", () => {
  const wg = stand(werkgebiedSuggesties());

  it("is dicht zonder / vooraan, en na een ander commando met een spatie (dan is het een vraag)", () => {
    expect(menuRegels("deelvragen", wg)).toBeNull();
    expect(menuRegels("/deelvragen bij artikel 9", wg)).toBeNull();
    expect(menuRegels("/ hoe zit het", wg)).toBeNull();
  });

  it("filtert op het begin van de naam, de exacte naam eerst, dan wat elders past", () => {
    expect(menuRegels("/dee", wg)!.map((r) => r.label)).toEqual(["/deelvragen", "/annoteer-deelvragen"]);
    expect(menuRegels("/annoteer", wg)!.map((r) => r.label)).toEqual(["/annoteer", "/annoteer-deelvragen"]);
    expect(menuRegels("/", wg)!.length).toBe(beschikbaar(wg).length);
    // Onbekend: een lege lijst, en dan verstuurt Enter de tekst als vraag.
    expect(menuRegels("/xyzq", wg)).toEqual([]);
    // Past geen naam, dan de hulptekst.
    expect(menuRegels("/eenvoudig", stand(suggestiesVan(begrip)))!.map((r) => r.label)).toEqual(["/uitleg"]);
  });

  it("Enter voert precies de suggestie uit: dezelfde tekst en actie als een klik", () => {
    const [r] = menuRegels("/deelvragen", wg)!;
    expect(r.uitvoer).toEqual({ soort: "suggestie", suggestie: werkgebiedSuggesties().find((s) => s.actie === "deelvragen_voorstellen") });
    const [annoteer] = menuRegels("/annoteer", stand(suggestiesVan(bepaling)))!;
    expect(annoteer.uitvoer).toMatchObject({ suggestie: { tekst: "Annoteer dit lid", doel: { bron_iri: bepaling.bron_iri } } });
  });

  it("een suggestiecommando kan niet tijdens een beurt of zonder budget; een klaargezette vraag en de client wel", () => {
    const bezig = stand(suggestiesVan(begrip), { bezig: true });
    const regels = menuRegels("/", bezig)!;
    expect(regels.find((r) => r.label === "/uitleg")).toMatchObject({ uit: "Lex is nog bezig", uitvoer: null });
    expect(regels.find((r) => r.label === "/verschil")?.uit).toBeUndefined();
    expect(regels.find((r) => r.label === "/nieuw")?.uitvoer).toEqual({ soort: "client", handeling: "nieuw" });
    expect(menuRegels("/uitleg", stand(suggestiesVan(begrip), { geblokkeerd: true }))![0].uit).toBe("je tokenbudget is op");
  });

  it("/bron vult aan en toont de bronnen met hun stand; wat de omgeving niet aanbiedt staat er niet bij", () => {
    const b = stand([], { connectors: bronnen });
    const [bron] = menuRegels("/bron", b)!;
    expect(bron).toMatchObject({ aanvulling: "/bron ", uitvoer: null });
    expect(connectorOpties(bronnen).map((k) => k.naam)).toEqual(["kamerstukken", "rechtspraak"]);
    const opties = menuRegels("/bron ", b)!;
    expect(opties.map((r) => r.hulp)).toEqual(["Kamerstukken staat nu aan – zet uit", "Rechtspraak staat nu uit – zet aan"]);
    expect(menuRegels("/bron recht", b)!.map((r) => r.uitvoer)).toEqual([{ soort: "client", handeling: "bron", argument: "rechtspraak" }]);
    expect(menuRegels("/bron staatsblad", b)).toEqual([]);
  });
});
