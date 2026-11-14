// De bewaarde berichten van een gesprek als items van de thread.
//
// Dit stond in `WerkplekClient.hydrateer`. Het staat hier omdat vitest node-env draait zonder DOM: alleen een pure
// functie is te toetsen, en dit is precies de plek waar een herladen gesprek er anders uit kan gaan zien dan live.
// Het laden zelf, de pogingteller en het weer aanhaken blijven in het component.

import { weergaveUitBericht } from "./delegatie";
import { parseGrounding, parseHergebruik, parseOverzicht, parseUitkomst, metingUitDekking } from "./agentEvents";
import { parseAntwoord } from "./antwoord";
import { annotatieDoelVan, artefactVanBericht } from "./artefact";
import { reeksUitBerichten } from "./reeks";
import type { ThreadItem } from "./threadItem";
import type { Bericht } from "./types";
import { parseAntwoordOp, parseVraagkaart } from "./vraagkaart";
import { parseBevestiging, parseBevestigingKeuze } from "./werkgebiedAnnoteren";

export interface Geschiedenis {
  items: ThreadItem[];
  /** De run-ids in de geschiedenis. Een reeks bewaart per onderdeel een bericht met run_id `<run>.<n>`; het run-id
   *  van de reeks zelf staat in `reeks.run_id`. Zonder dat telde een afgeronde reeks als verdwenen
   *  (`standVanVorigeRun`). */
  runIds: string[];
}

export function itemsUitGesprek(berichten: Bericht[], uid: () => string): Geschiedenis {
  // De berichten van één reeks (zelfde `reeks.run_id`) worden weer één reeksblok.
  const reeksen = new Map<string, Bericht[]>();
  for (const b of berichten) if (b.reeks) reeksen.set(b.reeks.run_id, [...(reeksen.get(b.reeks.run_id) ?? []), b]);
  const items = berichten.flatMap((b): ThreadItem[] => {
    if (b.reeks) {
      const groep = reeksen.get(b.reeks.run_id) ?? [];
      const reeks = groep[0] === b ? reeksUitBerichten(groep) : null;
      return reeks ? [{ id: uid(), type: "reeks", reeks }] : [];
    }
    // Het artefact van de beurt; een ouder bericht met alleen een bronnode wordt er een.
    const art = b.rol === "user" ? undefined : artefactVanBericht(b);
    const annotatieDoel = annotatieDoelVan(art);
    // De bronselectie (spoor J) draagt naast haar artefact een kaartje: dat blijft een antwoord, anders
    // is de open vraag na herladen weg. Het paneel opent de werkplek zelf (`toonVastgelegdeBeurt`). Zonder
    // kaartje (een oud bericht *Gevonden bepalingen*, nu een bronselectie) blijft het gewoon een chip.
    if (art && !annotatieDoel && (art.soort !== "bronselectie" || !b.vraagkaart)) {
      const delegatie = weergaveUitBericht(b.delegaties);
      const bevestiging = parseBevestiging(b.bevestiging);
      return [{ id: uid(), type: "artefact" as const, artefact: art, tekst: b.tekst?.trim() || undefined, denk: b.denk,
        ...(delegatie ? { delegatie } : {}), ...(bevestiging ? { bevestiging } : {}) }];
    }
    return [b.rol === "user"
      ? { id: uid(), type: "user" as const, tekst: b.tekst, antwoordOp: parseAntwoordOp(b.intake_antwoord),
          bevestigingKeuze: parseBevestigingKeuze(b.bevestiging_antwoord),
          ...(b.doorgegeven === "opdracht" || b.doorgegeven === "antwoorden" ? { doorgegeven: b.doorgegeven } : {}) }
      : annotatieDoel
        ? { id: uid(), type: "annotatie" as const, slug: annotatieDoel.bron_iri,
            titel: art?.titel || b.annotatie_titel || undefined, annotatie_doel: annotatieDoel,
            denk: b.denk,
            // De samenvatting van Lex (hoogstens vier zinnen), zoals graph-qa hem bewaarde.
            tekst: b.tekst?.trim() || undefined,
            // Na herladen moet nog te zien zijn dat er niets opnieuw is bekeken.
            hergebruik: b.hergebruik ? parseHergebruik(b.hergebruik) : undefined,
            meting: metingUitDekking(b.dekking) }
        : { id: uid(), type: "antwoord" as const, tekst: b.tekst, denk: b.denk, bronnen: b.bronnen,
            // Het overzicht zoals graph-qa het opbouwde: na herladen hetzelfde blok en dezelfde graafdoelen.
            overzicht: b.overzicht ? parseOverzicht(b.overzicht) : undefined,
            antwoord: parseAntwoord(b.antwoord),
            bevestiging: parseBevestiging(b.bevestiging),
            // Het kaartje van het samenstellen: na herladen nog te beantwoorden als het het laatste is.
            vraagkaart: parseVraagkaart(b.vraagkaart),
            uitkomst: parseUitkomst(b.uitkomst),
            // De subagents of de regie van deze beurt: hun stand van nu haalt het blok bij de api.
            ...(weergaveUitBericht(b.delegaties) ? { delegatie: weergaveUitBericht(b.delegaties) } : {}),
            // Het oordeel en de aanwijzing in de tekst blijven zo na herladen staan.
            grounding: parseGrounding(b.grounding) }];
  });
  return {
    items,
    runIds: berichten.flatMap((b) => [b.run_id, b.reeks?.run_id ?? ""]).filter(Boolean),
  };
}
