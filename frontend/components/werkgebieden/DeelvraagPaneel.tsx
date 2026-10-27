"use client";

import { useCallback, useEffect, useState } from "react";

import { Lijst, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { DeelvraagVoorstel, KoppelDialoog } from "@/components/werkgebieden/Deelvragen";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedProject";
import { foutTekst, haalDeelvraag, haalWerkgebied } from "@/lib/api";
import { deelvraagStand } from "@/lib/bronselectie";
import { splits } from "@/lib/deelvragen";
import type { DeelvraagDetail, Werkgebied } from "@/lib/types";
import { useBronselectieStand } from "@/lib/useBronselectieStand";
import { ROL_LABEL, isRevisieConflict } from "@/lib/werkgebied";
import Link from "next/link";
import { BronBoom } from "@/components/ui/BronBoom";
import { Button } from "@/components/ui/Button";
import { bouwBoom, regelingUitLabel } from "@/lib/bronPlaats";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { bronPad } from "@/lib/werkgebiedPaden";

/** Eén deelvraag naast het gesprek (F3d): wat Lex over haar opleverde, om te beoordelen.
 *
 *  - de vraag en haar stand (dezelfde dekking als op de pagina); is ze vervangen, dan door welke;
 *  - de voorstellen van Lex die haar vervangen (een scherpere formulering of een splitsing): overnemen zet
 *    het voorstel op haar plek, met haar bronnen;
 *  - de bronnen die erbij horen (begrippen horen bij het werkgebied, spoor K);
 *  - de bepalingen die Lex bij haar vond, met opnemen, later en uitsluiten (`BronKandidaten`).
 *
 *  Geen Lex-knoppen: wat Lex moet doen vraag je in het gesprek. Elke wijziging draagt de revisie in beeld;
 *  wijzigde iemand anders het werkgebied intussen, dan komt de nieuwe stand in beeld en zegt het paneel dat. */
export function DeelvraagPaneel({ werkgebiedId, deelvraagId, onKies, onGewijzigd }: {
  werkgebiedId: string;
  deelvraagId: string;
  /** Een andere deelvraag openen (de opvolger van een vervangen deelvraag). */
  onKies?: (deelvraag: { id: string; vraag: string }) => void;
  /** Het werkgebied is gewijzigd (een voorstel overgenomen, een bron opgenomen): de pagina eromheen laadt
   *  dan ook opnieuw. */
  onGewijzigd?: () => void;
}) {
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [detail, setDetail] = useState<DeelvraagDetail | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  const [koppelen, setKoppelen] = useState(false);
  // De plek van alle bronnen van het werkgebied (één verzoek), voor de boom van deze deelvraag.
  const plaatsen = usePlaatsen(wg?.bronnen.map((b) => b.bron_iri) ?? []);

  const laad = useCallback(async () => {
    try {
      const [w, d] = await Promise.all([haalWerkgebied(werkgebiedId), haalDeelvraag(werkgebiedId, deelvraagId)]);
      setWg(w);
      setDetail(d);
      setFout(null);
    } catch (e) {
      setFout(foutTekst(e, "De deelvraag kon niet worden geladen."));
    }
  }, [werkgebiedId, deelvraagId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  const muteer: Mutatie = useCallback(async (actie, { gelukt, opFout } = {}) => {
    if (!wg) return false;
    setMelding(null);
    try {
      setWg(await actie(wg.revisie));
      setDetail(await haalDeelvraag(werkgebiedId, deelvraagId));
      onGewijzigd?.();
      if (gelukt) setMelding({ type: "bevestiging", tekst: typeof gelukt === "function" ? gelukt() : gelukt });
      return true;
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde dit werkgebied net. De nieuwste stand staat nu in beeld." });
      } else if (!opFout?.(e)) {
        setMelding({ type: "waarschuwing", tekst: foutTekst(e) });
      }
      return false;
    }
  }, [wg, werkgebiedId, deelvraagId, laad, onGewijzigd]);

  const actief = splits(wg?.deelvragen).actief;
  const selectie = useBronselectieStand(werkgebiedId, wg?.revisie ?? 0, actief.length);

  if (fout) {
    return (
      <Melding type="fout" titel="De deelvraag kon niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => void laad()}>
          Opnieuw proberen
        </button>
      </Melding>
    );
  }
  if (!wg || !detail) return <SkeletonCard regels={4} />;

  const nummer = actief.findIndex((d) => d.id === detail.id) + 1;
  const hier = selectie?.deelvragen.find((d) => d.id === detail.id);
  const stand = deelvraagStand(hier);
  const bronnen = wg.bronnen.filter((b) => detail.bronnen.includes(b.id));
  const boom = bouwBoom(bronnen, { iri: (b) => b.bron_iri, naam: (b) => b.label || b.bron_iri, plaatsen,
    regelingNaam: (b) => regelingUitLabel(b.label) });

  return (
    <div data-deelvraag-paneel={detail.id} data-status={detail.status} className="space-y-5 text-sm text-ink">
      <div className="space-y-1.5">
        <p className="text-xs text-muted">
          {nummer ? `Deelvraag ${nummer} van ${actief.length}` : detail.status === "voorgesteld" ? "Voorstel van Lex" : "Deelvraag"}
          {" · "}{detail.herkomst === "lex" ? "voorgesteld door Lex" : `door ${detail.aangemaakt_door}`}
        </p>
        <p className="font-medium" data-deelvraag-vraag>{detail.vraag}</p>
        {stand && <StatusLabel toon={stand.toon} data-stand={hier?.status}>{stand.label}</StatusLabel>}
      </div>

      {melding && <Melding type={melding.type} compact>{melding.tekst}</Melding>}

      {detail.status === "vervangen" && (
        <Melding type="uitleg" compact>
          Deze deelvraag is vervangen
          {detail.opvolgers.length > 0 && <> door{" "}
            {detail.opvolgers.map((o, i) => (
              <span key={o.id}>
                {i > 0 && (i === detail.opvolgers.length - 1 ? " en " : ", ")}
                {onKies ? (
                  <button type="button" className="focus-ring rounded font-medium text-lint underline" data-opvolger={o.id}
                    onClick={() => onKies(o)}>“{o.vraag}”</button>
                ) : <>“{o.vraag}”</>}
              </span>
            ))}
          </>}.
        </Melding>
      )}
      {detail.status === "afgewezen" && (
        <Melding type="uitleg" compact>Dit voorstel is afgewezen{detail.reden ? `: ${detail.reden}` : "."}</Melding>
      )}

      {detail.voorstellen.length > 0 && (
        <Sectie titel="Voorstellen van Lex" telling={detail.voorstellen.length} niveau={3}
          toelichting="Overnemen vervangt deze deelvraag: het voorstel neemt haar plek en haar bronnen over.">
          <Lijst label="Voorstellen van Lex">
            {detail.voorstellen.map((v) => (
              <DeelvraagVoorstel key={v.id} wgId={werkgebiedId} deelvraag={v} alle={[...(wg.deelvragen ?? []), detail]} muteer={muteer} />
            ))}
          </Lijst>
        </Sectie>
      )}

      {/* De bronnen als boom per regeling › hoofdstuk › artikel › lid (spoor H3); koppelen in een venster. */}
      <Sectie titel="Bronnen" telling={bronnen.length} niveau={3}
        acties={detail.status === "actief" && (
          <Button size="sm" variant="secondary" onClick={() => setKoppelen(true)}
            aria-label={`Bronnen bij: ${detail.vraag}`}>Koppelen</Button>
        )}>
        {bronnen.length ? (
          <BronBoom boom={boom} label="Bronnen bij deze deelvraag"
            bladAttrs={(b) => ({ "data-bron": b.data.id })}
            renderBlad={(b) => (
              <span className="flex flex-wrap items-center gap-x-2 text-sm">
                <Link href={bronPad(b.bron_iri, werkgebiedId)} className="focus-ring rounded text-lint hover:underline">{b.label}</Link>
                <span className="text-xs text-muted">{ROL_LABEL[b.data.rol]}</span>
              </span>
            )} />
        ) : <p className="text-muted">Er hoort nog geen bron bij deze deelvraag.</p>}
      </Sectie>
      {koppelen && <KoppelDialoog wg={wg} deelvraag={detail} muteer={muteer} onKlaar={() => setKoppelen(false)} />}

      {detail.status === "actief" && (
        <BronKandidaten id={werkgebiedId} deelvraagId={detail.id} onGewijzigd={() => { void laad(); onGewijzigd?.(); }} />
      )}
    </div>
  );
}
