import { readFileSync } from "node:fs";
import { globSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  BUBBEL_MARGE, domineert, hervatIndex, indexVan, LEGE_STAND, moetStarten, plaatsBubbel,
  RONDLEIDING_VERSIE, STAPPEN, vraagtArtefact, zichtbareStappen, type Vak,
} from "./rondleiding";
import {
  DEMO_SLUG, demoBron, maakDemoDocument, maakDemoScene, pasDemoBeslissingToe,
  voegDemoElementToe, wisDemoElement, zetDemoStatus,
} from "./rondleidingDemo";
import { vindPositie } from "./selectie";
import { BESLIST_LIFECYCLES } from "./annotatie";

describe("de stappenlijst", () => {
  it("heeft unieke ids", () => {
    const ids = STAPPEN.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("loopt van oriëntatie naar afronding zonder terug te springen", () => {
    const orde = ["orientatie", "opdracht", "beoordelen", "afronding"];
    const posities = STAPPEN.map((s) => orde.indexOf(s.fase));
    expect(posities).toEqual([...posities].sort((a, b) => a - b));
  });

  it("opent het artefact pas nadat de stap erover is gegaan", () => {
    const eersteMetArtefact = STAPPEN.findIndex((s) => s.artefactOpen);
    // De stap die het artefact laat openen ("chip") staat er direct vóór en heeft hem zelf nog niet
    // nodig — anders wijst de rondleiding naar een paneel dat nog dicht is.
    expect(STAPPEN[eersteMetArtefact - 1].anker).toBe("chip");
    expect(STAPPEN[eersteMetArtefact - 1].artefactOpen).toBeUndefined();
  });

  it("laat elke stap iets aanwijzen", () => {
    for (const s of STAPPEN) expect(s.anker.length).toBeGreaterThan(0);
  });

  it("filtert beheerdersstappen weg voor een analist", () => {
    expect(zichtbareStappen(false).every((s) => !s.alleenBeheerder)).toBe(true);
    expect(zichtbareStappen(true).length).toBeGreaterThanOrEqual(zichtbareStappen(false).length);
  });

  it("weet welke stap het artefact nodig heeft", () => {
    const i = STAPPEN.findIndex((s) => s.artefactOpen);
    expect(vraagtArtefact(STAPPEN, i)).toBe(true);
    expect(vraagtArtefact(STAPPEN, 0)).toBe(false);
  });
});

describe("hervatten", () => {
  it("pakt de bewaarde stap op", () => {
    expect(hervatIndex(STAPPEN, STAPPEN[4].id)).toBe(4);
  });

  it("begint opnieuw als de bewaarde stap niet meer bestaat", () => {
    expect(hervatIndex(STAPPEN, "een-stap-die-weg-is")).toBe(0);
    expect(hervatIndex(STAPPEN, undefined)).toBe(0);
  });

  it("kent geen stap zonder id", () => {
    expect(indexVan(STAPPEN, undefined)).toBe(-1);
  });
});

describe("moetStarten", () => {
  it("start bij een lege stand", () => {
    expect(moetStarten(LEGE_STAND)).toBe(true);
  });

  it("start niet meer na afronden", () => {
    expect(moetStarten({ versie: RONDLEIDING_VERSIE, gezien: true })).toBe(false);
  });

  it("biedt zich opnieuw aan na een nieuwe versie", () => {
    expect(moetStarten({ versie: RONDLEIDING_VERSIE - 1, gezien: true })).toBe(true);
  });
});

describe("de voorbeeldscène", () => {
  it("markeert uitsluitend fragmenten die letterlijk in de wettekst staan", () => {
    const doc = maakDemoDocument();
    const bron = demoBron();
    const bezet: { start: number; eind: number }[] = [];
    for (const el of doc.elementen) {
      expect(el.anker, `${el.klasse} — "${el.tekst}"`).not.toBeNull();
      // Zelfde terugvindweg als het documentpaneel: staat de markering niet, dan zweeft hij.
      const pos = vindPositie(bron, el.tekst, el.anker, bezet);
      expect(pos, `${el.klasse} — "${el.tekst}"`).toBeGreaterThanOrEqual(0);
      bezet.push({ start: pos, eind: pos + el.tekst.length });
    }
  });

  it("laat de markeringen niet overlappen", () => {
    const bereiken = maakDemoDocument()
      .elementen.map((el) => el.anker!)
      .sort((a, b) => a.start - b.start);
    for (let i = 1; i < bereiken.length; i++) {
      expect(bereiken[i].start).toBeGreaterThanOrEqual(bereiken[i - 1].eind);
    }
  });

  it("begint met alles nog te beoordelen", () => {
    const doc = maakDemoDocument();
    expect(doc.elementen.length).toBeGreaterThan(5);
    expect(doc.elementen.every((el) => !BESLIST_LIFECYCLES.includes(el.lifecycle))).toBe(true);
  });

  it("toont alle drie de aandachtniveaus", () => {
    const niveaus = new Set(maakDemoDocument().elementen.map((el) => el.aandacht));
    expect(niveaus).toEqual(new Set(["groen", "geel", "rood"]));
  });

  it("levert een thread met een annotatie die naar het voorbeelddocument wijst", () => {
    const scene = maakDemoScene();
    const chip = scene.items.find((i) => i.type === "annotatie");
    expect(chip).toBeDefined();
    expect(chip!.type === "annotatie" && chip!.slug).toBe(DEMO_SLUG);
    expect(scene.docs[DEMO_SLUG]).toBeDefined();
    expect(scene.infos[DEMO_SLUG]).toBeDefined();
  });

  it("draagt overal het voorbeeld-label", () => {
    const scene = maakDemoScene();
    expect(scene.docs[DEMO_SLUG].citeertitel).toContain("VOORBEELD");
    const chip = scene.items.find((i) => i.type === "annotatie");
    expect(chip!.type === "annotatie" && chip!.titel).toContain("VOORBEELD");
    // Ook de sidebar-lijst: die staat naast de echte gesprekken van de gebruiker.
    for (const g of scene.gesprekken) expect(g.titel).toContain("VOORBEELD");
  });

  it("levert een gevulde gesprekkenlijst voor de sidebar", () => {
    // De stap "Je werk terugvinden" wijst de sidebar aan. Die haalt zijn lijst normaal bij de api,
    // en bij een nieuwe gebruiker — precies wie de rondleiding krijgt — is die leeg.
    const scene = maakDemoScene();
    expect(scene.gesprekken.length).toBeGreaterThan(0);
    expect(new Set(scene.gesprekken.map((g) => g.id)).size).toBe(scene.gesprekken.length);
  });

  it("bouwt elke keer een schone lei", () => {
    const eerste = maakDemoDocument();
    const beslist = pasDemoBeslissingToe(eerste, eerste.elementen[0].id, { type: "approve", comment: "" });
    expect(beslist.elementen[0].lifecycle).toBe("human_approved");
    // Het origineel blijft ongemoeid, en een volgende start begint weer bij nul.
    expect(eerste.elementen[0].lifecycle).toBe("critic_checked");
    expect(maakDemoDocument().elementen[0].lifecycle).toBe("critic_checked");
  });
});

describe("de demo-mutaties", () => {
  it("verwerpt een voorstel zonder het te wissen", () => {
    const doc = maakDemoDocument();
    const na = pasDemoBeslissingToe(doc, doc.elementen[1].id, {
      type: "reject", comment: "", review_reason: "verkeerde_klasse",
    });
    expect(na.elementen).toHaveLength(doc.elementen.length);
    expect(na.elementen[1].lifecycle).toBe("rejected");
  });

  it("neemt een klassewijziging over", () => {
    const doc = maakDemoDocument();
    const na = pasDemoBeslissingToe(doc, doc.elementen[0].id, {
      type: "edit", comment: "", wijziging: { klasse: "Rechtssubject" },
    });
    expect(na.elementen[0].klasse).toBe("Rechtssubject");
    expect(na.elementen[0].lifecycle).toBe("edited");
    expect(na.elementen[0].gewijzigd_door).toBe("mens");
  });

  it("zet een eigen markering er meteen goedgekeurd bij en wist hem weer", () => {
    const doc = maakDemoDocument();
    const bron = demoBron();
    const { doc: bij, id } = voegDemoElementToe(doc, {
      klasse: "Rechtsobject", tekst: "het aanslagbiljet", lid: "1", toelichting: "",
      anker: { lid: "1", start: 0, eind: 16, voor: "", na: "", bron_hash: "" },
    });
    expect(bron.length).toBeGreaterThan(0);
    expect(bij.elementen).toHaveLength(doc.elementen.length + 1);
    expect(bij.elementen.at(-1)!.lifecycle).toBe("human_approved");
    expect(bij.elementen.at(-1)!.herkomst).toBe("mens");
    expect(wisDemoElement(bij, id).elementen).toHaveLength(doc.elementen.length);
  });

  it("rondt af en heropent", () => {
    const doc = maakDemoDocument();
    expect(zetDemoStatus(doc, "geaccordeerd").status).toBe("geaccordeerd");
    expect(zetDemoStatus(zetDemoStatus(doc, "geaccordeerd"), "in_review").status).toBe("in_review");
  });
});

describe("waar de bubbel komt te staan", () => {
  const SCHERM = { breedte: 1440, hoogte: 900 };
  const TELEFOON = { breedte: 390, hoogte: 844 };
  const BUBBEL = { breedte: 340, hoogte: 220 };

  /** Ligt de bubbel volledig binnen het scherm? Dat is de eis waar het eerder op misging. */
  function binnenBeeld(
    plaatsing: ReturnType<typeof plaatsBubbel>,
    bubbel = BUBBEL,
    scherm = SCHERM,
  ): boolean {
    if (plaatsing.modus === "midden") return true;
    return (
      plaatsing.top >= 0 &&
      plaatsing.left >= 0 &&
      plaatsing.top + bubbel.hoogte <= scherm.hoogte &&
      plaatsing.left + bubbel.breedte <= scherm.breedte
    );
  }

  it("centreert als er geen element is", () => {
    expect(plaatsBubbel(null, BUBBEL, SCHERM)).toEqual({ modus: "midden" });
  });

  it("centreert bij het gespreksvenster in plaats van het aan te wijzen", () => {
    // De thread is de scroll-container tussen topbar en invoerveld: bijna de volle hoogte. Hier
    // ging het mis — "de kant met de meeste ruimte" leverde een bubbel onder de schermrand.
    const thread: Vak = { top: 56, left: 288, breedte: 1152, hoogte: 770 };
    expect(plaatsBubbel(thread, BUBBEL, SCHERM)).toEqual({ modus: "midden" });
  });

  it("centreert bij de sidebar over de volle hoogte", () => {
    const sidebar: Vak = { top: 0, left: 0, breedte: 272, hoogte: 900 };
    expect(plaatsBubbel(sidebar, BUBBEL, SCHERM)).toEqual({ modus: "midden" });
  });

  it("hangt onder een element dat bovenin staat", () => {
    const kop: Vak = { top: 80, left: 400, breedte: 300, hoogte: 40 };
    const p = plaatsBubbel(kop, BUBBEL, SCHERM);
    expect(p.modus).toBe("onder");
    if (p.modus !== "midden") expect(p.top).toBe(80 + 40 + BUBBEL_MARGE);
    expect(binnenBeeld(p)).toBe(true);
  });

  it("hangt boven een element dat onderin staat", () => {
    // Het invoerveld: onderaan het scherm, dus onder past de bubbel niet meer.
    const invoer: Vak = { top: 800, left: 400, breedte: 600, hoogte: 60 };
    const p = plaatsBubbel(invoer, BUBBEL, SCHERM);
    expect(p.modus).toBe("boven");
    if (p.modus !== "midden") expect(p.top + BUBBEL.hoogte).toBe(800 - BUBBEL_MARGE);
    expect(binnenBeeld(p)).toBe(true);
  });

  it("wijkt naar opzij als er boven noch onder ruimte is", () => {
    // Een hoge kolom links: boven en onder blijft 200px over, te weinig voor een bubbel van 220.
    // Het scherm domineren doet hij niet, dus wijkt de bubbel naar rechts uit.
    const band: Vak = { top: 200, left: 20, breedte: 500, hoogte: 500 };
    const p = plaatsBubbel(band, BUBBEL, SCHERM);
    expect(p.modus).toBe("rechts");
    expect(binnenBeeld(p)).toBe(true);
  });

  it("trekt een element aan de rand niet mee naar buiten", () => {
    // Een knop helemaal rechts: de bubbel zou uitgelijnd op het midden buiten beeld beginnen.
    const knop: Vak = { top: 100, left: 1380, breedte: 50, hoogte: 32 };
    const p = plaatsBubbel(knop, BUBBEL, SCHERM);
    expect(binnenBeeld(p)).toBe(true);
  });

  it("houdt de bubbel op een telefoon binnen beeld", () => {
    const kaart: Vak = { top: 300, left: 12, breedte: 366, hoogte: 120 };
    const p = plaatsBubbel(kaart, BUBBEL, TELEFOON);
    expect(binnenBeeld(p, BUBBEL, TELEFOON)).toBe(true);
  });

  it("herkent een element dat het scherm domineert", () => {
    // Op de hoogte alleen (een smalle kolom over de volle hoogte, zoals de sidebar) …
    expect(domineert({ top: 0, left: 0, breedte: 200, hoogte: 700 }, SCHERM)).toBe(true);
    // … en op het oppervlak alleen (breed en niet eens zo hoog).
    expect(domineert({ top: 0, left: 0, breedte: 1400, hoogte: 500 }, SCHERM)).toBe(true);
    expect(domineert({ top: 100, left: 100, breedte: 300, hoogte: 40 }, SCHERM)).toBe(false);
  });
});

describe("de ankers bestaan echt", () => {
  // Een stap die naar een `data-tour` wijst dat niemand meer zet, valt stil terug op een
  // gecentreerde kaart: de rondleiding breekt niet, maar wijst ook niets meer aan — en dat merk je
  // pas als je hem zelf doorloopt. Vandaar deze koppeling aan de bron.
  const bron = readFileSync(new URL("./rondleiding.test.ts", import.meta.url).pathname, "utf-8");
  const componenten = globSync("components/**/*.tsx").map((p) => readFileSync(p, "utf-8")).join("\n");

  /** Staat dit anker ergens in de componenten? Twee vormen tellen mee: het letterlijke attribuut,
   *  en de expressievorm (`data-tour={eerste ? "review-kaart" : undefined}`) die de reviewlijst
   *  gebruikt om alleen de bovenste kaart te markeren. */
  const gezet = (sleutel: string) =>
    componenten.includes(`data-tour="${sleutel}"`) ||
    (componenten.includes("data-tour={") && componenten.includes(`"${sleutel}"`));

  it("vindt elk anker terug in een component", () => {
    expect(bron.length).toBeGreaterThan(0);
    for (const stap of STAPPEN) {
      expect(gezet(stap.anker), `anker "${stap.anker}" (stap ${stap.id})`).toBe(true);
      if (stap.ankerSmal) expect(gezet(stap.ankerSmal), `anker "${stap.ankerSmal}"`).toBe(true);
    }
  });

  it("valt niet voor een anker dat nergens staat", () => {
    expect(gezet("dit-anker-bestaat-niet")).toBe(false);
  });
});
