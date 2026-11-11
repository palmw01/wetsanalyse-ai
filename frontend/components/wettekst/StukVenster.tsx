"use client";

import { useEffect, useMemo, useRef } from "react";

import { knopKlasse } from "@/components/ui/Button";
import { Regel, Regels, Sectie } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { StandMelding } from "@/components/ui/StandMelding";
import { ConnectorTekst, STUK_EENHEID } from "@/components/wettekst/ConnectorTekst";
import { hoortBij, stukGegevens, stukMeldingen, stukVerwijzingen, type StukPassage } from "@/lib/bronStuk";
import type { useStuk } from "@/lib/useStuk";
import type { TekstBij } from "@/lib/antwoord";
import { WETTEKST_LIVE, tekstBijMeldingen, wettekstMeldingen } from "@/lib/herkomst";

/** Het bronvenster van een stuk uit een bronconnector (ADR-013, het bronvenster PR 6), in vaste blokken onder de kop:
 *  1. de stand (een andere versie dan Lex las, een bewaarde versie, alleen een PDF);
 *  2. de inhoud: de koppen van het stuk; een klik springt ernaar (en laadt tot daar);
 *  3. de tekst, per deel (`ConnectorTekst`), met de passages die Lex citeerde gemarkeerd; *Volgende deel laden* zolang
 *     er meer is – nooit een stille afkapping;
 *  4. de gegevens uit de beschrijving van de connector (`metadata`);
 *  5. de verwijzingen uit de voetnoten: een stuk van dezelfde bron opent als eigen tab.
 *  Is de bron niet te bereiken, dan staat er wat Lex las (`voorbeeld`), met een melding. Geen graaf: die kent geen stukken. */
export function StukVenster({ stuk: { stand, fout, laadt, meer }, gelezen, voorbeeld, tekst: bij, onOpenStuk }: {
  stuk: ReturnType<typeof useStuk>;
  /** Bij welke tekst van de bepaling het stuk hoort (uit de lijst waar het geopend werd). */
  tekst?: TekstBij;
  gelezen?: { bron_hash: string; passages: number[] };
  voorbeeld?: StukPassage[];
  onOpenStuk: (v: { id: string; label: string; link: string }) => void;
}) {
  const tekst = useRef<HTMLDivElement>(null);
  const geciteerd = useMemo(() => new Set(gelezen?.passages ?? []), [gelezen]);
  const passages = stand?.passages ?? [];
  // Het venster opent bij de eerste passage die Lex citeerde.
  const eersteKeer = useRef(true);
  useEffect(() => {
    if (!passages.length || !eersteKeer.current) return;
    eersteKeer.current = false;
    tekst.current?.querySelector("[data-geciteerd]")?.scrollIntoView?.({ block: "start" });
  }, [passages.length]);

  if (fout && !stand) {
    return (
      <div className="space-y-4">
        <StandMelding meldingen={tekstBijMeldingen(bij ?? {})} />
        <Melding type="waarschuwing" compact><span data-stand-melding="bron-onbereikbaar">{fout}{voorbeeld?.length ? " Hieronder staat wat Lex las." : ""}</span></Melding>
        {!!voorbeeld?.length && <ConnectorTekst passages={voorbeeld} geciteerd={geciteerd} />}
      </div>
    );
  }
  if (!stand) return <div className="space-y-2"><Skeleton className="h-4 w-48" /><Skeleton className="h-16 w-full" /></div>;
  const { beschrijving, deel } = stand.antwoord;
  // Een wettekst buiten de graaf zegt zelf welke tekst hij is (de metadata van het gelezen stuk); een ander stuk zegt bij
  // welke tekst van de bepaling het hoort (uit de lijst waar het geopend werd).
  const meldingen = [...(beschrijving.brontype === WETTEKST_LIVE ? wettekstMeldingen({ ...bij, ...((deel.stuk ?? {}) as TekstBij & { status?: string }) })
    : tekstBijMeldingen(bij ?? {})), ...stukMeldingen(deel, gelezen)];
  const gegevens = stukGegevens(beschrijving, deel.stuk);
  const verwijzingen = stukVerwijzingen(passages);
  const naarKop = (offset: number) => {
    const doel = tekst.current?.querySelectorAll(STUK_EENHEID)[offset];
    if (doel) doel.scrollIntoView({ block: "start" });
    else meer?.();
  };
  return (
    <div className="space-y-5" data-stukvenster={String(deel.stuk?.id ?? "")}>
      <StandMelding meldingen={meldingen} />
      {!!deel.inhoud?.length && (
        <Sectie titel="Inhoud" niveau={3} data-blok="inhoud" toelichting={deel.inhoud_ingekort ? "De inhoud is ingekort: niet elke kop staat erin." : undefined}>
          <ol className="space-y-0.5 text-sm">
            {deel.inhoud.map((k) => (
              <li key={`${k.offset}:${k.kop}`}>
                <button type="button" onClick={() => naarKop(k.offset)} className="focus-ring rounded text-left text-lint hover:underline">{k.kop}</button>
              </li>
            ))}
          </ol>
        </Sectie>
      )}
      {passages.length > 0 && (
        <Sectie titel="Tekst" niveau={3} data-blok="tekst">
          <div ref={tekst}>
            <ConnectorTekst passages={passages} geciteerd={geciteerd}
              onOpen={(v) => (hoortBij(beschrijving, v.id) ? onOpenStuk(v) : window.open(v.link, "_blank", "noopener"))} />
          </div>
          {meer && (
            <button type="button" onClick={meer} disabled={laadt} data-volgende-deel className={`${knopKlasse("secondary", "sm")} w-full sm:w-auto`}>
              {laadt ? "Laden…" : "Volgende deel laden"}
            </button>
          )}
          {fout && <Melding type="fout" compact>{fout}</Melding>}
        </Sectie>
      )}
      {gegevens.length > 0 && (
        <Sectie titel="Gegevens" niveau={3} data-blok="gegevens">
          <Regels className="text-sm">{gegevens.map((g) => <Regel key={g.label} naam={g.label}>{g.waarde}</Regel>)}</Regels>
        </Sectie>
      )}
      {verwijzingen.length > 0 && (
        <Sectie titel="Verwijzingen" telling={verwijzingen.length} niveau={3} data-blok="verwijzingen">
          <ul className="space-y-0.5 text-sm">
            {verwijzingen.map((v) => (
              <li key={v.id}>
                {hoortBij(beschrijving, v.id)
                  ? <button type="button" onClick={() => onOpenStuk(v)} className="focus-ring rounded text-left text-lint hover:underline">{v.label}</button>
                  : <span>{v.label}</span>}
              </li>
            ))}
          </ul>
        </Sectie>
      )}
    </div>
  );
}
