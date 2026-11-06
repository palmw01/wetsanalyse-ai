import { describe, expect, it } from "vitest";

import {
  ONBEKEND, antwoordActie, antwoordTekst, beginstand, groepeerVragen, isLaatsteVraag, openVraag, parseAntwoordOp,
  parseVraagkaart, regelNamen, stilActie, typActie, vorige, type Vraagkaart,
} from "./vraagkaart";

describe("regels: één regel is één ding (4 nov 2026)", () => {
  it("noemt de regels naar wat het kaartje zegt, en zonder regel de deelvragen", () => {
    expect(regelNamen(null)).toMatchObject({ enkel: "deelvraag", label: "Eigen deelvraag", eerste: "Typ een eigen deelvraag…" });
    const b = regelNamen({ enkel: "bepaling", voorbeeld: "artikel 9 lid 2 Invorderingswet 1990" });
    expect(b).toMatchObject({ enkel: "bepaling", label: "Eigen bepaling", lijst: "Je eigen bepalingen",
      eerste: "Bijv. ‘artikel 9 lid 2 Invorderingswet 1990’", volgende: "Nog een bepaling…" });
  });

  it("leest `regel` van het kaartje en stuurt eigen bepalingen als regels", () => {
    const k = parseVraagkaart({ intake_id: "bs-wg1", stap: "bs_bepalingen", vraag: "De kernbepalingen", modus: "bronselectie",
      deelvraag_id: "d1", weergave: "paneel", regel: { enkel: "bepaling", voorbeeld: "artikel 9" } })!;
    expect(k.regel).toEqual({ enkel: "bepaling", voorbeeld: "artikel 9" });
    expect(parseVraagkaart({ intake_id: "x", stap: "naam", vraag: "?" })!.regel).toBeNull();
    expect(typActie(k, [" artikel 10 IW ", "", "artikel 3 IW"])).toEqual({ intake_id: "bs-wg1", stap: "bs_bepalingen",
      actie: "antwoord", teksten: ["artikel 10 IW", "artikel 3 IW"], deelvraag_id: "d1" });
    expect(typActie(k, ["", "  "])).toBeUndefined();
    expect(parseVraagkaart({ intake_id: "x", stap: "bs_toevoegen_treffers", vraag: "?" })).toBeUndefined();
  });
});

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
      afbakening: "Regelingen: nog te bepalen.", regelingen: [], gebeurtenis: "", bronnen: ["Afd. 5.1"], wijzigingen: [] });
    // Sinds 4 nov 2026: het zoekbereik en de gebeurtenis in plaats van de bronnen.
    const n = kaart({ soort: "samenvatting", stap: "samenvatting",
      samenvatting: { naam: "Box 3", regelingen: ["Wet IB 2001", 4], gebeurtenis: "heffing" } }).samenvatting!;
    expect([n.regelingen, n.gebeurtenis, n.bronnen]).toEqual([["Wet IB 2001"], "heffing", []]);
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

  it("‹ gaat naar de vorige stap, vanaf de samenvatting naar de gebeurtenis", () => {
    // De bronnen komen pas na de deelvragen en wat erbuiten valt (Handleiding 1f).
    expect(vorige(kaart({ terug: true }))).toEqual({ naar: "buiten" });
    expect(vorige(kaart({ stap: "analysevraag", terug: true }))).toEqual({ naar: "doel" });
    // Spoor I7: het thema is een kaartje van het aanvullen; ‹ gaat naar het praktijkvoorbeeld.
    expect(kaart({ stap: "thema", modus: "aanvullen", terug: true }).stap).toBe("thema");
    expect(vorige(kaart({ stap: "thema", modus: "aanvullen", terug: true }))).toEqual({ naar: "praktijkvoorbeeld" });
    expect(vorige(kaart({ terug: false }))).toBeUndefined();
    // De laatste stap is de gebeurtenis (4 nov 2026); de bronnen per deelvraag volgen in de bronselectie.
    expect(vorige(kaart({ stap: "samenvatting", soort: "samenvatting", terug: true, nr: 11, totaal: 11 })))
      .toEqual({ naar: "gebeurtenis" });
  });

  it("na de regelingen de gebeurtenis, met Verzend; een oud bepalingen-kaartje blijft leesbaar", () => {
    const g = kaart({ stap: "gebeurtenis", terug: true });
    expect(vorige(g)).toEqual({ naar: "regelingen" });
    expect(isLaatsteVraag(g)).toBe(true);
    expect(isLaatsteVraag(kaart({ stap: "regelingen" }))).toBe(false);
    expect(bep(1).deel).toEqual({ index: 1, totaal: 3, deelvraag: "Deelvraag 2?" });
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

describe("de bronselectie per deelvraag (spoor J)", () => {
  const bs = (over: Partial<Record<string, unknown>> = {}) => kaart({
    intake_id: "bs-wg1", modus: "bronselectie", stap: "bs_bepalingen", deelvraag_id: "d2", nr: 2, totaal: 4,
    vraag: "Welke bepalingen regelen deelvraag 2 zelf?", vooringevuld: [], ...over,
  });

  it("leest modus, stap en deelvraag, en een klik en het antwoord dragen de deelvraag", () => {
    const k = bs();
    expect([k.modus, k.stap, k.deelvraag_id, isLaatsteVraag(k)]).toEqual(["bronselectie", "bs_bepalingen", "d2", true]);
    const a = antwoordActie(k, ["BWBR0011353"], "Onderzoek ook de bijzondere invorderbaarheid.")!;
    expect(a.deelvraag_id).toBe("d2");
    expect(parseAntwoordOp({ intake_id: "bs-wg1", stap: "bs_bepalingen", actie: "antwoord", deelvraag_id: "d2" })?.deelvraag_id).toBe("d2");
    expect(antwoordTekst(k, { ...a, actie: "afbreken" })).toBe("Zet de bronselectie even stil.");
    // Een intakekaartje draagt geen deelvraag.
    expect(antwoordActie(kaart(), ["BWBR0011353"], "")?.deelvraag_id).toBeUndefined();
    expect(parseVraagkaart({ ...RUW, intake_id: "bs-wg1", stap: "bs_onbekend" })).toBeUndefined();
  });

  it("dezelfde stap bij twee deelvragen geeft twee paren in de Vragen-kaart", () => {
    const k1 = bs({ deelvraag_id: "d1", nr: 1 }), k2 = bs();
    const items = [
      { id: "a1", type: "antwoord", tekst: "", vraagkaart: k1 },
      { id: "u1", type: "user", tekst: "Artikel 9", antwoordOp: { intake_id: "bs-wg1", stap: "bs_bepalingen" as const, actie: "antwoord" as const, deelvraag_id: "d1" } },
      { id: "a2", type: "antwoord", tekst: "", vraagkaart: k2 },
      { id: "u2", type: "user", tekst: "Artikel 10", antwoordOp: { intake_id: "bs-wg1", stap: "bs_bepalingen" as const, actie: "antwoord" as const, deelvraag_id: "d2" } },
    ];
    const { groepen } = groepeerVragen(items, false);
    const [g] = [...groepen.values()];
    expect(g.paren.map((p) => [p.deelvraag_id, p.antwoord])).toEqual([["d1", "Artikel 9"], ["d2", "Artikel 10"]]);
  });
});

describe("de bronselectie stilzetten vanaf het compacte kaartje", () => {
  it("is de actie afbreken op de stap en deelvraag van het kaartje", () => {
    const k = { intake_id: "bs-wg1", stap: "bs_bepalingen", deelvraag_id: "d1" } as unknown as Vraagkaart;
    expect(stilActie(k)).toEqual({ intake_id: "bs-wg1", stap: "bs_bepalingen", actie: "afbreken", deelvraag_id: "d1" });
    expect(antwoordTekst({ ...k, modus: "bronselectie" } as Vraagkaart, stilActie(k))).toBe("Zet de bronselectie even stil.");
  });
});

describe("de keuzekaart van de begrippen-agent", () => {
  it("is leesbaar en geeft geen stap naar een samenvatting", () => {
    const k = parseVraagkaart({ intake_id: "bk-wg1", modus: "begrip", stap: "begrip_kiezen", vraag: "Welk begrip?",
      opties: [{ label: "akte", waarde: "betekenisverschil:a:b" }] });
    expect(k?.modus).toBe("begrip");
    expect(isLaatsteVraag(k!)).toBe(true);
    expect(antwoordTekst(k!, { ...{ intake_id: "bk-wg1", stap: "begrip_kiezen" }, actie: "afbreken" } as never)).toBe("Laat maar.");
  });
});
