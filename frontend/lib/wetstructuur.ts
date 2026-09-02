// Structuur herkennen in één regel wettekst, zodat de weergave kan tonen wat de wet bedoelt.
//
// `artikel._vouw_onderdelen_in` (graph-qa) bouwt het corpus op als één regel per onderdeel, in de
// vorm `"{nummer} {tekst}"`, met de lidtekst als eerste regel. Die structuur is in de brontekst dus
// alleen zichtbaar als regeleindes — en het documentpaneel toonde ze op één marge. Bij een
// definitieartikel is dat verwarrend: in art. 2 lid 1 IW 1990 hangen `1°.` t/m `4°.` onder een
// container tussen `a.` en `b.`, maar zonder inspringing lezen ze als zelfstandige onderdelen. Dat
// is een verschil in juridische strekking, niet in opmaak.
//
// HET NIVEAU IS AFGELEID, GEEN WAARHEID. De echte nesting zit in de graaf (`heeftOnderdeel+` met
// `?ouder`, sinds de volgordefix van 1 sep 2026), maar reist niet mee: `GET /v1/artikel` levert
// `leden_teksten` als `{lid, tekst}[]` en verder niets. Het niveau wordt hier dus uit de vórm van
// het nummer gelezen. Bij een regeling waar `1°.` wél op het hoogste niveau staat, springt het ten
// onrechte in. Dat is bewust geaccepteerd: een fout niveau geeft een scheve marge, nooit een scheve
// markering — de offsets komen uit `data-offset` per blok en niet uit deze functie.
//
// Deze parser bestaat twee keer: hier voor het documentpaneel, en in `api/app/wetstructuur.py` voor
// de PDF-export. `wetstructuur.vectoren.json` bewaakt dat beide kanten hetzelfde blijven doen —
// zelfde patroon als `bronHash.vectoren.json`, dat er kwam nadat Python en JS uiteenliepen.

/** Wat één regel wettekst blijkt te zijn. */
export interface Onderdeel {
  /** Het nummer zoals het in de wet staat, inclusief punt (`a.`, `1°.`, `–`); leeg als er geen is. */
  nummer: string;
  /** De gedefinieerde term vóór de dubbele punt, alleen vlak ná een nummer; anders leeg. */
  term: string;
  /** De rest van de regel, ná nummer en term. */
  tekst: string;
  /** 0 = aanhef of lopende tekst, 1 = letter-/streepje-onderdeel, 2 = genest (graden). */
  niveau: number;
}

/** Opsommingstekens die als onderdeelnummer gelden. Alleen aan het BEGIN van een regel — een
 *  en-dash komt ook midden in een zin voor als gedachtestreepje ("…opheldering niet – of niet…"),
 *  en dat is geen opsomming. */
const STREEPJES = ["–", "—", "•"];

/** `a.` `b.` `aa.` `1.` `12.` — een letter- of cijfergroep met een punt erachter. */
const NUMMER = /^([a-z]{1,3}|\d{1,3})\.(?=\s|$)/;

/** `1°.` `2°` — graden, in de BWB-conventie een niveau dieper dan de letters eromheen. */
const GRADEN = /^(\d{1,3}°)\.?(?=\s|$)/;

/** Ontleed één regel van de brontekst.
 *
 *  De regel gaat er ongeschonden weer uit: `nummer + term + tekst` bevat elk teken dat er stond, op
 *  de scheidende spaties en de dubbele punt na. Dat is geen finesse maar de eis waaronder deze
 *  functie mag bestaan — de weergave verplaatst tekst, ze verandert hem niet.
 */
export function ontleed(regel: string): Onderdeel {
  const kaal = regel.trimStart();
  const leeg: Onderdeel = { nummer: "", term: "", tekst: regel.trim(), niveau: 0 };
  if (!kaal) return { nummer: "", term: "", tekst: "", niveau: 0 };

  // 1. Graden eerst: `1°.` moet niet als het gewone `1.` worden gelezen, want dan valt het
  //    nestingniveau weg — dezelfde reden waarom `_onderdeel_nummer` in de agent de `°` laat staan.
  const graden = GRADEN.exec(kaal);
  if (graden) return _metTerm(kaal.slice(graden[0].length), graden[0], 2);

  // 2. Een streepje als opsommingsteken (Leidraad). Alleen aan het begin, en er moet iets achter
  //    staan — een losse dash is geen onderdeel.
  const streep = STREEPJES.find((s) => kaal.startsWith(s));
  if (streep && kaal.slice(streep.length).trimStart()) {
    return _metTerm(kaal.slice(streep.length), streep, 1);
  }

  // 3. Letters en cijfers met een punt. De lookahead in NUMMER eist witruimte of regeleinde erachter,
  //    zodat "a. buiten beschouwing" midden in een zin niet als onderdeel telt — die staat daar niet
  //    aan het begin, maar de eis houdt ook "art.2" en "nr.3" tegen.
  const nummer = NUMMER.exec(kaal);
  if (nummer) return _metTerm(kaal.slice(nummer[0].length), nummer[0], 1);

  return leeg;
}

/** De definitieterm afsplitsen: alleen vlak ná een nummer, en alleen als hij kort genoeg is.
 *
 *  Een dubbele punt staat ook in gewone volzinnen ("…voor de loonbelasting: ieder van de
 *  bestuurders"), dus zonder grens zou de halve bepaling vet worden. De term in een definitieartikel
 *  is een begrip van een paar woorden; alles daarboven is een zin en geen term.
 */
function _metTerm(rest: string, nummer: string, niveau: number): Onderdeel {
  const tekst = rest.trim();
  const dubbelePunt = tekst.indexOf(":");
  if (dubbelePunt > 0) {
    const kandidaat = tekst.slice(0, dubbelePunt).trim();
    if (kandidaat && kandidaat.split(/\s+/).length <= MAX_TERM_WOORDEN) {
      return { nummer, term: kandidaat, tekst: tekst.slice(dubbelePunt + 1).trim(), niveau };
    }
  }
  return { nummer, term: "", tekst, niveau };
}

/** Een gedefinieerd begrip is kort ("de BES eilanden", "belastingrente en revisierente"); een
 *  volzin die toevallig een dubbele punt bevat is dat niet. Vier woorden is de grens die de
 *  definities in art. 2 IW 1990 wél pakt en de volzinnen daaromheen niet. */
const MAX_TERM_WOORDEN = 4;

/** Eén blok in de weergave: een lid-aanhef of een onderdeel, mét zijn plek in de brontekst. */
export interface Blok extends Onderdeel {
  /** Waar de bloktekst begint in de brontekst. Draagt de positiebepaling, zie `offsetInBlok`. */
  offset: number;
  /** De regel zoals hij in de bron staat — `bron.slice(offset, offset + regel.length)`. */
  regel: string;
  /** Het lidnummer waar dit blok bij hoort, of "" bij een artikel zonder genummerde leden. */
  lid: string;
  /** Eerste blok van een lid? Dan hoort er ruimte boven en draagt het het lidnummer. */
  eersteVanLid: boolean;
  /** Posities BINNEN `regel` van het nummer en de term, voor opmaak zonder de tekst te herschrijven.
   *  `-1` als het deel er niet is. De weergave knipt hierop; zij mag de tekst niet zelf opnieuw
   *  samenstellen, want dan staat hij dubbel in de DOM en lopen de offsets mis. */
  nummerEind: number;
  termStart: number;
  termEind: number;
}

/** Deel de brontekst op in blokken, in dezelfde volgorde en met dezelfde tekst.
 *
 *  DE INVARIANT: voor elk blok geldt `bron.slice(b.offset, b.offset + b.regel.length) === b.regel`.
 *  Daar hangt de hele weergave aan — zonder dat wijst een zelfgemaakte markering naar de verkeerde
 *  tekst. `wetstructuur.test.ts` toetst hem expliciet in plaats van hem impliciet te laten volgen
 *  uit de rendering.
 *
 *  De scheiding is exact die van `bronVan` / `_leden_en_corpus`: leden aaneengeregen met `\n\n`,
 *  onderdelen daarbinnen met `\n`. Wijkt dat af, dan lopen de offsets mis — dus reken hier met de
 *  regels zoals ze binnenkomen en niet met een eigen splitsing van de hele bron.
 */
export function blokkenVan(regels: { lid: string; regel: string }[]): Blok[] {
  const blokken: Blok[] = [];
  let offset = 0;
  for (const r of regels) {
    let binnen = 0;
    const stukken = r.regel.split("\n");
    stukken.forEach((stuk, i) => {
      // Het LIDVOORVOEGSEL heeft exact dezelfde vorm als een onderdeelnummer: `regelsVan` zet
      // "1. " vóór de lidtekst, en `ontleed` ziet daar terecht een `1.` in. Alleen hier is te
      // weten dat het om het lid gaat — het is het eerste stuk van een regel waarvan het lidnummer
      // bekend is. Zonder dit onderscheid springt de aanhef van elk genummerd lid in alsof het een
      // onderdeel was, en dan verschuift de hele bepaling een niveau.
      const isLidkop = i === 0 && !!r.lid && stuk.startsWith(`${r.lid}.`);
      const ontleed_ = isLidkop
        ? { ...ontleed(stuk.slice(r.lid.length + 1)), nummer: `${r.lid}.`, niveau: 0 }
        : ontleed(stuk);
      // De posities opzoeken in plaats van optellen: `ontleed` trimt, dus de lengtes van nummer,
      // term en tekst tellen niet op tot de regel. Zoeken op de letterlijke deelstring kan wél,
      // want beide komen ongewijzigd uit deze regel.
      const nummerEind = ontleed_.nummer
        ? stuk.indexOf(ontleed_.nummer) + ontleed_.nummer.length
        : -1;
      const termStart = ontleed_.term
        ? stuk.indexOf(ontleed_.term, Math.max(nummerEind, 0))
        : -1;
      blokken.push({
        ...ontleed_,
        offset: offset + binnen,
        regel: stuk,
        lid: r.lid,
        eersteVanLid: i === 0,
        nummerEind,
        termStart,
        termEind: termStart >= 0 ? termStart + ontleed_.term.length : -1,
      });
      binnen += stuk.length + 1;   // +1 voor de "\n" die we net weggesplitst hebben
    });
    offset += r.regel.length + 2;  // +2 voor de "\n\n" tussen de leden
  }
  return blokken;
}
