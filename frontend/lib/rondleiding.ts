// De rondleiding door de werkplek: welke stappen er zijn, in welke volgorde, en wat de browser
// onthoudt van wie hem al gezien heeft.
//
// Pure module. Vitest draait hier in node-env zonder DOM (zie `lib/selectie.ts`), dus alles wat te
// toetsen valt – de volgorde, het filter op rol, het hervatten – staat hier en niet in het component.
// Het opslaglaagje onderaan is bewust dun en faalt stil: dit is een hulpmiddel, geen contract.
//
// De teksten staan hier óók, en dat is opzet. Ze vormen samen één verhaal (van oriëntatie naar een
// afgeronde annotatie) en dat verhaal lees je alleen als de zinnen bij elkaar staan, niet verspreid
// over veertien componenten.

export const RONDLEIDING_VERSIE = 2;

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
      "Hier speelt alles zich af. Je stelt een vraag over wet- en regelgeving, of je vraagt om een " +
      "annotatie. Allebei typ je in ditzelfde venster.",
    waarom:
      "Je zoekt zelf geen wet op. Lex vindt de bepaling in de kennisgraaf, dus je kunt geen " +
      "verkeerd artikelnummer overtypen.",
  },
  {
    id: "sidebar",
    anker: "sidebar",
    ankerSmal: "sidebar-mobiel",
    fase: "orientatie",
    titel: "Je werk terugvinden",
    tekst:
      "Je gesprekken staan hier. Onder Annotaties vind je alle bepalingen die je hebt laten " +
      "annoteren, met de onbeoordeelde bovenaan.",
    waarom:
      "Een annotatie blijft bestaan als je het gesprek verwijdert. Opruimen kost je dus geen werk.",
  },
  {
    id: "invoerveld",
    anker: "invoer",
    fase: "opdracht",
    titel: "Het invoerveld",
    tekst:
      "Twee soorten opdracht, één veld. Vraag je “Wat betekent 'belastingschuldige'?”, dan krijg je " +
      "een antwoord met bronnen. Vraag je “Annoteer artikel 9 van de Invorderingswet 1990”, dan " +
      "krijg je een JAS-annotatie om te beoordelen.",
    waarom: "Je kiest vooraf niets. Lex leidt uit je zin af wat je bedoelt.",
  },
  {
    id: "bronnen",
    anker: "bronnen",
    fase: "opdracht",
    titel: "Een antwoord met bronnen",
    tekst:
      "Onder elk antwoord staan de vindplaatsen waarop het steunt. Klap ze uit en klik door naar de " +
      "wettekst op wetten.overheid.nl.",
    waarom: "Je moet alles kunnen nazoeken. Daarom noemt Lex altijd waar iets vandaan komt.",
  },
  {
    id: "brongetrouwheid",
    anker: "grounding",
    fase: "opdracht",
    titel: "Brongetrouwheid",
    tekst:
      "Dit blok verschijnt alleen als er iets niet klopt: een verwijzing die niet uit de graaf komt, " +
      "of een citaat dat niet letterlijk in de opgehaalde tekst staat. Zo'n citaat kleurt geel in " +
      "de tekst zelf.",
    waarom: "Zo valt het op als het één keer misgaat.",
  },
  {
    id: "denkproces",
    anker: "denkproces",
    fase: "opdracht",
    titel: "Een annotatie duurt even",
    tekst:
      "Reken op 60 tot 90 seconden. Onder “Zo is dit tot stand gekomen” volg je live wat Lex doet: " +
      "de tekst ophalen, markeren, en het resultaat langs de tegenlezer halen.",
    waarom:
      "De beurt draait op de server. Je kunt herladen, van gesprek wisselen of even weglopen zonder " +
      "iets te verliezen.",
  },
  {
    id: "artefact-openen",
    anker: "chip",
    fase: "beoordelen",
    titel: "De annotatie openen",
    tekst:
      "De uitkomst is een document dat je kunt beoordelen. Klik de kaart aan. Op een breed scherm " +
      "komt hij naast je gesprek te staan, zodat je kunt blijven vragen terwijl je leest.",
  },
  {
    id: "wettekst",
    anker: "wettekst",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "De wettekst",
    tekst:
      "Dit is de letterlijke tekst uit de kennisgraaf. Kies hiernaast een markering en je ziet " +
      "meteen waar die staat.",
    waarom:
      "Elke markering wijst een stuk van deze tekst aan. Dat anker blijft kloppen als de wet " +
      "opnieuw wordt ingelezen.",
  },
  {
    id: "reviewlijst",
    anker: "review-kop",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "De reviewlijst",
    tekst:
      "Hier staan de voorstellen van Lex, in de vaste volgorde van de JAS-tabel. De teller houdt bij " +
      "hoeveel je al beoordeelde. Met de filters spring je naar wat nog openstaat of wat aandacht " +
      "vraagt.",
    waarom: "De volgorde verandert niet terwijl je werkt, dus je raakt je plek nooit kwijt.",
  },
  {
    id: "reviewkaart",
    anker: "review-kaart",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "Wat een kaart je vertelt",
    tekst:
      "Elke kaart is één markering: het letterlijke fragment, de JAS-klasse in zijn eigen kleur, en " +
      "een oordeel. Dat oordeel luidt Geen bezwaar, Even kijken of Waarschijnlijk fout.",
    waarom:
      "Het oordeel komt uit concrete signalen, zoals twijfel tussen twee klassen. Gebruik het om te " +
      "prioriteren.",
  },
  {
    id: "beslissen",
    // Hetzelfde anker als de vorige stap, en dat is geen kopieerfout: die beschrijft de kaart, deze
    // de handeling. Het gat in de dimlaag hangt aan dit anker (`klikGat`), en het moet de héle kaart
    // vrijgeven. Wees hier alleen de knoprij aan, dan viel er precies één ding te doen: die rij
    // stopt de klik (`ReviewQueue`), dus er raakte niets geselecteerd, en zonder selectie doen j, k,
    // a, x en c niets (`ArtefactInhoud`) en liggen de klassebadge en × buiten het gat. Een stap die
    // vijf handelingen noemt en er één toelaat, leert de verkeerde les.
    anker: "review-kaart",
    artefactOpen: true,
    interactie: "akkoord",
    fase: "beoordelen",
    titel: "Jij beslist",
    tekst:
      "Probeer het: klik de kaart aan en dan op Akkoord. Je kunt ook op de klassebadge klikken om te " +
      "corrigeren, of een voorstel verwerpen met × (met reden). Met het toetsenbord gaat het " +
      "sneller: j en k door de lijst, a voor akkoord, x voor verwerpen, c voor klasse.",
    waarom:
      "Elke beslissing komt in het auditspoor. Een voorstel dat je verwerpt blijft zichtbaar, met " +
      "jouw reden erbij.",
  },
  {
    id: "zelf-markeren",
    anker: "wettekst-tip",
    artefactOpen: true,
    fase: "beoordelen",
    titel: "Zelf markeren",
    tekst:
      "Miste Lex iets? Selecteer het in de wettekst en kies zelf een klasse. Een bestaande markering " +
      "korter of langer maken kan ook: klik hem aan en selecteer opnieuw.",
    waarom: "Wat jij vastlegt blijft staan. Een volgende ronde van Lex laat het met rust.",
  },
  {
    id: "afronden",
    anker: "artefact-acties",
    artefactOpen: true,
    fase: "afronding",
    titel: "Afronden en exporteren",
    tekst:
      "Exporteren kan altijd, ook halverwege: als PDF, CSV of JSON. Het bestand vermeldt hoeveel er " +
      "nog openstaat en bevat het volledige spoor, inclusief het model waarmee Lex de voorstellen " +
      "maakte. Afronden zet het document vast; heropenen kan daarna nog steeds.",
    waarom: "Alle kaarten beslissen is iets anders dan klaar zijn. Dat oordeel blijft aan jou.",
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

/** Wat er met het artefactpaneel moet gebeuren om bij `naar` te passen.
 *
 *  Het paneel hoort bij de stap, in beide richtingen. Alleen openen was niet genoeg: liep je terug
 *  naar een stap die de thread aanwijst, dan bleef het artefact ervoor staan en wees de bubbel naar
 *  iets wat je niet kon zien. */
export function artefactActie(
  paneelOpen: boolean,
  naar: Stap | undefined,
): "openen" | "sluiten" | null {
  const nodig = Boolean(naar?.artefactOpen);
  if (nodig && !paneelOpen) return "openen";
  if (!nodig && paneelOpen) return "sluiten";
  return null;
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

/** Waar de bubbel terechtkomt. `midden` betekent: niet aanwijzen maar centreren – dan hoort er
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
 *  bubbel er **past** – niet welke kant het meeste ruimte heeft. Dat laatste was de oude regel, en
 *  daardoor belandde de bubbel bij een schermvullend element buiten beeld: "meer ruimte" kan nog
 *  altijd te weinig zijn. Wat er ook uitkomt, de bubbel blijft binnen het scherm.
 *
 *  `voorkeur` is de kant die hij bij de vórige meting koos. Past die nog, dan wint hij van de vaste
 *  volgorde – en dan telt `domineert` ook niet meer. Zonder dat sprong de bubbel middenin een
 *  handeling van kant: het klassepalet maakt de reviewkaart in één klap hoger, en dan is er ineens
 *  geen ruimte meer onder het element (of gaat het element domineren) en stond de bubbel opeens
 *  gecentreerd. Een uitklapper mag de bubbel verschuiven, niet verplaatsen. */
export function plaatsBubbel(
  gemeten: Vak | null,
  bubbel: Afmeting,
  viewport: Afmeting,
  voorkeur?: Plaatsing["modus"],
): Plaatsing {
  if (!gemeten) return { modus: "midden" };
  // Rekenen op wat er in beeld staat: een element dat half uit zijn scroller hangt levert anders een
  // rand ver buiten het scherm, en daar werd de bubbel dan tegenaan gezet. Is er niets van te zien,
  // dan valt er ook niets aan te wijzen.
  const vak = zichtbaarDeel(gemeten, viewport);
  if (!vak) return { modus: "midden" };

  const m = BUBBEL_MARGE;
  const onderRand = vak.top + vak.hoogte;
  const rechterRand = vak.left + vak.breedte;
  /** Houd een plek binnen het scherm. De fit-toetsen hieronder gaan uit van een vak dat in beeld
   *  staat; deze klem maakt de belofte in de docstring waar, wat er ook in gemeten wordt. */
  const binnen = (top: number, left: number): { top: number; left: number } => ({
    top: klem(top, m, Math.max(m, viewport.hoogte - bubbel.hoogte - m)),
    left: klem(left, m, Math.max(m, viewport.breedte - bubbel.breedte - m)),
  });

  // Horizontaal uitgelijnd op het midden van het element, verticaal idem – in beide gevallen
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

  /** Past de bubbel aan deze kant? Zo ja, waar komt hij dan te staan. */
  const kandidaat = (modus: Plaatsing["modus"]): Plaatsing | null => {
    if (modus === "onder" && viewport.hoogte - onderRand >= bubbel.hoogte + 2 * m) {
      return { modus, ...binnen(onderRand + m, linksGecentreerd) };
    }
    if (modus === "boven" && vak.top >= bubbel.hoogte + 2 * m) {
      return { modus, ...binnen(vak.top - m - bubbel.hoogte, linksGecentreerd) };
    }
    if (modus === "rechts" && viewport.breedte - rechterRand >= bubbel.breedte + 2 * m) {
      return { modus, ...binnen(topGecentreerd, rechterRand + m) };
    }
    if (modus === "links" && vak.left >= bubbel.breedte + 2 * m) {
      return { modus, ...binnen(topGecentreerd, vak.left - m - bubbel.breedte) };
    }
    return null;
  };

  // De kant van de vorige meting krijgt voorrang, ook boven `domineert`: die kant is al eens gekozen
  // toen het element nog klein was, en de gebruiker heeft de bubbel dáár zien staan.
  const vastgehouden = voorkeur ? kandidaat(voorkeur) : null;
  if (vastgehouden) return vastgehouden;

  if (domineert(vak, viewport)) return { modus: "midden" };
  for (const modus of ["onder", "boven", "rechts", "links"] as const) {
    const plek = kandidaat(modus);
    if (plek) return plek;
  }
  return { modus: "midden" };
}

/** Waar de dimlaag een gat laat, zodat de gebruiker de aangewezen knop kan indrukken.
 *
 *  Alleen in een stap die om een handeling vraagt. In alle andere stappen dekt de laag alles af,
 *  want daar is elke klik buiten de bubbel er een die de rondleiding kan slopen.
 *
 *  Dit hangt bewust aan het gemeten vak en niet aan de plaatsing van de bubbel. Die twee werden
 *  eerder door elkaar gehaald: stond de bubbel gecentreerd (te weinig ruimte ernaast), dan verdween
 *  het gat terwijl het element er gewoon was, en kon je de knop niet meer indrukken. Waar de bubbel
 *  staat en of de knop bereikbaar is, zijn verschillende vragen.
 *
 *  De marge is ruimer dan die van de spotlight: het gat mag over de rand vallen, maar een meting die
 *  een paar pixels achterloopt mag nooit de knop afdekken. */
export function klikGat(stap: Stap, vak: Vak | null, marge: number): Vak | null {
  if (!stap.interactie || !vak) return null;
  return uitsnede(vak, marge);
}

/** Het vak plus een marge eromheen: de uitsparing die de dimlaag openlaat.
 *
 *  Los van `klikGat`, want er zijn twee verschillende vragen. **Zien** doe je het aangewezen element
 *  in élke stap – gedimd wijst het niets aan, dan zie je alleen een rand om iets grijs. **Bedienen**
 *  mag alleen in de stap die om een handeling vraagt; daarbuiten legt `TourBubbel` een onzichtbare
 *  vanger over ditzelfde vak. */
export function uitsnede(vak: Vak, marge: number): Vak {
  return {
    top: vak.top - marge,
    left: vak.left - marge,
    breedte: vak.breedte + marge * 2,
    hoogte: vak.hoogte + marge * 2,
  };
}

/** Het deel van `vak` dat werkelijk in beeld staat; `null` als er niets van te zien is.
 *
 *  `getBoundingClientRect` geeft het **ongeclipte** vak, ook als het element binnen een scroller
 *  hangt en er maar een strook van zichtbaar is. Een reviewkaart die uitklapt tot 600px in een
 *  scroller van 400px levert dus een vak dat tot ver onder de schermrand doorloopt, en de bubbel
 *  werd daar netjes onder gehangen – buiten beeld. Plaatsen doe je bij wat de gebruiker ziet. */
export function zichtbaarDeel(vak: Vak, viewport: Afmeting): Vak | null {
  const top = Math.max(0, vak.top);
  const links = Math.max(0, vak.left);
  const onder = Math.min(viewport.hoogte, vak.top + vak.hoogte);
  const rechts = Math.min(viewport.breedte, vak.left + vak.breedte);
  if (onder <= top || rechts <= links) return null;
  return { top, left: links, breedte: rechts - links, hoogte: onder - top };
}

/** De dimlaag als losse rechthoeken, met een gat op `gat`.
 *
 *  Waarom niet één vlak met een box-shadow, zoals eerst: een box-shadow tekent wel maar **vangt
 *  geen kliks**. De laag bestond dus visueel en niet als klikvlak, en daardoor bleef de hele
 *  werkplek tijdens de rondleiding bedienbaar. Wie op "Nieuw gesprek" klikte, gooide weg waar de
 *  volgende stap naar wees.
 *
 *  Vier rechthoeken lossen dat op én houden de uitzondering mogelijk die er moet zijn: in de stap
 *  waar je zelf iets doet, blijft precies dat ene element bereikbaar.
 *
 *  Zonder `gat` is het één vlak over het hele scherm. Randen worden geklemd op 0, zodat een element
 *  dat half buiten beeld valt geen negatieve afmetingen oplevert. */
export function maskRechthoeken(gat: Vak | null, viewport: Afmeting): Vak[] {
  if (!gat) {
    return [{ top: 0, left: 0, breedte: viewport.breedte, hoogte: viewport.hoogte }];
  }
  const top = Math.max(0, gat.top);
  const links = Math.max(0, gat.left);
  const onder = Math.min(viewport.hoogte, gat.top + gat.hoogte);
  const rechts = Math.min(viewport.breedte, gat.left + gat.breedte);

  const vakken: Vak[] = [
    { top: 0, left: 0, breedte: viewport.breedte, hoogte: top },
    { top: onder, left: 0, breedte: viewport.breedte, hoogte: viewport.hoogte - onder },
    { top, left: 0, breedte: links, hoogte: onder - top },
    { top, left: rechts, breedte: viewport.breedte - rechts, hoogte: onder - top },
  ];
  // Een rand die niets bedekt hoeft er niet te zijn; scheelt vier lege divs in de DOM.
  return vakken.filter((v) => v.breedte > 0 && v.hoogte > 0);
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
 *  versie die nu draait – een latere uitbreiding kan zich zo opnieuw aanbieden. */
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
    /* opslag niet beschikbaar – dan start de rondleiding een volgende keer opnieuw */
  }
}
