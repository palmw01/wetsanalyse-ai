import { readFileSync } from "node:fs";
import { globSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  artefactActie, BUBBEL_MARGE, domineert, heeftOmvang, hervatIndex, indexVan, klikGat, LEGE_STAND,
  maskRechthoeken, moetStarten, toetsActie, uitsnede, zichtbaarDeel, type ToetsContext,
  plaatsBubbel, RONDLEIDING_VERSIE, STAPPEN, vraagtArtefact, zichtbareStappen, type Vak,
} from "./rondleiding";
import {
  DEMO_DOEL, DEMO_LEDEN, DEMO_SAMENVATTING, DEMO_SLUG, maakDemoOpslag, maakDemoScene, maakDemoWeergave,
  pasDemoBeslissingToe, voegDemoElementToe, wisDemoElement, zetDemoStatus,
} from "./rondleidingDemo";
import { vindPositie } from "./selectie";
import { BESLIST_LIFECYCLES } from "./annotatie";
import { documentVanNode, nodeBronVan, nogOngedekt, ongedektVanNode } from "./annotatieNodeAdapter";
import { segmentAnker } from "./annotatieNode";

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
  /** De weergave zoals het paneel hem ziet: door dezelfde adapter als echt werk. */
  const alsPaneel = () => {
    const view = maakDemoWeergave();
    const nb = nodeBronVan(view);
    return { view, nb, doc: documentVanNode(view, nb) };
  };

  it("draagt de letterlijke wettekst per lid", () => {
    const { view } = alsPaneel();
    expect(view.segmenten.map((s) => s.tekst)).toEqual(DEMO_LEDEN.map((l) => l.tekst));
  });

  it("markeert uitsluitend fragmenten die letterlijk in de wettekst staan", () => {
    const { view, nb, doc } = alsPaneel();
    // Elk anker raakt in zijn eigen lid precies de tekst van het element, in codepoints.
    for (const el of view.elementen) {
      expect(el.ankers, `${el.klasse} – "${el.tekst}"`).toHaveLength(1);
      const [a] = el.ankers;
      const segment = view.segmenten.find((s) => s.bron_iri === a.bron_iri)!;
      expect(Array.from(segment.tekst).slice(a.start, a.eind).join("")).toBe(el.tekst);
    }
    // En via de adapter staat elke markering in het paneel op haar plek: geen zwevende.
    const bezet: { start: number; eind: number }[] = [];
    for (const el of doc.elementen) {
      expect(el.anker, `${el.klasse} – "${el.tekst}"`).not.toBeNull();
      const pos = vindPositie(nb.bron, el.tekst, el.anker, bezet);
      expect(pos, `${el.klasse} – "${el.tekst}"`).toBeGreaterThanOrEqual(0);
      bezet.push({ start: pos, eind: pos + el.tekst.length });
    }
  });

  it("laat de markeringen niet overlappen", () => {
    const bereiken = alsPaneel().doc.elementen.map((el) => el.anker!).sort((a, b) => a.start - b.start);
    for (let i = 1; i < bereiken.length; i++) {
      expect(bereiken[i].start).toBeGreaterThanOrEqual(bereiken[i - 1].eind);
    }
  });

  it("begint met alles nog te beoordelen", () => {
    const { doc } = alsPaneel();
    expect(doc.elementen.length).toBeGreaterThan(5);
    expect(doc.elementen.every((el) => !BESLIST_LIFECYCLES.includes(el.lifecycle))).toBe(true);
    expect(doc.status).toBe("in_review");
  });

  it("toont de aandacht zoals de keten haar zet: geen badge, geel en groen, nooit rood", () => {
    const niveaus = new Set(maakDemoWeergave().elementen.map((el) => el.aandacht));
    expect(niveaus).toEqual(new Set([null, "geel", "groen"]));
  });

  it("vat de voorstellen samen zoals graph-qa dat doet", () => {
    // Dezelfde tellingen als `agent/nodes/annotatie_samenvatting.py`, uit de demo zelf.
    const els = maakDemoWeergave().elementen;
    const door = (e: (typeof els)[number]) => e.trace?.beslissing?.door;
    const keuze = els.filter((e) => e.aandacht === "geel" || door(e) === "terugval").length;
    const vast = els.filter((e) => door(e) === "regel").length;
    const model = els.filter((e) => door(e) === "model").length;
    const getal = ["", "één", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien", "elf"];
    expect(DEMO_SAMENVATTING).toContain(`${getal[els.length]} JAS-elementen gevonden`);
    expect(DEMO_SAMENVATTING.toLowerCase()).toContain(`${getal[keuze]} voorstellen hebben een plausibel alternatief`);
    expect(DEMO_SAMENVATTING.toLowerCase()).toContain(`${getal[vast]} voorstellen volgen rechtstreeks uit vaste regels, ${getal[model]} koos het model`);
    const telling = new Map<string, number>();
    for (const e of els) telling.set(e.klasse, (telling.get(e.klasse) ?? 0) + 1);
    const top = [...telling.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map(([k]) => k);
    expect(DEMO_SAMENVATTING).toContain(`vooral ${top.join(" en ")}`);
  });

  it("geeft het paneel een ongedekt zinsdeel dat letterlijk in de tekst staat", () => {
    const { view, nb, doc } = alsPaneel();
    const delen = nogOngedekt(ongedektVanNode(view, nb), doc.elementen, nb.bron);
    expect(delen.map((d) => d.tekst)).toEqual(["invorderbaar"]);
    expect(delen[0].lid).toBe("2");
  });

  it("biedt bij een termijn een andere grens aan", () => {
    const { doc } = alsPaneel();
    const termijn = doc.elementen.find((e) => e.tekst.startsWith("zes weken"))!;
    expect(termijn.grensopties?.map((o) => o.tekst)).toEqual(["zes weken"]);
  });

  it("draagt in elk spoor alleen codes die de keten kent", () => {
    const yaml = readFileSync(
      new URL("../../tools/graph-qa/agent/jas_pipeline/verklaringen.yaml", import.meta.url).pathname,
      "utf-8",
    );
    for (const el of maakDemoWeergave().elementen) {
      const t = el.trace!;
      const codes = [
        ...(t.kandidaat?.bewijs ?? []).map((b) => b.code),
        ...(t.twijfel ?? []).map((x) => x.reden),
        ...(t.resolutie ?? []).map((r) => r.regel),
        t.beslissing?.door ?? "",
      ];
      for (const code of codes) expect(yaml, `${el.tekst}: ${code}`).toMatch(new RegExp(`^  ${code}:`, "m"));
    }
  });

  it("levert een thread met een annotatie die het paneel op de voorbeeldweergave opent", () => {
    const scene = maakDemoScene();
    const chip = scene.items.find((i) => i.type === "annotatie");
    expect(chip).toBeDefined();
    expect(chip!.type === "annotatie" && chip!.slug).toBe(DEMO_SLUG);
    // Met een bronnode: dan opent het echte paneel (`NodeAnnotatiePaneel`), niet het oude slug-pad.
    expect(chip!.type === "annotatie" && chip!.annotatie_doel).toEqual(DEMO_DOEL);
    expect(scene.opslag.levend).toBe(false);
  });

  it("draagt overal het voorbeeld-label", () => {
    const scene = maakDemoScene();
    expect(alsPaneel().doc.citeertitel).toContain("VOORBEELD");
    expect(DEMO_DOEL.label).toContain("VOORBEELD");
    const chip = scene.items.find((i) => i.type === "annotatie");
    expect(chip!.type === "annotatie" && chip!.titel).toContain("VOORBEELD");
    // Ook de sidebar-lijst: die staat naast de echte gesprekken van de gebruiker.
    for (const g of scene.gesprekken) expect(g.titel).toContain("VOORBEELD");
  });

  it("wijst een eigen iri aan, nooit een uit de graaf", () => {
    const view = maakDemoWeergave();
    for (const iri of [view.doel.bron_iri, ...view.segmenten.map((s) => s.bron_iri)]) {
      expect(iri.startsWith("demo:")).toBe(true);
    }
  });

  it("levert een gevulde gesprekkenlijst voor de sidebar", () => {
    // De stap "Je werk terugvinden" wijst de sidebar aan. Die haalt zijn lijst normaal bij de api,
    // en bij een nieuwe gebruiker – precies wie de rondleiding krijgt – is die leeg.
    const scene = maakDemoScene();
    expect(scene.gesprekken.length).toBeGreaterThan(0);
    expect(new Set(scene.gesprekken.map((g) => g.id)).size).toBe(scene.gesprekken.length);
  });

  it("bouwt elke keer een schone lei", () => {
    const eerste = maakDemoWeergave();
    const beslist = pasDemoBeslissingToe(eerste, eerste.elementen[0].id, { type: "approve" });
    expect(beslist.elementen[0].lifecycle).toBe("human_approved");
    // Het origineel blijft ongemoeid, en een volgende start begint weer bij nul.
    expect(eerste.elementen[0].lifecycle).toBe("voorgesteld");
    expect(maakDemoWeergave().elementen[0].lifecycle).toBe("voorgesteld");
  });
});

describe("de demo-mutaties", () => {
  it("verwerpt een voorstel zonder het te wissen", () => {
    const view = maakDemoWeergave();
    const na = pasDemoBeslissingToe(view, view.elementen[1].id, { type: "reject", review_reason: "verkeerde_klasse" });
    expect(na.elementen).toHaveLength(view.elementen.length);
    expect(na.elementen[1].lifecycle).toBe("rejected");
    expect(na.elementen[1].beslissingen?.at(-1)?.type).toBe("reject");
  });

  it("neemt een klassewijziging over en verhoogt de revisie van de laag", () => {
    const view = maakDemoWeergave();
    const el = view.elementen[0];
    const na = pasDemoBeslissingToe(view, el.id, { type: "edit", wijziging: { klasse: "Rechtssubject" } });
    expect(na.elementen[0].klasse).toBe("Rechtssubject");
    expect(na.elementen[0].lifecycle).toBe("edited");
    expect(na.elementen[0].gewijzigd_door).toBe("mens");
    const revisie = (v: typeof view) => v.lagen.find((l) => l.bron_iri === el.eigenaar_iri)!.revisie;
    expect(revisie(na)).toBe(revisie(view) + 1);
  });

  it("zet een eigen markering er meteen goedgekeurd bij en wist hem weer", () => {
    const view = maakDemoWeergave();
    const lid1 = view.segmenten[0];
    const start = lid1.tekst.indexOf("het aanslagbiljet");
    const anker = segmentAnker(lid1, start, start + "het aanslagbiljet".length);
    const { view: bij, id } = voegDemoElementToe(view, {
      klasse: "Rechtsobject", toelichting: "", tekst: anker.tekst, ankers: [anker],
    });
    expect(bij.elementen).toHaveLength(view.elementen.length + 1);
    expect(bij.elementen.at(-1)!.lifecycle).toBe("human_approved");
    expect(bij.elementen.at(-1)!.herkomst).toBe("mens");
    expect(bij.elementen.at(-1)!.eigenaar_iri).toBe(lid1.bron_iri);
    expect(wisDemoElement(bij, id).elementen).toHaveLength(view.elementen.length);
  });

  it("rondt een laag af en heropent hem", () => {
    const view = maakDemoWeergave();
    const laag = view.lagen[0].id;
    expect(zetDemoStatus(view, laag, "geaccordeerd").lagen[0].status).toBe("geaccordeerd");
    expect(zetDemoStatus(zetDemoStatus(view, laag, "geaccordeerd"), laag, "in_review").lagen[0].status).toBe("in_review");
  });

  it("houdt de stand vast in de opslag en geeft kopieën", async () => {
    const opslag = maakDemoOpslag();
    const voor = await opslag.weergave(DEMO_DOEL);
    await opslag.beslis(voor.elementen[0].id, { type: "approve" });
    const na = await opslag.weergave(DEMO_DOEL);
    expect(na.elementen[0].lifecycle).toBe("human_approved");
    // Wat het paneel kreeg, verandert niet onder zijn handen.
    expect(voor.elementen[0].lifecycle).toBe("voorgesteld");
  });

  it("toont na verwijderen een verwijderde annotatie", async () => {
    const opslag = maakDemoOpslag();
    await opslag.verwijder({});
    const na = await opslag.weergave(DEMO_DOEL);
    expect(na.elementen).toEqual([]);
    expect(na.lagen).toEqual([]);
    expect(na.verwijderd?.op).toBeTruthy();
  });
});

describe("waar de bubbel komt te staan", () => {
  const SCHERM = { breedte: 1440, hoogte: 900 };
  const TELEFOON = { breedte: 390, hoogte: 844 };
  const BUBBEL = { breedte: 340, hoogte: 220 };

  /** Ligt de bubbel volledig binnen het scherm? Dat is de eis die hier bewaakt wordt. */
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

  it("herkent een element zonder omvang", () => {
    // Een `display: none`-element (de zijbalk onder `lg`, de hamburger erboven) meet 0×0. Daar hoort
    // de rondleiding niets aan te hangen: dan wijst hij een punt in de hoek van het scherm aan.
    expect(heeftOmvang(null)).toBe(false);
    expect(heeftOmvang({ top: 0, left: 0, breedte: 0, hoogte: 0 })).toBe(false);
    expect(heeftOmvang({ top: 0, left: 0, breedte: 272, hoogte: 0 })).toBe(false);
    expect(heeftOmvang({ top: 10, left: 10, breedte: 40, hoogte: 24 })).toBe(true);
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

describe("de openen-stap", () => {
  const openen = STAPPEN.find((s) => s.id === "artefact-openen")!;

  it("laat de kaart zelf aanklikken", () => {
    // Zonder interactie lag er een klikvanger over de kaart, terwijl de tekst om een klik vroeg; een
    // timer opende het paneel daarna vanzelf. Dat was de rondleiding die "zelf doorliep".
    expect(openen.interactie).toBe("openen");
    expect(klikGat(openen, { top: 400, left: 300, breedte: 500, hoogte: 60 }, 14)).not.toBeNull();
  });

  it("opent het paneel zelf nog niet", () => {
    expect(openen.artefactOpen).toBeUndefined();
  });

  it("heeft geen timer meer in de motor", () => {
    const motor = readFileSync(
      new URL("../components/rondleiding/Rondleiding.tsx", import.meta.url).pathname,
      "utf-8",
    );
    expect(motor).not.toMatch(/setTimeout\(onOpenArtefact/);
  });
});

describe("welke toets de rondleiding stuurt", () => {
  const basis: ToetsContext = {
    key: "Enter", inBubbel: false, nergens: true, opBediening: false, interactief: false,
    alAfgevangen: false,
  };
  const t = (extra: Partial<ToetsContext>) => toetsActie({ ...basis, ...extra });

  it("gaat verder met Enter op de kop van de bubbel of zonder focus", () => {
    expect(t({ inBubbel: true, nergens: false })).toBe("volgende");
    expect(t({})).toBe("volgende");
  });

  it("laat Enter op een knop aan die knop", () => {
    // Enter op *Vorige* ging een stap vooruit, en Enter op *Overslaan* sloeg niets over.
    expect(t({ inBubbel: true, nergens: false, opBediening: true })).toBeNull();
  });

  it("bladert met de pijltjes, ook als een knop in de bubbel de focus heeft", () => {
    expect(t({ key: "ArrowRight", inBubbel: true, nergens: false, opBediening: true })).toBe("volgende");
    expect(t({ key: "ArrowLeft", inBubbel: true, nergens: false, opBediening: true })).toBe("vorige");
  });

  it("blijft in een interactieve stap van de werkplek af", () => {
    // In "Jij beslist" keurde Enter op *Akkoord* niets goed: de rondleiding sprong door.
    const inWerkplek = { nergens: false, interactief: true, opBediening: true };
    expect(t({ ...inWerkplek })).toBeNull();
    expect(t({ ...inWerkplek, key: "ArrowRight" })).toBeNull();
    expect(t({ ...inWerkplek, key: "Escape" })).toBeNull();
    // Zonder focus ook niet: daar typ je net j, k of a.
    expect(t({ interactief: true, key: "ArrowRight" })).toBeNull();
  });

  it("sluit met Escape vanuit de bubbel, maar niet als iemand anders hem al afving", () => {
    expect(t({ key: "Escape", inBubbel: true, nergens: false })).toBe("sluiten");
    // Het klassepalet en een scherpe BevestigKnop vangen Escape in de capture-fase.
    expect(t({ key: "Escape", inBubbel: true, nergens: false, alAfgevangen: true })).toBeNull();
  });

  it("negeert andere toetsen", () => {
    expect(t({ key: "a", inBubbel: true, nergens: false })).toBeNull();
  });
});
