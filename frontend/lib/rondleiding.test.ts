import { readFileSync } from "node:fs";
import { globSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  artefactActie, BUBBEL_MARGE, domineert, hervatIndex, indexVan, klikGat, LEGE_STAND,
  maskRechthoeken, moetStarten, uitsnede, zichtbaarDeel,
  plaatsBubbel, RONDLEIDING_VERSIE, STAPPEN, vraagtArtefact, zichtbareStappen, type Vak,
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
    // nodig – anders wijst de rondleiding naar een paneel dat nog dicht is.
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
      expect(el.anker, `${el.klasse} – "${el.tekst}"`).not.toBeNull();
      // Zelfde terugvindweg als het documentpaneel: staat de markering niet, dan zweeft hij.
      const pos = vindPositie(bron, el.tekst, el.anker, bezet);
      expect(pos, `${el.klasse} – "${el.tekst}"`).toBeGreaterThanOrEqual(0);
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
    // en bij een nieuwe gebruiker – precies wie de rondleiding krijgt – is die leeg.
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
    // ging het mis – "de kant met de meeste ruimte" leverde een bubbel onder de schermrand.
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

  it("houdt de eerder gekozen kant vast als die nog past", () => {
    // Een reviewkaart die krimpt of opschuift: beide kanten passen, dus de vaste volgorde zou naar
    // "onder" springen terwijl de bubbel al bovenaan stond. Middenin een handeling is dat een sprong
    // zonder aanleiding.
    const kaart: Vak = { top: 500, left: 400, breedte: 400, hoogte: 100 };
    expect(plaatsBubbel(kaart, BUBBEL, SCHERM).modus).toBe("onder");

    const met = plaatsBubbel(kaart, BUBBEL, SCHERM, "boven");
    expect(met.modus).toBe("boven");
    expect(binnenBeeld(met)).toBe(true);
  });

  it("houdt die kant ook vast als het element gaat domineren", () => {
    // Het palet kan de kaart over de 60%-grens duwen. Terugvallen op het scherm-midden leest als
    // een sprong; de gebruiker heeft de bubbel net nog naast het element zien staan.
    const groot: Vak = { top: 40, left: 40, breedte: 300, hoogte: 800 };
    expect(plaatsBubbel(groot, BUBBEL, SCHERM).modus).toBe("midden");
    expect(plaatsBubbel(groot, BUBBEL, SCHERM, "rechts").modus).toBe("rechts");
  });

  it("valt terug op de vaste volgorde als de vastgehouden kant niet meer past", () => {
    const onderin: Vak = { top: 800, left: 400, breedte: 600, hoogte: 60 };
    // "onder" past hier niet meer – dan telt de gewone volgorde weer.
    expect(plaatsBubbel(onderin, BUBBEL, SCHERM, "onder").modus).toBe("boven");
  });

  it("rekent op het zichtbare deel van een element dat uit zijn scroller hangt", () => {
    // Een reviewkaart die uitklapt tot ver onder de schermrand. `getBoundingClientRect` geeft het
    // ongeclipte vak, dus zonder bijsnijden zou de bubbel eronder gehangen worden – buiten beeld.
    const uitgeklapt: Vak = { top: 700, left: 900, breedte: 400, hoogte: 600 };
    const p = plaatsBubbel(uitgeklapt, BUBBEL, SCHERM);
    expect(binnenBeeld(p)).toBe(true);
  });

  it("houdt de bubbel binnen beeld bij een element dat naar boven is weggescrold", () => {
    const weg: Vak = { top: -300, left: 900, breedte: 400, hoogte: 120 };
    const p = plaatsBubbel(weg, BUBBEL, SCHERM);
    expect(binnenBeeld(p)).toBe(true);
  });

  it("centreert als er van het element niets meer in beeld staat", () => {
    // Helemaal onder de viewport weggescrold: er valt niets aan te wijzen.
    const buiten: Vak = { top: 1200, left: 900, breedte: 400, hoogte: 120 };
    expect(plaatsBubbel(buiten, BUBBEL, SCHERM)).toEqual({ modus: "midden" });
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
  // gecentreerde kaart: de rondleiding breekt niet, maar wijst ook niets meer aan – en dat merk je
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

describe("de dimlaag", () => {
  const viewport = { breedte: 1000, hoogte: 800 };

  /** Dekken de rechthoeken samen dit punt af? */
  function bedekt(vakken: Vak[], x: number, y: number): boolean {
    return vakken.some(
      (v) => x >= v.left && x < v.left + v.breedte && y >= v.top && y < v.top + v.hoogte,
    );
  }

  it("dekt het hele scherm af als er geen gat is", () => {
    // De normale stap: je hoort nergens te kunnen klikken behalve in de bubbel.
    const vakken = maskRechthoeken(null, viewport);
    expect(bedekt(vakken, 0, 0)).toBe(true);
    expect(bedekt(vakken, 500, 400)).toBe(true);
    expect(bedekt(vakken, 999, 799)).toBe(true);
  });

  it("laat het gat vrij en dekt de rest af", () => {
    // De interactieve stap: alleen de knop waar de rondleiding om vraagt mag door.
    const gat = { top: 300, left: 400, breedte: 120, hoogte: 40 };
    const vakken = maskRechthoeken(gat, viewport);

    expect(bedekt(vakken, 460, 320)).toBe(false); // midden in het gat
    expect(bedekt(vakken, 460, 299)).toBe(true); // net erboven
    expect(bedekt(vakken, 460, 341)).toBe(true); // net eronder
    expect(bedekt(vakken, 399, 320)).toBe(true); // net links
    expect(bedekt(vakken, 521, 320)).toBe(true); // net rechts
    expect(bedekt(vakken, 0, 0)).toBe(true);
    expect(bedekt(vakken, 999, 799)).toBe(true);
  });

  it("levert geen negatieve afmetingen bij een gat tegen de rand", () => {
    // Een element dat half buiten beeld valt (na scrollen) mag geen kapotte divs opleveren.
    for (const gat of [
      { top: -50, left: -20, breedte: 200, hoogte: 100 },
      { top: 780, left: 960, breedte: 200, hoogte: 100 },
    ]) {
      for (const v of maskRechthoeken(gat, viewport)) {
        expect(v.breedte).toBeGreaterThan(0);
        expect(v.hoogte).toBeGreaterThan(0);
      }
    }
  });

  it("snijdt een element bij op wat ervan in beeld staat", () => {
    // De uitsnede voor de dimlaag hangt hieraan: een kaart die half uit haar scroller hangt hoort
    // geen gat op te leveren dat tot ver buiten het scherm doorloopt.
    expect(zichtbaarDeel({ top: -40, left: 100, breedte: 200, hoogte: 140 }, viewport)).toEqual({
      top: 0, left: 100, breedte: 200, hoogte: 100,
    });
    expect(zichtbaarDeel({ top: 700, left: 100, breedte: 200, hoogte: 400 }, viewport)).toEqual({
      top: 700, left: 100, breedte: 200, hoogte: 100,
    });
    // Volledig weggescrold: er is niets aan te wijzen.
    expect(zichtbaarDeel({ top: 900, left: 100, breedte: 200, hoogte: 50 }, viewport)).toBeNull();
  });

  it("legt de uitsnede rond het element, met marge", () => {
    expect(uitsnede({ top: 100, left: 200, breedte: 50, hoogte: 20 }, 10)).toEqual({
      top: 90, left: 190, breedte: 70, hoogte: 40,
    });
  });

  it("laat lege randen weg", () => {
    // Een gat over de volle breedte heeft geen linker- en rechterrand nodig.
    const vakken = maskRechthoeken({ top: 300, left: 0, breedte: 1000, hoogte: 40 }, viewport);
    expect(vakken).toHaveLength(2);
  });
});

describe("het artefactpaneel volgt de stap", () => {
  const metPaneel = STAPPEN.find((s) => s.artefactOpen)!;
  const zonderPaneel = STAPPEN.find((s) => !s.artefactOpen)!;

  it("opent het paneel voor een stap die het nodig heeft", () => {
    expect(artefactActie(false, metPaneel)).toBe("openen");
  });

  it("sluit het paneel bij teruglopen naar een stap zonder paneel", () => {
    // De bug: alleen openen was geregeld. Wie terugliep hield het artefact voor de thread staan,
    // en de bubbel wees naar iets wat niet te zien was.
    expect(artefactActie(true, zonderPaneel)).toBe("sluiten");
  });

  it("laat het paneel met rust als het al goed staat", () => {
    expect(artefactActie(true, metPaneel)).toBeNull();
    expect(artefactActie(false, zonderPaneel)).toBeNull();
  });

  it("sluit het paneel als er geen stap meer is", () => {
    // Voorbij de laatste stap: dan hoort de werkplek weer schoon te zijn.
    expect(artefactActie(true, undefined)).toBe("sluiten");
    expect(artefactActie(false, undefined)).toBeNull();
  });

  it("regelt de overgang rond de openen-stap in beide richtingen", () => {
    // Stap 7 gaat over het openen zelf en heeft het paneel dus nog niet nodig; de stap erna wel.
    const i = STAPPEN.findIndex((s) => s.id === "artefact-openen");
    expect(artefactActie(true, STAPPEN[i])).toBe("sluiten"); // terug vanaf de wettekst
    expect(artefactActie(false, STAPPEN[i + 1])).toBe("openen"); // vooruit naar de wettekst
  });
});

describe("het gat in de dimlaag", () => {
  const vak: Vak = { top: 400, left: 700, breedte: 90, hoogte: 32 };
  const interactief = STAPPEN.find((s) => s.interactie)!;
  const gewoon = STAPPEN.find((s) => !s.interactie)!;

  it("laat een gat vallen in de stap die om een handeling vraagt", () => {
    const gat = klikGat(interactief, vak, 14);
    expect(gat).toEqual({ top: 386, left: 686, breedte: 118, hoogte: 60 });
  });

  it("laat geen gat vallen in een gewone stap", () => {
    // Daar is elke klik buiten de bubbel er een die de rondleiding kan slopen.
    expect(klikGat(gewoon, vak, 14)).toBeNull();
  });

  it("laat geen gat vallen zonder gemeten element", () => {
    expect(klikGat(interactief, null, 14)).toBeNull();
  });

  it("hangt niet af van waar de bubbel terechtkomt", () => {
    // De bug die dit veroorzaakte: het gat hing aan het vak dat óók de spotlight stuurt, en dat is
    // null zodra de bubbel gecentreerd staat. Dan verdween het gat terwijl het element er gewoon
    // was, en kon je de knop niet meer indrukken.
    const bubbelStaatGecentreerd = plaatsBubbel(
      { top: 0, left: 0, breedte: 1000, hoogte: 700 },
      { breedte: 340, hoogte: 220 },
      { breedte: 1000, hoogte: 800 },
    );
    expect(bubbelStaatGecentreerd.modus).toBe("midden");
    // En tóch is de knop bereikbaar:
    expect(klikGat(interactief, vak, 14)).not.toBeNull();
  });
});

describe("de dimlaag laat het gat echt door", () => {
  // De valkuil die dit koste: de rechthoeken kloppen (zie hierboven), maar ze zitten in een
  // schermvullende container. Staat die niet op `pointer-events-none`, dan is het gat een illusie —
  // een klik "in het gat" landt op de container en bereikt de knop eronder nooit. Dat is precies
  // wat er misging, en het is niet zichtbaar in een test op de rechthoeken zelf.
  const bubbel = readFileSync(
    new URL("../components/rondleiding/TourBubbel.tsx", import.meta.url).pathname,
    "utf-8",
  );

  it("laat de container van de dimlaag niets vangen", () => {
    expect(bubbel).toMatch(/pointer-events-none[^"]*fixed inset-0 z-\[60\]/);
  });

  it("laat de losse dimvlakken wél vangen", () => {
    expect(bubbel).toContain("pointer-events-auto absolute bg-ink/55");
  });

  it("houdt de rand om het element doorlaatbaar", () => {
    // Die ligt over het gat heen; zou hij vangen, dan was de knop alsnog onbereikbaar.
    expect(bubbel).toMatch(/pointer-events-none absolute rounded-kaart/);
  });

  it("animeert de dimvlakken niet", () => {
    // Een vlak dat 150 ms lang naar zijn nieuwe plek beweegt, dekt in die tijd nog de oude af.
    expect(bubbel).not.toMatch(/pointer-events-auto absolute bg-ink\/55 transition/);
  });
});
