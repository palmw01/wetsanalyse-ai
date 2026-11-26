import { describe, expect, it } from "vitest";

import { CLIENT_COMMANDOS, NAAM_RE, beschikbaar, connectorOpties, hulpOverzicht, menuRegels, ontleed, type Stand } from "./commandos";
import type { ConnectorStand } from "./connectorsMenu";
import { ACTIES, MODULES, commandoContexten, suggestiesVan, werkgebiedSuggesties, type Onderwerp, type Suggestie } from "./vraagLex";

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

  it("de commando's van een context zijn de suggesties van die context, dan de plugins en de clientcommando's", () => {
    const namen = beschikbaar(stand(werkgebiedSuggesties())).map((c) => c.naam);
    expect(namen.slice(0, 3)).toEqual(["dossier", "thema", "deelvragen"]);
    expect(namen).toContain("annoteer");
    expect(namen.slice(-2)).toEqual(["context", "help"]);
    // Zonder bron om om te zetten geen /bron.
    expect(namen).not.toContain("bron");
    expect(beschikbaar(stand([], { connectors: bronnen })).map((c) => c.naam)).toEqual(["contenttoets", "nieuw", "bron", "context", "help"]);
    // Bij een deelvraag de handelingen op de deelvraag, niet die van het werkgebied.
    const bijDeelvraag = beschikbaar(stand(suggestiesVan(deelvraag))).map((c) => c.naam);
    expect(bijDeelvraag).toEqual(["scherper", "splits", "bronnen", "bepaling", "annoteer", "dekking", "contenttoets", "nieuw", "context", "help"]);
  });
});

describe("een plugin", () => {
  it("/contenttoets staat in het menu, vult aan en sluit het menu zodra er tekst achter staat", () => {
    const regels = menuRegels("/content", stand([]))!;
    expect(regels[0]).toMatchObject({ label: "/contenttoets", aanvulling: "/contenttoets ", uitvoer: null });
    expect(menuRegels("/contenttoets U kunt betalen in 24 maanden.", stand([]))).toBeNull();
  });

  it("staat er alleen als de plugin in het gesprek aanstaat", () => {
    expect(beschikbaar(stand([], { plugins: [] })).map((c) => c.naam)).not.toContain("contenttoets");
    expect(beschikbaar(stand([], { plugins: ["contenttoets"] })).map((c) => c.naam)).toContain("contenttoets");
  });

  it("kan niet tijdens een beurt of zonder budget", () => {
    expect(menuRegels("/contenttoets", stand([], { bezig: true }))![0].uit).toBe("Lex is nog bezig");
    expect(menuRegels("/contenttoets", stand([], { geblokkeerd: true }))![0].uit).toBe("je tokenbudget is op");
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

describe("/help: het overzicht van alle commando's", () => {
  const contexten = commandoContexten();
  const namen = (st: Stand, huidig?: Parameters<typeof hulpOverzicht>[2]) =>
    hulpOverzicht(st, contexten, huidig).flatMap((g) => g.regels.map((r) => r.label));
  /** Elke stand waarin het menu kan openen: zonder onderwerp, in elke context, met en zonder bron om om te zetten. */
  const standen = (): [Stand, Parameters<typeof hulpOverzicht>[2]][] => [geenBronnen, bronnen].flatMap((connectors) => [
    [stand([], { connectors }), undefined] as [Stand, undefined],
    ...contexten.map((c) => [stand(c.suggesties, { connectors }), c.soort] as [Stand, typeof c.soort]),
  ]);

  it("de contexten zijn die van de werkplek: dezelfde suggesties als de rij boven het veld", () => {
    const per = Object.fromEntries(contexten.map((c) => [c.soort, c.suggesties]));
    expect(per.werkgebied).toEqual(werkgebiedSuggesties());
    expect(per.deelvraag).toEqual(suggestiesVan(deelvraag));
    expect(per.begrip).toEqual(suggestiesVan(begrip));
    expect(contexten.map((c) => c.soort)).not.toContain("markering");
  });

  it("de groep Hier is precies het menu bij /, in elke stand", () => {
    for (const [st, huidig] of standen()) {
      const [hier] = hulpOverzicht(st, contexten, huidig);
      expect(hier.reden).toBeUndefined();
      expect(hier.regels.map((r) => r.label)).toEqual(menuRegels("/", st)!.map((r) => r.label));
      expect(hier.regels.map((r) => r.aanvulling)).toEqual(menuRegels("/", st)!.map((r) => r.aanvulling));
    }
  });

  it("vanuit elke stand staat elk commando dat ergens in het menu kan erin: het menu loopt nooit voor op /help", () => {
    const ooitInMenu = new Set(standen().flatMap(([st]) => menuRegels("/", st)!.map((r) => r.label)));
    for (const c of CLIENT_COMMANDOS) expect(ooitInMenu).toContain(`/${c.naam}`);
    for (const [st, huidig] of standen()) {
      const overzicht = new Set(namen(st, huidig));
      for (const label of ooitInMenu) expect(overzicht, `${label} ontbreekt (${huidig ?? "geen context"})`).toContain(label);
    }
  });

  it("wat hier niet kan staat gegroepeerd met de reden, en een groep herhaalt niet wat hier al staat", () => {
    const groepen = hulpOverzicht(stand([]), contexten);
    const wg = groepen.find((g) => g.sleutel === "werkgebied")!;
    expect(wg).toMatchObject({ titel: "In een werkgebied", reden: "alleen in een werkgebied" });
    expect(wg.regels.map((r) => r.label)).toContain("/deelvragen");
    // Zonder bron om om te zetten: /bron niet in het menu, wel in het overzicht met waarom.
    const niet = groepen.find((g) => g.sleutel.startsWith("niet:"))!;
    expect(niet.regels.map((r) => r.label)).toEqual(["/bron"]);
    expect(niet.reden).toMatch(/bron naast de wet/);
    for (const g of groepen.slice(1)) expect(g.reden).toBeTruthy();
    // Een clientcommando staat één keer, onder Hier.
    expect(namen(stand([])).filter((l) => l === "/nieuw")).toHaveLength(1);
    // In een werkgebied geen eigen groep voor het werkgebied: die commando's staan onder Hier.
    expect(hulpOverzicht(stand(werkgebiedSuggesties()), contexten, "werkgebied").map((g) => g.sleutel)).not.toContain("werkgebied");
  });

  it("per commando: of het een beurt start, en een voorbeeld als dat helpt", () => {
    const regels = hulpOverzicht(stand(suggestiesVan(begrip), { connectors: bronnen }), contexten, "begrip")[0].regels;
    const r = (label: string) => regels.find((x) => x.label === label)!;
    expect(r("/uitleg")).toMatchObject({ beurt: "beurt" });
    expect(r("/uitleg").voorbeeld).toBeUndefined();
    expect(r("/verschil")).toMatchObject({ beurt: "klaarzetten", voorbeeld: "Wat is het betekenisverschil met …" });
    expect(r("/nieuw")).toMatchObject({ beurt: "geen" });
    expect(r("/bron")).toMatchObject({ beurt: "geen", voorbeeld: "/bron kamerstukken", aanvulling: "/bron " });
    // Tijdens een beurt zegt Hier waarom een suggestie nu niet kan.
    const bezig = hulpOverzicht(stand(suggestiesVan(begrip), { bezig: true }), contexten, "begrip")[0].regels;
    expect(bezig.find((x) => x.label === "/uitleg")?.uit).toBe("Lex is nog bezig");
  });
});
