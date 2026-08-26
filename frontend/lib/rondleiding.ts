// De rondleiding door de werkplek: welke stappen er zijn, in welke volgorde, en wat de browser
// onthoudt van wie hem al gezien heeft.
//
// Pure module. Vitest draait hier in node-env zonder DOM (zie `lib/selectie.ts`), dus alles wat te
// toetsen valt — de volgorde, het filter op rol, het hervatten — staat hier en niet in het component.
// Het opslaglaagje onderaan is bewust dun en faalt stil: dit is een hulpmiddel, geen contract.
//
// De teksten staan hier óók, en dat is opzet. Ze vormen samen één verhaal (van oriëntatie naar een
// afgeronde annotatie) en dat verhaal lees je alleen als de zinnen bij elkaar staan, niet verspreid
// over veertien componenten.

export const RONDLEIDING_VERSIE = 1;

/** Waar in het verhaal een stap hoort. Alleen voor de voortgangsweergave; de volgorde is de lijst. */
export type Fase = "orientatie" | "opdracht" | "beoordelen" | "afronding";

export interface Stap {
  id: string;
  /** Waar de bubbel aan hangt: het element met `data-tour="<anker>"`. */
  anker: string;
  /** Alternatief anker onder `lg`, waar de sidebar een drawer is en dus niet in beeld staat. */
  ankerSmal?: string;
  titel: string;
  tekst: string;
  /** Waaróm dit onderdeel er is. Zonder deze regel leert een rondleiding alleen waar dingen staan. */
  waarom?: string;
  fase: Fase;
  /** Moet het annotatie-artefact openstaan voordat deze stap iets kan aanwijzen? */
  artefactOpen?: boolean;
  /** Deze stap nodigt uit tot een echte handeling en wacht daarop. */
  interactie?: "akkoord";
  alleenBeheerder?: boolean;
}

export const STAPPEN: Stap[] = [
  {
    id: "gespreksvenster",
    anker: "thread",
    fase: "orientatie",
    titel: "Het gespreksvenster",
    tekst:
      "Alles gebeurt hier, in één gesprek. Je stelt een vraag over wet- en regelgeving, of je vraagt " +
      "een annotatie — hetzelfde venster, dezelfde manier van vragen.",
    waarom:
      "Er is bewust geen wetkiezer en geen formulier. Lex zoekt de bepaling zelf op in de " +
      "kennisgraaf, zodat je nooit een verkeerd artikelnummer overtypt.",
  },
  {
    id: "sidebar",
    anker: "sidebar",
    ankerSmal: "sidebar-mobiel",
    fase: "orientatie",
    titel: "Je werk terugvinden",
    tekst:
      "Hier staan je gesprekken. Nieuw gesprek begint schoon; onder Annotaties staan al je " +
      "geannoteerde bepalingen, met de nog te beoordelen bovenaan.",
    waarom:
      "Een annotatie overleeft het gesprek waarin hij gemaakt is. Verwijder je het gesprek, dan " +
      "blijft het document gewoon vindbaar.",
  },
  {
    id: "invoerveld",
    anker: "invoer",
    fase: "opdracht",
    titel: "Het invoerveld",
    tekst:
      "Eén veld, twee soorten opdracht. “Wat betekent 'belastingschuldige'?” levert een antwoord met " +
      "bronnen. “Annoteer artikel 9 van de Invorderingswet 1990” levert een JAS-annotatie om te " +
      "beoordelen.",
    waarom: "Je hoeft vooraf niets te kiezen. Lex leidt uit je zin af wat je bedoelt.",
  },
  {
    id: "bronnen",
    anker: "bronnen",
    fase: "opdracht",
    titel: "Een antwoord met bronnen",
    tekst:
      "Elk antwoord draagt de vindplaatsen waar het op steunt. Klap ze uit en klik door naar de " +
      "wettekst op wetten.overheid.nl.",
    waarom:
      "Een antwoord zonder vindplaats is voor jouw werk onbruikbaar. Je moet het kunnen nazoeken.",
  },
  {
    id: "brongetrouwheid",
    anker: "grounding",
    fase: "opdracht",
    titel: "Brongetrouwheid",
    tekst:
      "Dit blok zwijgt als alles klopt, en spreekt alleen als een verwijzing niet uit de graaf komt " +
      "of een citaat niet letterlijk in de opgehaalde tekst staat. Zo'n citaat wordt in de tekst " +
      "zelf geel gemarkeerd.",
    waarom:
      "Een groen vinkje bij élk antwoord leert je eroverheen kijken. Alleen wat aandacht vraagt, " +
      "krijgt aandacht.",
  },
  {
    id: "denkproces",
    anker: "denkproces",
    fase: "opdracht",
    titel: "Een annotatie duurt even",
    tekst:
      "Een annotatiebeurt duurt 60 tot 90 seconden. Onder “Zo is dit tot stand gekomen” zie je live " +
      "wat Lex doet: ophalen, markeren, en de eigen tegenlezer langs het resultaat.",
    waarom:
      "De beurt draait bij de server, niet in dit tabblad. Je kunt gerust herladen, van gesprek " +
      "wisselen of even weglopen — je verliest niets.",
  },
  {
    id: "artefact-openen",
    anker: "chip",
    fase: "beoordelen",
    titel: "De annotatie openen",
    tekst:
      "De uitkomst is geen lap tekst maar een document dat je kunt beoordelen. Klik de kaart aan — " +
      "op een breed scherm komt hij naast je gesprek te staan, zodat je kunt blijven vragen terwijl " +
      "je leest.",
  },
  {
    id: "wettekst",
    anker: "wettekst",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "De wettekst",
    tekst:
      "Dit is de letterlijke tekst uit de kennisgraaf — niet geparafraseerd, niet gereconstrueerd. " +
      "Kies je hiernaast een markering, dan licht hier op wáár die staat.",
    waarom:
      "Elke markering is een stuk van déze tekst, met een anker dat een herimport van de wet " +
      "overleeft.",
  },
  {
    id: "reviewlijst",
    anker: "review-kop",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "De reviewlijst",
    tekst:
      "Hier staan de voorstellen van Lex, in de vaste volgorde van de JAS-tabel. De teller laat zien " +
      "hoeveel je al beoordeelde; met de filters spring je naar wat nog te beoordelen is of wat " +
      "aandacht vraagt.",
    waarom:
      "De volgorde verandert nooit door te reviewen. Wat je goedkeurt springt niet weg, dus je raakt " +
      "je plek niet kwijt.",
  },
  {
    id: "reviewkaart",
    anker: "review-kaart",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "Wat een kaart je vertelt",
    tekst:
      "Elke kaart is één markering: het letterlijke fragment, de JAS-klasse in zijn eigen kleur, en " +
      "een oordeel — Geen bezwaar, Even kijken of Waarschijnlijk fout.",
    waarom:
      "Dat oordeel is geen zelfvertrouwen van het model, maar komt uit echte signalen: twijfelde Lex " +
      "tussen twee klassen, of staat het citaat niet stevig in de tekst. Het helpt je prioriteren, " +
      "het is geen cijfer.",
  },
  {
    id: "beslissen",
    anker: "review-acties",
    artefactOpen: true,
    interactie: "akkoord",
    fase: "beoordelen",
    titel: "Jij beslist",
    tekst:
      "Probeer het maar: klik op Akkoord. Verder kun je op de klassebadge klikken om te corrigeren, " +
      "met × een voorstel verwerpen (met reden), of via Vraag Lex een vraag over deze markering in " +
      "het chatveld klaarzetten. Met het toetsenbord gaat het sneller: j en k door de lijst, a " +
      "akkoord, x verwerpen, c klasse.",
    waarom:
      "Lex stelt voor, jij beslist. Elke beslissing gaat het auditspoor in — een voorstel verwerp " +
      "je, mét reden; je wist het niet weg.",
  },
  {
    id: "zelf-markeren",
    anker: "wettekst-tip",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "Zelf markeren",
    tekst:
      "Miste Lex iets? Selecteer het in de wettekst en kies zelf een klasse. Een bestaande markering " +
      "in- of uitkorten kan ook: klik hem aan en selecteer opnieuw.",
    waarom:
      "Jouw markering wint. Zodra jij iets vastlegt of beslist, laat een volgende ronde van de agent " +
      "het met rust.",
  },
  {
    id: "afronden",
    anker: "artefact-acties",
    artefactOpen: true,
    fase: "afronding",
    titel: "Afronden en exporteren",
    tekst:
      "Exporteren geeft je PDF, CSV of JSON — ook halverwege; het bestand zegt zelf hoeveel er nog " +
      "openstaat. Daarin zit ook het volledige spoor: elke beslissing, en met welk model Lex het " +
      "voorstel maakte. Afronden zet het document vast; heropenen kan altijd.",
    waarom:
      "“Alle kaarten beslist” is niet hetzelfde als “ik ben klaar”. Dat blijft jouw oordeel.",
  },
];

/** De stappen die deze gebruiker te zien krijgt. */
export function zichtbareStappen(isBeheerder: boolean): Stap[] {
  return STAPPEN.filter((s) => !s.alleenBeheerder || isBeheerder);
}

/** Index van de stap met dit id; -1 als hij niet (meer) bestaat. */
export function indexVan(stappen: Stap[], id: string | undefined): number {
  return id ? stappen.findIndex((s) => s.id === id) : -1;
}

/** Waar hervat je? Kent de app de bewaarde stap niet meer (de rondleiding is veranderd), dan begin
 *  je opnieuw in plaats van op een willekeurige plek te landen. */
export function hervatIndex(stappen: Stap[], gestoptBij: string | undefined): number {
  const i = indexVan(stappen, gestoptBij);
  return i === -1 ? 0 : i;
}

/** Moet het artefact openstaan om van `van` naar `naar` te kunnen? */
export function vraagtArtefact(stappen: Stap[], index: number): boolean {
  return Boolean(stappen[index]?.artefactOpen);
}

// --- waar komt de bubbel te staan ------------------------------------------------------------
//
// Hier en niet in het component, om dezelfde reden als de rest van dit bestand: vitest draait
// zonder DOM, en dit is precies het soort rekenwerk dat je wilt kunnen natellen zonder browser.

/** Ruimte tussen het aangewezen element en de bubbel, en tussen de bubbel en de schermrand. */
export const BUBBEL_MARGE = 12;

/** Een gemeten rechthoek in viewport-coördinaten. */
export interface Vak {
  top: number;
  left: number;
  breedte: number;
  hoogte: number;
}

export interface Afmeting {
  breedte: number;
  hoogte: number;
}

/** Waar de bubbel terechtkomt. `midden` betekent: niet aanwijzen maar centreren — dan hoort er
 *  ook geen spotlight omheen. */
export type Plaatsing =
  | { modus: "midden" }
  | { modus: "onder" | "boven" | "links" | "rechts"; top: number; left: number };

/** Houd een waarde binnen [onder, boven]. Bij een te krappe ruimte wint de ondergrens: liever
 *  tegen de bovenrand aan dan eronderuit gezakt. */
function klem(waarde: number, onder: number, boven: number): number {
  return Math.max(onder, Math.min(waarde, boven));
}

/** Domineert dit element het scherm? Dan is "ernaast wijzen" geen zinnige plaatsing meer: er ís
 *  geen naast. Het gespreksvenster en de sidebar vullen bijna de hele hoogte, en een spotlight
 *  eromheen licht het halve scherm op in plaats van iets aan te wijzen. */
export function domineert(vak: Vak, viewport: Afmeting): boolean {
  const hoogHalf = vak.hoogte > viewport.hoogte * 0.6;
  const grootVlak = vak.breedte * vak.hoogte > viewport.breedte * viewport.hoogte * 0.5;
  return hoogHalf || grootVlak;
}

/** Kies een plek voor de bubbel bij het aangewezen vak.
 *
 *  De volgorde is: onder, boven, rechts, links, en anders het midden. Doorslaggevend is of de
 *  bubbel er **past** — niet welke kant het meeste ruimte heeft. Dat laatste was de oude regel, en
 *  daardoor belandde de bubbel bij een schermvullend element buiten beeld: "meer ruimte" kan nog
 *  altijd te weinig zijn. Wat er ook uitkomt, de bubbel blijft binnen het scherm. */
export function plaatsBubbel(vak: Vak | null, bubbel: Afmeting, viewport: Afmeting): Plaatsing {
  if (!vak || domineert(vak, viewport)) return { modus: "midden" };

  const m = BUBBEL_MARGE;
  const onderRand = vak.top + vak.hoogte;
  const rechterRand = vak.left + vak.breedte;

  // Horizontaal uitgelijnd op het midden van het element, verticaal idem — in beide gevallen
  // geklemd, zodat een element aan de rand de bubbel niet mee naar buiten trekt.
  const linksGecentreerd = klem(
    vak.left + vak.breedte / 2 - bubbel.breedte / 2,
    m,
    Math.max(m, viewport.breedte - bubbel.breedte - m),
  );
  const topGecentreerd = klem(
    vak.top + vak.hoogte / 2 - bubbel.hoogte / 2,
    m,
    Math.max(m, viewport.hoogte - bubbel.hoogte - m),
  );

  if (viewport.hoogte - onderRand >= bubbel.hoogte + 2 * m) {
    return { modus: "onder", top: onderRand + m, left: linksGecentreerd };
  }
  if (vak.top >= bubbel.hoogte + 2 * m) {
    return { modus: "boven", top: vak.top - m - bubbel.hoogte, left: linksGecentreerd };
  }
  if (viewport.breedte - rechterRand >= bubbel.breedte + 2 * m) {
    return { modus: "rechts", top: topGecentreerd, left: rechterRand + m };
  }
  if (vak.left >= bubbel.breedte + 2 * m) {
    return { modus: "links", top: topGecentreerd, left: vak.left - m - bubbel.breedte };
  }
  return { modus: "midden" };
}

// --- browser-opslag (dun laagje om de pure functies heen) -------------------------------------

const SLEUTEL = "wa_rondleiding";

export interface Stand {
  versie: number;
  /** Heeft deze gebruiker de rondleiding afgerond of bewust overgeslagen? */
  gezien: boolean;
  /** Waar hij was toen hij werd onderbroken. Leeg zodra de rondleiding is afgerond. */
  gestoptBij?: string;
}

export const LEGE_STAND: Stand = { versie: RONDLEIDING_VERSIE, gezien: false };

/** Start de rondleiding vanzelf? Alleen als deze browser hem nooit heeft gezien, en alleen voor de
 *  versie die nu draait — een latere uitbreiding kan zich zo opnieuw aanbieden. */
export function moetStarten(stand: Stand): boolean {
  return !stand.gezien || stand.versie < RONDLEIDING_VERSIE;
}

export function leesStand(): Stand {
  try {
    const rauw = window.localStorage.getItem(SLEUTEL);
    if (!rauw) return LEGE_STAND;
    const stand = JSON.parse(rauw) as Partial<Stand>;
    return {
      versie: typeof stand.versie === "number" ? stand.versie : 0,
      gezien: stand.gezien === true,
      gestoptBij: typeof stand.gestoptBij === "string" ? stand.gestoptBij : undefined,
    };
  } catch {
    // Privémodus, volle opslag of rommel in de sleutel: dan biedt de rondleiding zich gewoon aan.
    return LEGE_STAND;
  }
}

export function schrijfStand(stand: Stand): void {
  try {
    window.localStorage.setItem(SLEUTEL, JSON.stringify(stand));
  } catch {
    /* opslag niet beschikbaar — dan start de rondleiding een volgende keer opnieuw */
  }
}
