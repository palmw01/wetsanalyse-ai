import { JAS_KLASSEN } from "./jas";
import { describe, expect, it } from "vitest";
import {
  groeneVoorstellen, heeftOordeel,
  bronVan,
  documentStand,
  documentStatusLabel,
  regelsVan,
  pastInFilter,
  sorteerReview,
  volgendeElement,
  vraagSuggesties,
  KLASSEVRAAG,
  overlaptSelectie,
  doelVanKandidaat,
  kandidaatLabel,
  kandidaatPrompt,
  isVerwijderd,
  isBeslist,
  slotVan,
  isDocumentVergrendeld,
  alGemarkeerd,
} from "./annotatie";
import slotregel from "./slotregel.json";
import type { AnnotatieElement, GraafArtikel } from "./types";

describe("documentStand", () => {
  const laag = { status: "in_review" as const, aantal_elementen: 3, te_beoordelen: 1 };

  it("houdt de status zolang er iets te beoordelen is", () => {
    expect(documentStand(laag)).toEqual({ label: "In behandeling", toon: "geel" });
  });

  it("toont een eigen label als alleen het afronden ontbreekt", () => {
    const stand = documentStand({ ...laag, te_beoordelen: 0 });
    expect(stand.label).toBe("Klaar om af te ronden");
    expect(stand.toon).toBe("neutraal");
    expect(stand.uitleg).toBeTruthy();
  });

  it("laat een lege laag en een afgeronde laag met rust", () => {
    expect(documentStand({ ...laag, aantal_elementen: 0, te_beoordelen: 0 }).label).toBe("In behandeling");
    expect(documentStand({ ...laag, status: "geaccordeerd", te_beoordelen: 0 }))
      .toEqual({ label: "Afgerond", toon: "groen" });
  });
});

describe("documentStatusLabel", () => {
  it("mapt de drie documentstatussen naar NL-labels", () => {
    expect(documentStatusLabel("in_review")).toBe("In behandeling");
    expect(documentStatusLabel("geaccordeerd")).toBe("Afgerond");
    expect(documentStatusLabel("gepromoveerd")).toBe("In de graaf");
  });
});

// De agent kan hetzelfde element meer dan eens sturen. Zonder ontdubbelen zou de werkplek dubbele kaarten tonen én dubbel naar de server sturen.
describe("kandidaten bij een onderwerp-vraag", () => {
  const k = { bwbId: "BWBR0004770", artikel: "36a", lid: "1", citeertitel: "Invorderingswet 1990" };

  it("noemt lid alleen als er een lid is", () => {
    expect(kandidaatLabel(k)).toBe("Artikel 36a, lid 1 – Invorderingswet 1990");
    expect(kandidaatLabel({ bwbId: "BWBR1", artikel: "36" })).toBe("Artikel 36");
  });

  it("zet het bwbId in de vervolgopdracht", () => {
    // Zonder bwbId moet de ophaal-agent opnieuw zoeken op de citeertitel – en kan hij bij een
    // andere bepaling uitkomen dan die de jurist aanwees.
    expect(kandidaatPrompt(k)).toContain("BWBR0004770");
    expect(kandidaatPrompt(k)).toContain("artikel 36a lid 1");
  });

  it("levert de keuze ook als gestructureerd doel", () => {
    // Hiermee slaat de agent de supervisor en de ophaal-agent over – en kan hij niet bij een
    // andere bepaling uitkomen dan de jurist zojuist aanwees.
    expect(doelVanKandidaat(k)).toEqual({
      bwbId: "BWBR0004770",
      artikel: "36a",
      lid: "1",
      citeertitel: "Invorderingswet 1990",
    });
  });

  it("laat lege velden weg uit het doel", () => {
    expect(doelVanKandidaat({ bwbId: "BWBR1", artikel: "36" })).toEqual({
      bwbId: "BWBR1",
      artikel: "36",
    });
  });
});

// --- de reden hoeft niet meer gevraagd te worden ------------------------------------------------

const ELEMENT = {
  id: "el-1",
  klasse: "Rechtsobject",
  tekst: "belastingaanslag",
  lid: "1",
  toelichting: "het object",
  vindplaats: "",
  herkomst: "agent",
  gewijzigd_door: "",
  lifecycle: "voorgesteld",
  alternatieven: [],
  aandacht: null,
  review_uitleg: "",
  anker: null,
  diff: {},
  beslissingen: [],
} as unknown as AnnotatieElement;

describe("overlaptSelectie", () => {
  const bereik = { start: 10, eind: 26 };

  it("herkent een selectie die het fragment raakt", () => {
    expect(overlaptSelectie({ start: 6, eind: 26 }, bereik)).toBe(true);   // uitbreiden naar links
    expect(overlaptSelectie({ start: 10, eind: 20 }, bereik)).toBe(true);  // inkorten
    expect(overlaptSelectie({ start: 26, eind: 40 }, bereik)).toBe(true);  // sluit erop aan
  });

  it("herkent een selectie die er los van staat", () => {
    expect(overlaptSelectie({ start: 0, eind: 9 }, bereik)).toBe(false);
    expect(overlaptSelectie({ start: 27, eind: 40 }, bereik)).toBe(false);
  });
});

// --- de lijst ordenen -----------------------------------------------------------------------------

function el(id: string, extra: Partial<AnnotatieElement> = {}): AnnotatieElement {
  return { ...ELEMENT, id, ...extra } as AnnotatieElement;
}

describe("sorteerReview", () => {
  it("volgt de canonieke JAS-tabelvolgorde, niet de invoervolgorde", () => {
    const lijst = [
      el("vw", { klasse: "Voorwaarde" }),
      el("subj", { klasse: "Rechtssubject" }),
      el("feit", { klasse: "Rechtsfeit" }),
      el("obj", { klasse: "Rechtsobject" }),
    ];
    expect(sorteerReview(lijst).map((e) => e.id)).toEqual(["subj", "obj", "feit", "vw"]);
  });

  it("zet een onbekende klasse achteraan", () => {
    const lijst = [el("x", { klasse: "Iets Onbekends" }), el("subj", { klasse: "Rechtssubject" })];
    expect(sorteerReview(lijst).map((e) => e.id)).toEqual(["subj", "x"]);
  });

  it("sorteert het lid numeriek, niet lexicaal", () => {
    // "10" < "2" als je op tekst sorteert; dat is precies de val.
    const lijst = [
      el("tien", { klasse: "Rechtsobject", lid: "10" }),
      el("twee", { klasse: "Rechtsobject", lid: "2" }),
      el("geen", { klasse: "Rechtsobject", lid: "" }),
    ];
    expect(sorteerReview(lijst).map((e) => e.id)).toEqual(["geen", "twee", "tien"]);
  });

  it("sorteert binnen een klasse op de plek in de tekst", () => {
    const lijst = [el("laat", { klasse: "Rechtsobject" }), el("vroeg", { klasse: "Rechtsobject" })];
    const posities = new Map([["laat", 80], ["vroeg", 10]]);
    expect(sorteerReview(lijst, posities).map((e) => e.id)).toEqual(["vroeg", "laat"]);
  });

  it("zet een markering die niet in de tekst te vinden is achteraan binnen zijn klasse", () => {
    const lijst = [
      el("zwevend", { klasse: "Rechtsobject" }),
      el("gevonden", { klasse: "Rechtsobject" }),
      el("later", { klasse: "Voorwaarde" }),
    ];
    const posities = new Map([["gevonden", 10], ["later", 5]]);
    // "zwevend" heeft geen positie: achteraan bij de Rechtsobjecten, maar nog wél vóór de Voorwaarde.
    expect(sorteerReview(lijst, posities).map((e) => e.id)).toEqual(["gevonden", "zwevend", "later"]);
  });

  it("verandert NIET als een element wordt beoordeeld", () => {
    // Dit is het hele punt: een goedgekeurd element springt niet naar achteren en de rest schuift niet op.
    const voor = [
      el("a", { klasse: "Rechtssubject", aandacht: "groen" }),
      el("b", { klasse: "Rechtsobject", aandacht: "rood" }),
      el("c", { klasse: "Rechtsfeit" }),
    ];
    const na = [
      el("a", { klasse: "Rechtssubject", aandacht: "groen", lifecycle: "human_approved" }),
      el("b", { klasse: "Rechtsobject", aandacht: "rood" }),
      el("c", { klasse: "Rechtsfeit", lifecycle: "rejected" }),
    ];
    expect(sorteerReview(na).map((e) => e.id)).toEqual(sorteerReview(voor).map((e) => e.id));
  });

  it("is stabiel bij een volledig gelijke sleutel", () => {
    const lijst = [el("1"), el("2"), el("3")];
    expect(sorteerReview(lijst).map((e) => e.id)).toEqual(["1", "2", "3"]);
  });

  it("werkt zonder positiekaart", () => {
    const lijst = [el("vw", { klasse: "Voorwaarde" }), el("subj", { klasse: "Rechtssubject" })];
    expect(sorteerReview(lijst).map((e) => e.id)).toEqual(["subj", "vw"]);
  });

  it("laat de invoer ongemoeid", () => {
    const lijst = [el("a", { klasse: "Voorwaarde" }), el("b", { klasse: "Rechtssubject" })];
    sorteerReview(lijst);
    expect(lijst.map((e) => e.id)).toEqual(["a", "b"]);
  });
});

describe("pastInFilter", () => {
  it("filtert op te beoordelen", () => {
    expect(pastInFilter(el("a"), "te_beoordelen")).toBe(true);
    expect(pastInFilter(el("b", { lifecycle: "human_approved" }), "te_beoordelen")).toBe(false);
  });

  it("filtert op aandacht – groen telt niet mee", () => {
    expect(pastInFilter(el("r", { aandacht: "rood" }), "aandacht")).toBe(true);
    expect(pastInFilter(el("g", { aandacht: "groen" }), "aandacht")).toBe(false);
    expect(pastInFilter(el("x"), "aandacht")).toBe(false);
  });

  it("laat bij 'alles' alles door", () => {
    expect(pastInFilter(el("b", { lifecycle: "rejected" }), "alles")).toBe(true);
  });
});

describe("slotVan", () => {
  // Dezelfde gevallen draaien tegen `slot_van` in de api (`api/tests/test_slotregel_drift.py`).
  it.each(slotregel)("$geval", ({ element, laag_status, slot }) => {
    expect(slotVan(element, laag_status)).toBe(slot);
  });

  it("is een ander begrip dan beslist: een aangepast element is beslist maar blijft bewerkbaar", () => {
    const bewerkt = el("c", { lifecycle: "edited" });
    expect(isBeslist(bewerkt)).toBe(true);
    expect(slotVan(bewerkt)).toBe("geen");
  });
});

describe("alGemarkeerd", () => {
  const items = [
    el("a", { klasse: "Rechtsfeit", tekst: "zes weken na de dagtekening" }),
  ];

  it("herkent een fragment dat er al ligt, ongeacht spaties en kapitalen", () => {
    expect(alGemarkeerd(items, "Rechtsfeit", "  Zes   weken na de dagtekening ")).toBe(true);
  });

  it("telt een verworpen markering NIET mee", () => {
    // Je hebt hem net weggestuurd; "inmiddels gemarkeerd" is dan het omgekeerde van wat er gebeurde,
    // en het ontbrekend-item bleef onaanklikbaar staan terwijl je hem opnieuw wilde toevoegen.
    const verworpen = [el("a", {
      klasse: "Rechtsfeit", tekst: "zes weken na de dagtekening", lifecycle: "rejected",
    })];
    expect(alGemarkeerd(verworpen, "Rechtsfeit", "zes weken na de dagtekening")).toBe(false);
  });

  it("kijkt naar klasse én fragment, en negeert een leeg fragment", () => {
    expect(alGemarkeerd(items, "Rechtssubject", "zes weken na de dagtekening")).toBe(false);
    expect(alGemarkeerd(items, "Rechtsfeit", "   ")).toBe(false);
  });
});

describe("isDocumentVergrendeld", () => {
  it("bevriest alleen een afgerond document", () => {
    expect(isDocumentVergrendeld({ status: "geaccordeerd" })).toBe(true);
    expect(isDocumentVergrendeld({ status: "in_review" })).toBe(false);
    expect(isDocumentVergrendeld({ status: "gepromoveerd" })).toBe(false);
  });
});

describe("volgendeElement", () => {
  const lijst = [el("1"), el("2", { lifecycle: "human_approved" }), el("3")];

  it("loopt vooruit en achteruit door de lijst", () => {
    expect(volgendeElement(lijst, "1")?.id).toBe("2");
    expect(volgendeElement(lijst, "2", -1)?.id).toBe("1");
  });

  it("stopt aan het eind in plaats van rond te lopen", () => {
    // Rondlopen laat je onbedoeld een tweede ronde beginnen zonder dat je het doorhebt.
    expect(volgendeElement(lijst, "3")).toBeUndefined();
    expect(volgendeElement(lijst, "1", -1)).toBeUndefined();
  });

  it("begint bij de rand als er niets geselecteerd is", () => {
    expect(volgendeElement(lijst, undefined)?.id).toBe("1");
    expect(volgendeElement(lijst, undefined, -1)?.id).toBe("3");
  });

  it("slaat bij auto-advance de beslist-elementen over", () => {
    expect(volgendeElement(lijst, "1", 1, true)?.id).toBe("3");
  });

  it("geeft niets terug als de lijst leeg is", () => {
    expect(volgendeElement([], undefined)).toBeUndefined();
  });
});

// --- de brontekst en de lidnummers -----------------------------------------------------------------

describe("regelsVan", () => {
  const artikel = (leden: { lid: string; tekst: string }[]): GraafArtikel => ({
    bwbId: "BWBR0004770", artikel: "8", citeertitel: "Invorderingswet 1990", opschrift: "",
    leden_teksten: leden,
  });

  it("houdt het lidnummer bij de regel waarin het staat", () => {
    const regels = regelsVan(artikel([{ lid: "3", tekst: "De ontvanger maant aan." }]));
    expect(regels).toEqual([{ lid: "3", regel: "3. De ontvanger maant aan." }]);
  });

  it("laat het nummer weg bij een artikel zonder genummerde leden", () => {
    expect(regelsVan(artikel([{ lid: "", tekst: "Deze wet berust op…" }]))).toEqual([
      { lid: "", regel: "Deze wet berust op…" },
    ]);
  });

  it("slaat lege leden over", () => {
    const regels = regelsVan(artikel([{ lid: "1", tekst: "Eerste." }, { lid: "2", tekst: "  " }]));
    expect(regels).toEqual([{ lid: "1", regel: "1. Eerste." }]);
  });

  it("levert een bron waarin de offsets van de regels kloppen", () => {
    const regels = regelsVan(artikel([{ lid: "1", tekst: "Eerste." }, { lid: "2", tekst: "Tweede." }]));
    const bron = bronVan(regels);
    expect(bron).toBe("1. Eerste.\n\n2. Tweede.");
    expect(bron.indexOf("Tweede")).toBe("1. Eerste.\n\n2. ".length);
  });
});

describe("isVerwijderd", () => {
  it("herkent de 404 als 'bestaat niet (meer)'", () => {
    // De api geeft 404 zowel bij een verwijderd document als bij dat van iemand anders; voor de UI
    // is dat hetzelfde: opnieuw proberen kan niet slagen.
    expect(isVerwijderd({ status: 404, detail: "Onbekend annotatie-document: doc-x" })).toBe(true);
  });

  it("laat storingen storingen blijven (die mogen wél een retry houden)", () => {
    expect(isVerwijderd({ status: 502, detail: "Upstream onbereikbaar" })).toBe(false);
    expect(isVerwijderd({ status: 504, detail: "Wachttijd verstreken" })).toBe(false);
  });

  it("is geen ApiError → geen verwijderd", () => {
    expect(isVerwijderd(new Error("netwerk weg"))).toBe(false);
    expect(isVerwijderd(undefined)).toBe(false);
  });
});

describe("vraagSuggesties", () => {
  it("noemt de klasse van het element in de eerste vraag", () => {
    const [eerste] = vraagSuggesties(el("a", { klasse: "Tijdsaanduiding" }));
    expect(eerste).toBe("Waarom is dit een Tijdsaanduiding?");
  });

  it("vraagt bij twijfel naar het alternatief", () => {
    // Daar zit het verschil per element: "waarom geen Voorwaarde?" is scherper dan welke vaste
    // formulering ook, en de agent heeft dat alternatief zelf voorgesteld.
    const met = vraagSuggesties(el("a", {
      klasse: "Tijdsaanduiding",
      alternatieven: [{ klasse: "Voorwaarde", motivatie: "kan ook een conditie zijn" }],
    }));
    expect(met[2]).toBe("Waarom geen Voorwaarde?");
  });

  it("stelt als tweede vraag die van de klasse, en zonder alternatief de afbakening", () => {
    const zonder = vraagSuggesties(el("a", { klasse: "Tijdsaanduiding", alternatieven: [] }));
    expect(zonder[1]).toBe(KLASSEVRAAG.Tijdsaanduiding);
    expect(zonder[2]).toBe("Klopt de afbakening van dit fragment?");
  });

  it("heeft voor elke JAS-klasse een eigen vraag", () => {
    expect(JAS_KLASSEN.filter((k) => !KLASSEVRAAG[k])).toEqual([]);
    expect(Object.keys(KLASSEVRAAG).sort()).toEqual([...JAS_KLASSEN].sort());
  });

  it("valt bij een onbekende klasse terug op afbakening en samenhang", () => {
    expect(vraagSuggesties({ klasse: "Iets anders" }).slice(1)).toEqual([
      "Klopt de afbakening van dit fragment?", "Hoe verhoudt dit zich tot de rest van het artikel?"]);
  });

  it("noemt een alternatief dat gelijk is aan de klasse niet", () => {
    expect(vraagSuggesties({ klasse: "Voorwaarde", alternatieven: [{ klasse: "Voorwaarde" }] })[2])
      .toBe("Klopt de afbakening van dit fragment?");
  });

  it("levert er altijd precies drie, en geen dubbele", () => {
    const vragen = vraagSuggesties(el("a", {
      klasse: "Voorwaarde",
      alternatieven: [{ klasse: "Tijdsaanduiding", motivatie: "" }],
    }));
    expect(vragen).toHaveLength(3);
    expect(new Set(vragen).size).toBe(3);
  });
});


describe("beoordeeld en oordeel (B18, B19)", () => {
  it("een aangepast element is beslist, een voorstel niet", () => {
    expect(isBeslist({ lifecycle: "edited" })).toBe(true);
    expect(isBeslist({ lifecycle: "published" })).toBe(true);
    expect(isBeslist({ lifecycle: "voorgesteld" })).toBe(false);
  });

  it("de regel van een eigen markering is geen oordeel", () => {
    expect(heeftOordeel({ beslissingen: [{ type: "markering" }] })).toBe(false);
    expect(heeftOordeel({ beslissingen: [{ type: "markering" }, { type: "comment" }] })).toBe(true);
    expect(heeftOordeel({})).toBe(false);
  });
});

describe("groeneVoorstellen", () => {
  const el = (x: Partial<Parameters<typeof groeneVoorstellen>[0][number]>) =>
    ({ lifecycle: "voorgesteld", klasse: "Rechtsfeit", herkomst: "agent", aandacht: null, ...x });

  it("laat geel, rood, zonder klasse, beslist, verouderd en eigen werk staan", () => {
    const groen = el({ aandacht: "groen" }), kaal = el({});
    expect(groeneVoorstellen([groen, kaal, el({ aandacht: "geel" }), el({ aandacht: "rood" }), el({ klasse: "" }),
      el({ lifecycle: "human_approved" }), el({ verouderd: true }), el({ herkomst: "mens" })])).toEqual([groen, kaal]);
  });
});
