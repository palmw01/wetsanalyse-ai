import { describe, expect, it } from "vitest";

import {
  ONBEKEND, antwoordActie, antwoordTekst, beginstand, groepeerVragen, isLaatsteVraag, openVraag, parseAntwoordOp,
  parseVraagkaart, vorigeStap, type Vraagkaart,
} from "./vraagkaart";

const RUW = {
  intake_id: "ik1", soort: "vraag", stap: "regelingen", nr: 3, totaal: 5,
  vraag: "Welke regeling(en) horen erbij?", toelichting: "",
  opties: [
    { label: "Wet inkomstenbelasting 2001", waarde: "BWBR0011353", bron: { bwb_id: "BWBR0011353" }, omschrijving: "wet · 2 delen" },
    { label: "Weet ik (nog) niet", waarde: ONBEKEND, bron: {} },
    { label: "", waarde: "kapot" },
  ],
  meerkeuze: true, vrije_tekst: true, overslaanbaar: true, vooringevuld: ["BWBR0011353", "Awir"], samenvatting: {},
};

const kaart = (over: Partial<Record<string, unknown>> = {}) => parseVraagkaart({ ...RUW, ...over }) as Vraagkaart;

describe("parseVraagkaart", () => {
  it("neemt een geldig kaartje over en laat een optie zonder label weg", () => {
    const k = kaart();
    expect(k.stap).toBe("regelingen");
    expect(k.opties.map((o) => o.waarde)).toEqual(["BWBR0011353", ONBEKEND]);
    expect(k.samenvatting).toBeNull();
  });

  it("weigert een kaartje zonder intake, met een onbekende stap of zonder vraag", () => {
    expect(parseVraagkaart({ ...RUW, intake_id: "met spatie" })).toBeUndefined();
    expect(parseVraagkaart({ ...RUW, stap: "peildatum" })).toBeUndefined();
    expect(parseVraagkaart({ ...RUW, vraag: "" })).toBeUndefined();
    expect(parseVraagkaart(null)).toBeUndefined();
  });

  it("leest de samenvatting alleen bij een samenvattingskaart, met het hele dossier", () => {
    const s = kaart({ soort: "samenvatting", stap: "samenvatting",
      samenvatting: { naam: "Box 3", aanleiding: "Wetswijziging.", doel: "Webservices.", analysevraag: "Wie?",
        deelvragen: ["Wat telt mee?", 7], afbakening: "Regelingen: nog te bepalen.", bronnen: ["Afd. 5.1", 3] } });
    expect(s.samenvatting).toEqual({ naam: "Box 3", aanleiding: "Wetswijziging.", context: "", doel: "Webservices.",
      analysevraag: "Wie?", praktijkvoorbeeld: "", deelvragen: ["Wat telt mee?"],
      afbakening: "Regelingen: nog te bepalen.", bronnen: ["Afd. 5.1"] });
  });

  it("kent de stappen van startactiviteit a en de deelvragen", () => {
    for (const stap of ["aanleiding", "context", "doel", "praktijkvoorbeeld", "deelvragen"]) {
      expect(kaart({ stap }).stap).toBe(stap);
    }
    expect(kaart({ meer_tekst: true }).meer_tekst).toBe(true);
    expect(kaart().meer_tekst).toBe(false);
  });
});

describe("het antwoord", () => {
  it("begint met wat Lex vooraf invulde: een optie geselecteerd, de rest als eigen tekst", () => {
    expect(beginstand(kaart())).toEqual({ gekozen: ["BWBR0011353"], eigen: "Awir", teksten: [] });
    expect(beginstand(kaart({ meerkeuze: false, vooringevuld: ["BWBR0011353", ONBEKEND] })).gekozen).toEqual(["BWBR0011353"]);
  });

  it("bij meer eigen antwoorden krijgt elk een regel, met een lege erachter", () => {
    const k = kaart({ stap: "deelvragen", meer_tekst: true, opties: [{ label: "Wie?", waarde: "Wie?", bron: {} }],
      vooringevuld: ["Wie?", "Eigen een?", "Eigen twee?"] });
    expect(beginstand(k)).toEqual({ gekozen: ["Wie?"], eigen: "", teksten: ["Eigen een?", "Eigen twee?", ""] });
    const a = antwoordActie(k, ["Wie?"], "", [" Eigen een? ", "", "Eigen twee?"]);
    expect(a).toEqual({ intake_id: "ik1", stap: "deelvragen", actie: "antwoord", keuzes: ["Wie?"],
      teksten: ["Eigen een?", "Eigen twee?"] });
    expect(antwoordActie(k, [], "", ["", " "])).toBeUndefined();
    expect(antwoordTekst(k, a!)).toBe("Wie?; Eigen een?; Eigen twee?");
  });

  it("zonder keuze en zonder tekst is er geen antwoord", () => {
    const k = kaart();
    expect(antwoordActie(k, [], "  ")).toBeUndefined();
    expect(antwoordActie(k, ["BWBR0011353"], "")).toEqual(
      { intake_id: "ik1", stap: "regelingen", actie: "antwoord", keuzes: ["BWBR0011353"] });
    expect(antwoordActie(k, [], " Awir ")?.tekst).toBe("Awir");
  });

  it("de tekst in het gesprek noemt de labels, niet de waarden", () => {
    const k = kaart();
    expect(antwoordTekst(k, { intake_id: "ik1", stap: "regelingen", actie: "antwoord", keuzes: ["BWBR0011353", ONBEKEND] }))
      .toBe("Wet inkomstenbelasting 2001; Weet ik (nog) niet");
    expect(antwoordTekst(k, { intake_id: "ik1", stap: "samenvatting", actie: "aanmaken" })).toBe("Maak het werkgebied aan.");
    expect(antwoordTekst(k, { intake_id: "ik1", stap: "samenvatting", actie: "wijzig", naar: "buiten" })).toBe("Terug naar wat erbuiten valt.");
  });
});

describe("parse van de nieuwe velden", () => {
  it("leest omschrijving, terug en beantwoord", () => {
    const k = kaart({ terug: true, beantwoord: true });
    expect(k.opties[0].omschrijving).toBe("wet · 2 delen");
    expect([k.terug, k.beantwoord]).toEqual([true, true]);
    expect(kaart().terug).toBe(false);
  });

  it("een antwoord op een kaartje, streng op intake en stap", () => {
    expect(parseAntwoordOp({ intake_id: "ik1", stap: "naam", actie: "overslaan" })).toEqual({ intake_id: "ik1", stap: "naam", actie: "overslaan" });
    expect(parseAntwoordOp({ intake_id: "ik1", stap: "naam" })?.actie).toBe("antwoord");
    expect(parseAntwoordOp({ intake_id: "ik1", stap: "peildatum" })).toBeUndefined();
    expect(parseAntwoordOp(undefined)).toBeUndefined();
  });
});

describe("bladeren", () => {
  it("‹ gaat naar de vorige stap, vanaf de samenvatting naar de laatste vraag", () => {
    // De bronnen komen pas na de deelvragen en wat erbuiten valt (Handleiding 1f).
    expect(vorigeStap(kaart({ terug: true }))).toBe("buiten");
    expect(vorigeStap(kaart({ stap: "analysevraag", terug: true }))).toBe("doel");
    expect(vorigeStap(kaart({ terug: false }))).toBeUndefined();
    expect(vorigeStap(kaart({ stap: "samenvatting", soort: "samenvatting", terug: true }))).toBe("onderdelen");
    expect(isLaatsteVraag(kaart({ stap: "onderdelen" }))).toBe(true);
    expect(isLaatsteVraag(kaart())).toBe(false);
  });
});

describe("groepeerVragen", () => {
  const naam = kaart({ stap: "naam", nr: 1, vraag: "Hoe noemen we het werkgebied?", meerkeuze: false, opties: [] });
  const vraag = kaart({ stap: "analysevraag", nr: 2, vraag: "Wat is de analysevraag?", opties: [] });
  const ant = (id: string, stap: Vraagkaart["stap"], tekst: string, actie: "antwoord" | "overslaan" | "wijzig" = "antwoord") =>
    ({ id, type: "user", tekst, antwoordOp: { intake_id: "ik1", stap, actie } });

  it("bundelt vragen en antwoorden in één kaart; de antwoordbubbels en latere vragen verdwijnen", () => {
    const items = [
      { id: "u0", type: "user", tekst: "Kunnen we een werkgebied samenstellen?" },
      { id: "l1", type: "antwoord", tekst: "Laten we beginnen.", vraagkaart: naam },
      ant("u1", "naam", "Box 3"),
      { id: "l2", type: "antwoord", tekst: "Dan de vraag.", vraagkaart: vraag },
    ];
    const { groepen, verborgen } = groepeerVragen(items, false);
    expect([...groepen.keys()]).toEqual(["l1"]);
    const g = groepen.get("l1")!;
    expect(g.tekst).toBe("Laten we beginnen.");
    expect(g.paren).toEqual([{ stap: "naam", vraag: "Hoe noemen we het werkgebied?", antwoord: "Box 3", overgeslagen: false }]);
    expect(g.open?.stap).toBe("analysevraag");
    expect(g.openId).toBe("l2");
    expect([...verborgen].sort()).toEqual(["l2", "u1"]);
    expect(openVraag(groepen)?.openId).toBe("l2");
  });

  it("de lopende beurt na een antwoord is 'Nadenken…', geen eigen rij", () => {
    const items = [{ id: "l1", type: "antwoord", tekst: "", vraagkaart: naam }, ant("u1", "naam", "Box 3"),
      { id: "l2", type: "antwoord", tekst: "" }];
    const { groepen, verborgen } = groepeerVragen(items, true);
    expect(groepen.get("l1")?.denkt).toBe(true);
    expect(verborgen.has("l2")).toBe(true);
    // Klaar en zonder kaartje (bijvoorbeeld na afbreken): gewoon een rij, en geen open vraag.
    const klaar = groepeerVragen(items, false);
    expect(klaar.verborgen.has("l2")).toBe(false);
    expect(openVraag(klaar.groepen)).toBeUndefined();
  });

  it("een tussenvraag breekt de kaart, maar de open vraag blijft open", () => {
    const items = [{ id: "l1", type: "antwoord", tekst: "", vraagkaart: naam }, ant("u1", "naam", "Box 3"),
      { id: "l2", type: "antwoord", tekst: "", vraagkaart: vraag },
      { id: "u2", type: "user", tekst: "Wat is box 3?" }, { id: "l3", type: "antwoord", tekst: "Sparen en beleggen." }];
    const { groepen, verborgen } = groepeerVragen(items, false);
    expect(verborgen.has("u2") || verborgen.has("l3")).toBe(false);
    expect(openVraag(groepen)?.open?.stap).toBe("analysevraag");
  });

  it("overslaan heet zo, en opnieuw beantwoorden na terugbladeren vervangt het paar", () => {
    const items = [{ id: "l1", type: "antwoord", tekst: "", vraagkaart: naam }, ant("u1", "naam", "Box 3"),
      { id: "l2", type: "antwoord", tekst: "", vraagkaart: vraag }, ant("u2", "analysevraag", "Sla deze vraag over.", "overslaan"),
      { id: "l3", type: "antwoord", tekst: "", vraagkaart: kaart({ stap: "regelingen" }) },
      ant("u3", "regelingen", "Terug naar de naam.", "wijzig"),
      { id: "l4", type: "antwoord", tekst: "", vraagkaart: naam }, ant("u4", "naam", "Box 3-heffing")];
    const g = groepeerVragen(items, false).groepen.get("l1")!;
    expect(g.paren.map((p) => [p.stap, p.antwoord, p.overgeslagen])).toEqual([["naam", "Box 3-heffing", false]]);
  });
});
