import { describe, expect, it } from "vitest";

import { ONBEKEND, actiefKaartje, antwoordActie, antwoordTekst, beginstand, parseVraagkaart, type Vraagkaart } from "./vraagkaart";

const RUW = {
  intake_id: "ik1", soort: "vraag", stap: "regelingen", nr: 3, totaal: 5,
  vraag: "Welke regeling(en) horen erbij?", toelichting: "",
  opties: [
    { label: "Wet inkomstenbelasting 2001", waarde: "BWBR0011353", bron: { bwb_id: "BWBR0011353" } },
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

  it("leest de samenvatting alleen bij een samenvattingskaart", () => {
    const s = kaart({ soort: "samenvatting", stap: "samenvatting",
      samenvatting: { naam: "Box 3", analysevraag: "Wie?", afbakening: "Regelingen: nog te bepalen.", bronnen: ["Afd. 5.1", 3] } });
    expect(s.samenvatting).toEqual({ naam: "Box 3", analysevraag: "Wie?", afbakening: "Regelingen: nog te bepalen.", bronnen: ["Afd. 5.1"] });
  });
});

describe("het antwoord", () => {
  it("begint met wat Lex vooraf invulde: een optie geselecteerd, de rest als eigen tekst", () => {
    expect(beginstand(kaart())).toEqual({ gekozen: ["BWBR0011353"], eigen: "Awir" });
    expect(beginstand(kaart({ meerkeuze: false, vooringevuld: ["BWBR0011353", ONBEKEND] })).gekozen).toEqual(["BWBR0011353"]);
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
    expect(antwoordTekst(k, { intake_id: "ik1", stap: "samenvatting", actie: "wijzig", naar: "buiten" })).toBe("Pas wat erbuiten valt aan.");
  });
});

describe("actiefKaartje", () => {
  it("is het laatste kaartje, tot er een werkgebied uit is aangemaakt", () => {
    const k = kaart();
    expect(actiefKaartje([{ id: "a", vraagkaart: k }, { id: "b" }, { id: "c", vraagkaart: k }, { id: "d" }])).toBe("c");
    expect(actiefKaartje([{ id: "a", vraagkaart: k }, { id: "b", werkgebiedAangemaakt: true }])).toBeUndefined();
    expect(actiefKaartje([{ id: "a" }])).toBeUndefined();
  });
});
