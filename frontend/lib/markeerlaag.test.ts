import { describe, expect, it } from "vitest";

import { banenInBlok, laagVan, markeringVan, segmentenVanBlok, type Markeerbaar } from "./markeerlaag";
import { blokkenVan } from "@/lib/wetstructuur";
import { maakAnker } from "@/lib/selectie";

const BRON = "De ontvanger kan uitstel van betaling verlenen aan de belastingschuldige.";
const HERHAALD = "De ontvanger verleent uitstel. De ontvanger kan dat weigeren.";

/** Alle segmenten samen zijn altijd de hele brontekst – anders raakt er wettekst zoek in beeld. */
function heelGebleven(bron: string, segs: { tekst: string }[]) {
  expect(segs.map((s) => s.tekst).join("")).toBe(bron);
}

/** De hele bron als één blok, zoals een bepaling zonder leden. */
const heel = (bron: string) => ({ offset: 0, regel: bron, nummerEind: 0, termStart: -1, termEind: -1 });
const segmenteer = (bron: string, elementen: Markeerbaar[]) => segmentenVanBlok(heel(bron), laagVan(bron, elementen));

describe("laagVan – alle markeringen in banen (optie B)", () => {
  const ELEMENTEN = [
    { id: "lang", klasse: "Afleidingsregel", tekst: BRON },
    { id: "kort", klasse: "Rechtsobject", tekst: "uitstel van betaling" },
  ];

  it("de korte valt niet weg in de lange: zij houdt het vlak, de lange ligt als baan eronder", () => {
    // Dit was het probleem: overlappende markeringen konden niet naast elkaar bestaan, dus de lange slokte de korte op.
    const segs = segmenteer(BRON, ELEMENTEN);
    expect(segs.filter((s) => s.klasse).map((s) => [s.id, s.tekst])).toEqual([["kort", "uitstel van betaling"]]);
    expect(segs.every((s) => s.banen?.map((b) => b.id).join() === "lang")).toBe(true);
    expect(banenInBlok(segs)).toBe(1);
    heelGebleven(BRON, segs);
  });

  it("zonder markeringen blijft de tekst schoon", () => {
    expect(segmenteer(BRON, [])).toEqual([{ tekst: BRON }]);
  });

  it("een markering die de hele bron beslaat en niets omvat, is één vlak", () => {
    const segs = segmenteer(BRON, [ELEMENTEN[0]]);
    expect(segs).toHaveLength(1);
    expect(segs[0].klasse).toBe("Afleidingsregel");
    expect(segs[0].banen).toBeUndefined();
  });

  it("markeert een fragment niet als het niet letterlijk in de tekst staat", () => {
    const segs = segmenteer(BRON, [{ id: "a", klasse: "Rechtssubject", tekst: "komt niet voor" }]);
    expect(segs.some((s) => s.klasse || s.banen)).toBe(false);
    heelGebleven(BRON, segs);
  });

  it("draagt de herkomst mee, zodat de tekst een eigen markering anders kan tonen", () => {
    const segs = segmenteer(BRON, [
      { id: "lang", klasse: "Afleidingsregel", tekst: BRON, herkomst: "mens" },
      { id: "m", klasse: "Rechtsobject", tekst: "uitstel van betaling", herkomst: "mens" },
    ]);
    expect(segs.find((s) => s.klasse)?.herkomst).toBe("mens");
    expect(segs[0].banen?.[0].herkomst).toBe("mens");
  });

  it("de volgorde van de elementen maakt niets uit", () => {
    expect(segmenteer(BRON, [...ELEMENTEN].reverse())).toEqual(segmenteer(BRON, ELEMENTEN));
  });
});

// --- ankers: welk voorkomen van een herhaald fragment wordt gemarkeerd? -------------------------

describe("markeringVan – ankers", () => {
  it("gebruikt het anker om het juiste voorkomen te kiezen", () => {
    // Zonder anker zou "De ontvanger" altijd op positie 0 landen; het anker wijst de tweede aan.
    const tweede = HERHAALD.indexOf("De ontvanger", 1);
    const m = markeringVan(HERHAALD, [
      { id: "b", klasse: "Rechtssubject", tekst: "De ontvanger", anker: maakAnker(HERHAALD, tweede, tweede + 12) },
    ], "b");
    expect(m?.start).toBe(tweede);
  });

  it("valt terug op de omringende tekst als de bron is geschoven", () => {
    // Het anker komt van een oudere versie van de tekst: de hash klopt niet meer en de offsets
    // wijzen naar de verkeerde plek. De context moet het dan alsnog goed krijgen.
    const oud = "Inleiding. " + HERHAALD;
    // let op: lastIndexOf – met indexOf(…, 1) pak je in `oud` nog steeds het EERSTE voorkomen,
    // want "Inleiding. " schuift alles 11 tekens op.
    const tweedeOud = oud.lastIndexOf("De ontvanger");
    const verouderd = maakAnker(oud, tweedeOud, tweedeOud + 12);
    const m = markeringVan(HERHAALD, [{ id: "b", klasse: "Rechtssubject", tekst: "De ontvanger", anker: verouderd }], "b");
    expect(m?.start).toBe(HERHAALD.indexOf("De ontvanger", 1));
  });

  it("pakt zonder anker het eerste voorkomen, en niets als het id niet (meer) bestaat", () => {
    const els = [{ id: "a", klasse: "Rechtssubject", tekst: "De ontvanger" }];
    expect(markeringVan(HERHAALD, els, "a")?.start).toBe(0);
    expect(markeringVan(HERHAALD, els, "weg")).toBeNull();
  });

  it("de laag plaatst twee gelijke fragmenten met hun eigen anker", () => {
    const tweede = HERHAALD.indexOf("De ontvanger", 1);
    const laag = laagVan(HERHAALD, [
      { id: "a", klasse: "Rechtssubject", tekst: "De ontvanger", anker: maakAnker(HERHAALD, 0, 12) },
      { id: "b", klasse: "Rechtssubject", tekst: "De ontvanger", anker: maakAnker(HERHAALD, tweede, tweede + 12) },
    ]);
    expect([laag.plekken.get("a")?.start, laag.plekken.get("b")?.start]).toEqual([0, tweede]);
  });
});

describe("segmentenVanBlok – één bron van tekst", () => {
  // De echte tekst uit art. 2 lid 1 IW 1990, zoals `regelsVan` hem opbouwt.
  const REGELS = [{
    lid: "1",
    regel: "1. Deze wet verstaat onder:\n" +
      "a. rijksbelastingen: belastingen als bedoeld in artikel 1 van de Algemene wet;\n" +
      "1°. Koninkrijk: Koninkrijk der Nederlanden;\n" +
      "b. de ontvanger: de functionaris;",
  }];
  const BRON_B = REGELS[0].regel;
  const blokken = blokkenVan(REGELS);

  function markering(fragment: string, klasse = "Voorwaarde", id = "m") {
    return laagVan(BRON_B, [{ id, klasse, tekst: fragment }]);
  }

  it("levert samen exact de regel, met en zonder markering", () => {
    // Rendert de weergave nummer en term apart én daarna nog eens de hele regel via deze functie,
    // dan staat de tekst dubbel in de DOM en telt `offsetVanGrens` te veel op — elke zelfgemaakte
    // markering landt dan op de verkeerde plek. `blokkenVan` en `segmentenVanBlok` waren elk apart getest; alleen hun combinatie brak.
    for (const b of blokken) {
      expect(segmentenVanBlok(b, null).map((s) => s.tekst).join("")).toBe(b.regel);
      expect(segmentenVanBlok(b, markering("Koninkrijk der Nederlanden")).map((s) => s.tekst).join(""))
        .toBe(b.regel);
      expect(segmentenVanBlok(b, markering("verstaat onder:\na. rijksbelastingen")).map((s) => s.tekst).join(""))
        .toBe(b.regel);
    }
  });

  it("knipt ook op ongedekte zinsdelen, zonder tekst te verliezen, en laat de markering voorgaan", () => {
    const deel = (fragment: string) => { const s = BRON_B.indexOf(fragment); return { start: s, eind: s + fragment.length }; };
    const ongedekt = [deel("belastingen als bedoeld"), deel("de functionaris")];
    for (const b of blokken) {
      expect(segmentenVanBlok(b, null, ongedekt).map((s) => s.tekst).join("")).toBe(b.regel);
      expect(segmentenVanBlok(b, markering("bedoeld in artikel 1"), ongedekt).map((s) => s.tekst).join("")).toBe(b.regel);
    }
    const a = segmentenVanBlok(blokken[1], null, ongedekt);
    expect(a.filter((s) => s.ongedekt).map((s) => s.tekst).join("")).toBe("belastingen als bedoeld");
    // Waar de markering ligt, wint die: "bedoeld" valt in beide en is dan alleen gemarkeerd.
    const metMark = segmentenVanBlok(blokken[1], markering("bedoeld in artikel 1"), ongedekt);
    expect(metMark.filter((s) => s.ongedekt).map((s) => s.tekst).join("")).toBe("belastingen als ");
    expect(metMark.some((s) => s.klasse && s.ongedekt)).toBe(false);
  });

  it("geeft het onderdeelnummer en de definitieterm hun eigen nadruk", () => {
    const segs = segmentenVanBlok(blokken[1], null);
    expect(segs.find((s) => s.nadruk === "nummer")?.tekst).toBe("a.");
    expect(segs.find((s) => s.nadruk === "term")?.tekst).toBe("rijksbelastingen");
    // De rest draagt geen nadruk – anders wordt de hele bepaling vet.
    expect(segs.filter((s) => s.nadruk).length).toBe(2);
  });

  it("laat de lidkop zijn nummer houden", () => {
    const segs = segmentenVanBlok(blokken[0], null);
    expect(segs.find((s) => s.nadruk === "nummer")?.tekst).toBe("1.");
  });

  it("kan nadruk en markering tegelijk dragen", () => {
    // De jurist markeert de definitieterm zelf: dan is het segment én term én markering.
    const segs = segmentenVanBlok(blokken[1], markering("rijksbelastingen", "Brondefinitie", "x"));
    const term = segs.find((s) => s.nadruk === "term");
    expect(term?.klasse).toBe("Brondefinitie");
    expect(term?.id).toBe("x");
    expect(segs.map((s) => s.tekst).join("")).toBe(blokken[1].regel);
  });

  it("zwijgt over nadruk in een blok zonder nummer of term", () => {
    const los = blokkenVan([{ lid: "", regel: "Een belastingaanslag is invorderbaar." }]);
    expect(segmentenVanBlok(los[0], null)).toEqual([{ tekst: "Een belastingaanslag is invorderbaar." }]);
  });
});

describe("segmentenVanBlok – een markering knippen op de blokgrens", () => {
  // De blokken zoals `blokkenVan` ze levert voor één lid met twee onderdelen.
  const REGELS = [{ lid: "1", regel: "1. De aanhef luidt:\na. het eerste onderdeel;\nb. het tweede;" }];
  const BRON_B = REGELS[0].regel;
  const blokken = blokkenVan(REGELS);

  function markering(fragment: string, klasse = "Voorwaarde", id = "m") {
    return laagVan(BRON_B, [{ id, klasse, tekst: fragment }]);
  }

  it("laat een blok zonder markering ongemarkeerd", () => {
    // De tekst blijft heel; hij wordt wél op de nummergrens geknipt, want dat nummer draagt opmaak.
    const segs = segmentenVanBlok(blokken[0], null);
    expect(segs.map((s) => s.tekst).join("")).toBe("1. De aanhef luidt:");
    expect(segs.some((s) => s.klasse)).toBe(false);
  });

  it("markeert binnen één blok en houdt de rest van dat blok heel", () => {
    const segs = segmentenVanBlok(blokken[1], markering("eerste onderdeel"));
    expect(segs.map((s) => s.tekst).join("")).toBe(blokken[1].regel);
    expect(segs.filter((s) => s.klasse)).toHaveLength(1);
    expect(segs.find((s) => s.klasse)?.tekst).toBe("eerste onderdeel");
  });

  it("knipt een markering die twee blokken overspant in twee stukken", () => {
    // Een <mark> kan niet over twee blokken heen – die zijn aparte DOM-elementen. Zonder knippen
    // zou de markering in het tweede blok verdwijnen.
    const m = markering("luidt:\na. het eerste");
    const eerste = segmentenVanBlok(blokken[0], m).filter((s) => s.klasse);
    const tweede = segmentenVanBlok(blokken[1], m).filter((s) => s.klasse);
    // Elk blok draagt zijn deel van de markering. Binnen een blok kan dat nog verder opgeknipt zijn
    // omdat het nummer eigen opmaak heeft – de samengevoegde tekst is wat telt.
    expect(eerste.map((s) => s.tekst).join("")).toBe("luidt:");
    expect(tweede.map((s) => s.tekst).join("")).toBe("a. het eerste");
    // Alle stukken dragen dezelfde klasse en hetzelfde id – anders reageren ze los op een klik.
    expect([...eerste, ...tweede].every((s) => s.id === "m" && s.klasse === "Voorwaarde")).toBe(true);
  });

  it("raakt een blok dat buiten de markering valt niet aan", () => {
    const m = markering("eerste onderdeel");
    expect(segmentenVanBlok(blokken[2], m).some((s) => s.klasse)).toBe(false);
    expect(segmentenVanBlok(blokken[0], m).some((s) => s.klasse)).toBe(false);
  });

  it("houdt elk blok in zijn geheel, ongeacht de markering", () => {
    // Zelfde eis als `heelGebleven` hierboven, nu per blok: er mag geen wettekst zoekraken.
    const m = markering("aanhef luidt:\na. het");
    for (const b of blokken) {
      expect(segmentenVanBlok(b, m).map((s) => s.tekst).join("")).toBe(b.regel);
    }
  });
});


/** De weergave op ECHTE wettekst: art. 2 lid 1 IW 1990, zoals hij uit de graaf komt.
 *
 *  De tests hierboven dekken `blokkenVan` en `segmentenVanBlok` apart. Deze dekt wat de browser
 *  feitelijk doet: alle tekstknopen binnen één blok optellen (`offsetVanGrens`). Precies die
 *  combinatie kan breken — rendert de weergave nummer en term apart én daarna nog eens de hele
 *  regel, dan staat de tekst dubbel in de DOM en landt elke zelfgemaakte markering op de verkeerde
 *  plek. Geen van de losse tests ziet dat.
 */
// De echte tekst uit de export van de gebruiker (art. 2 lid 1 IW 1990), afgekapt.
const TEKST = "Deze wet verstaat onder:\na. rijksbelastingen: belastingen als bedoeld in artikel 1 van de Algemene wet inzake rijksbelastingen, alsmede rechten bij invoer en rechten bij uitvoer als bedoeld in artikel 7:3 van de Algemene douanewet, die in Nederland worden geheven;\n1°. Koninkrijk: Koninkrijk der Nederlanden;\n2°. Rijk: het land Nederland, zijnde Nederland en de BES eilanden;\nb. belastingrente en revisierente: de belastingrente en de revisierente, bedoeld in hoofdstuk VA van de Algemene wet inzake rijksbelastingen;";

describe("de gerenderde DOM op de echte wettekst", () => {
  const regels = [{ lid: "1", regel: `1. ${TEKST}` }];
  const bron = regels.map((r) => r.regel).join("\n\n");
  const blokken = blokkenVan(regels);

  it("reconstrueert per blok exact de brontekst uit de tekstknopen", () => {
    // Dit is wat `offsetVanGrens` in de browser doet: alle tekstknopen binnen één blok optellen.
    for (const b of blokken) {
      const knopen = segmentenVanBlok(b, null).map((s) => s.tekst);
      expect(knopen.join("")).toBe(bron.slice(b.offset, b.offset + b.regel.length));
    }
  });

  it("plaatst het echte anker van 'Koninkrijk: Koninkrijk der Nederlanden' op de juiste tekst", () => {
    // Het anker uit de export: start 272, eind 310 in de brontekst mét "1. " voorvoegsel.
    const el = { id: "k", klasse: "Brondefinitie", tekst: "Koninkrijk: Koninkrijk der Nederlanden" };
    const m = markeringVan(bron, [el], "k");
    expect(m).not.toBeNull();
    expect(bron.slice(m!.start, m!.eind)).toBe(el.tekst);

    // En dat stuk moet binnen het 1°-blok landen, niet ergens anders.
    const blok = blokken.find((b) => m!.start >= b.offset && m!.start < b.offset + b.regel.length);
    expect(blok?.nummer).toBe("1°.");
    expect(segmentenVanBlok(blok!, laagVan(bron, [el])).filter((s) => s.klasse).map((s) => s.tekst).join(""))
      .toBe(el.tekst);
  });

  it("geeft de vier geneste definities niveau 2 en de letters niveau 1", () => {
    expect(blokken.map((b) => `${b.nummer}:${b.niveau}`)).toEqual([
      "1.:0", "a.:1", "1°.:2", "2°.:2", "b.:1",
    ]);
  });
});
