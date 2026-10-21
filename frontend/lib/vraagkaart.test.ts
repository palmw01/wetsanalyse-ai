import { describe, expect, it } from "vitest";

import {
  ONBEKEND, antwoordActie, antwoordTekst, beginstand, groepeerVragen, isLaatsteVraag, openVraag, parseAntwoordOp,
  parseVraagkaart, vorige, type Vraagkaart,
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
      afbakening: "Regelingen: nog te bepalen.", bronnen: ["Afd. 5.1"], wijzigingen: [] });
    expect(s.modus).toBe("samenstellen");
  });

  it("kent de stappen van startactiviteit a en de deelvragen", () => {
    for (const stap of ["aanleiding", "context", "doel", "praktijkvoorbeeld", "deelvragen"]) {
      expect(kaart({ stap }).stap).toBe(stap);
    }
    expect(kaart({ meer_tekst: true }).meer_tekst).toBe(true);
    expect(kaart().meer_tekst).toBe(false);
  });
});

describe("aanvullen", () => {
  const aanvul = (over: Partial<Record<string, unknown>> = {}) =>
    kaart({ modus: "aanvullen", stap: "praktijkvoorbeeld", nr: 1, totaal: 2, opties: [], vooringevuld: [], ...over });

  it("leest de modus en de wijzigingen toen → nu; een rij zonder veld valt weg", () => {
    const s = aanvul({ soort: "samenvatting", stap: "samenvatting", samenvatting: { wijzigingen: [
      { veld: "praktijkvoorbeeld", label: "Praktijkvoorbeeld", toen: "", nu: "Een spaarder." }, { label: "kapot" }] } });
    expect(s.modus).toBe("aanvullen");
    expect(s.samenvatting?.wijzigingen).toEqual([{ veld: "praktijkvoorbeeld", label: "Praktijkvoorbeeld", toen: "",
      nu: "Een spaarder." }]);
    expect(kaart({ modus: "iets" }).modus).toBe("samenstellen");
  });

  it("vooringevuld staat in het tekstveld; Verzend op de laatste gevraagde stap", () => {
    expect(beginstand(aanvul({ vooringevuld: ["Een spaarder."] })).eigen).toBe("Een spaarder.");
    expect(isLaatsteVraag(aanvul())).toBe(false);
    expect(isLaatsteVraag(aanvul({ nr: 2 }))).toBe(true);
    expect(isLaatsteVraag(aanvul({ soort: "samenvatting", stap: "samenvatting", nr: 2 }))).toBe(false);
  });

  it("opslaan is een klik met een eigen tekst en een eigen antwoord", () => {
    const s = aanvul({ soort: "samenvatting", stap: "samenvatting" });
    expect(antwoordTekst(s, { intake_id: "ik1", stap: "samenvatting", actie: "opslaan" })).toBe("Sla de wijziging op.");
    expect(antwoordTekst(s, { intake_id: "ik1", stap: "samenvatting", actie: "afbreken" })).toBe("Stop met aanvullen.");
    expect(parseAntwoordOp({ intake_id: "ik1", stap: "samenvatting", actie: "opslaan" })?.actie).toBe("opslaan");
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
  const bep = (index: number, totaal = 3) => kaart({ stap: "bepalingen", terug: true, nr: 10 + index, totaal: 9 + totaal,
    deel: { index, totaal, deelvraag: `Deelvraag ${index + 1}?` } });

  it("‹ gaat naar de vorige stap, vanaf de samenvatting naar het laatste bepalingen-kaartje", () => {
    // De bronnen komen pas na de deelvragen en wat erbuiten valt (Handleiding 1f).
    expect(vorige(kaart({ terug: true }))).toEqual({ naar: "buiten" });
    expect(vorige(kaart({ stap: "analysevraag", terug: true }))).toEqual({ naar: "doel" });
    expect(vorige(kaart({ terug: false }))).toBeUndefined();
    // Negen vaste stappen en drie deelvragen: de samenvatting is 12 van 12, terug is deel 3 (index 2).
    expect(vorige(kaart({ stap: "samenvatting", soort: "samenvatting", terug: true, nr: 12, totaal: 12 })))
      .toEqual({ naar: "bepalingen", naar_deel: 2 });
  });

  it("de bepalingen hebben een kaartje per deelvraag: ‹ bladert per deel, Verzend op het laatste", () => {
    expect(bep(0).deel).toEqual({ index: 0, totaal: 3, deelvraag: "Deelvraag 1?" });
    expect(vorige(bep(0))).toEqual({ naar: "regelingen" });
    expect(vorige(bep(2))).toEqual({ naar: "bepalingen", naar_deel: 1 });
    expect(isLaatsteVraag(bep(1))).toBe(false);
    expect(isLaatsteVraag(bep(2))).toBe(true);
    expect(isLaatsteVraag(kaart())).toBe(false);
    // Zonder deelvragen één kaartje over de analysevraag.
    expect(isLaatsteVraag(kaart({ stap: "bepalingen", deel: { index: 0, totaal: 1, deelvraag: null } }))).toBe(true);
    // Een keuze en terugbladeren dragen het deel.
    expect(antwoordActie(bep(1), ["urn:bwb:x"], "")).toMatchObject({ stap: "bepalingen", deel: 1 });
    expect(antwoordTekst(bep(2), { intake_id: "ik1", stap: "bepalingen", deel: 2, actie: "wijzig", naar: "bepalingen", naar_deel: 1 }))
      .toBe("Terug naar de bepalingen bij deelvraag 2.");
    // `deel` alleen bij de bepalingen.
    expect(kaart({ deel: { index: 0, totaal: 1, deelvraag: null } }).deel).toBeNull();
    expect(parseAntwoordOp({ intake_id: "ik1", stap: "bepalingen", deel: 1 })).toEqual(
      { intake_id: "ik1", stap: "bepalingen", deel: 1, actie: "antwoord" });
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

  it("elk bepalingen-kaartje is een eigen paar: deelvraag 2 vervangt deelvraag 1 niet", () => {
    const bep = (index: number) => kaart({ stap: "bepalingen", vraag: `Welke bepalingen horen bij deelvraag ${index + 1}?`,
      deel: { index, totaal: 2, deelvraag: "?" } });
    const antDeel = (id: string, deel: number, tekst: string, actie: "antwoord" | "wijzig" = "antwoord") =>
      ({ id, type: "user", tekst, antwoordOp: { intake_id: "ik1", stap: "bepalingen" as const, deel, actie } });
    const items = [{ id: "l1", type: "antwoord", tekst: "", vraagkaart: bep(0) }, antDeel("u1", 0, "Artikel 6:7"),
      { id: "l2", type: "antwoord", tekst: "", vraagkaart: bep(1) }, antDeel("u2", 1, "Artikel 6:5, lid 1"),
      { id: "l3", type: "antwoord", tekst: "", vraagkaart: kaart({ stap: "samenvatting", soort: "samenvatting" }) }];
    const g = groepeerVragen(items, false).groepen.get("l1")!;
    expect(g.paren.map((p) => [p.deel, p.antwoord])).toEqual([[0, "Artikel 6:7"], [1, "Artikel 6:5, lid 1"]]);
    // Terug naar deel 1 en opnieuw beantwoorden: de reeks begint daar opnieuw.
    const opnieuw = [...items, antDeel("u3", 0, "Terug.", "wijzig"),
      { id: "l4", type: "antwoord", tekst: "", vraagkaart: bep(0) }, antDeel("u4", 0, "Artikel 6:8, lid 1")];
    const h = groepeerVragen(opnieuw, false).groepen.get("l1")!;
    expect(h.paren.map((p) => [p.deel, p.antwoord])).toEqual([[0, "Artikel 6:8, lid 1"]]);
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
