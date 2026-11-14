"use client";

import { useEffect, useState } from "react";

import { knopKlasse } from "@/components/ui/Button";
import { Lijst, LijstRij, StatusLabel } from "@/components/ui/Lijst";
import { haalDelegaties, luisterNaarDelegaties } from "@/lib/api";
import {
  STAND_TEKST, delegatieSamenvatting, standToon, taakMeta, teTonen,
  type DelegatieVoortgang, type DelegatieWeergave,
} from "@/lib/delegatie";
import type { Delegatie } from "@/lib/types";

/** Wat de subagents van een beurt doen (ADR-016 §A5), of de kinderen van een regie (ADR-012): het plan, per kind de
 *  stand en een link naar zijn deelgesprek. Zolang de beurt loopt uit de stroom; daarna, en na herladen, de stand van nu
 *  bij de api (`/v1/delegaties`). Eén blok voor beide soorten: het verschil is alleen het woord in de kop. */
export function DelegatieBlok({ weergave, gesprekId, loopt, onOpenGesprek }: {
  weergave: DelegatieWeergave;
  gesprekId?: string | null;
  /** De beurt van dit bericht loopt nog: dan is de stroom de bron. */
  loopt: boolean;
  onOpenGesprek?: (id: string) => void;
}) {
  const api = useDelegatiesVan(loopt ? null : gesprekId ?? null);
  const lijst = teTonen(weergave, api, loopt);
  if (!lijst.length) return null;
  return (
    <div className="mt-3 space-y-3">
      {lijst.map((d) => <Een key={d.regie_id} d={d} onOpenGesprek={onOpenGesprek} />)}
    </div>
  );
}

function Een({ d, onOpenGesprek }: { d: DelegatieVoortgang; onOpenGesprek?: (id: string) => void }) {
  const kop = d.soort === "regie" ? "Regie" : d.hervat ? "Subagent gaat verder" : d.taken.length === 1 ? "Subagent" : "Subagents";
  return (
    <section data-delegatie={d.regie_id} data-delegatie-status={d.status} aria-live="polite"
      aria-label={`${kop}: ${delegatieSamenvatting(d)}`}
      className="rounded-kaart border border-line bg-paper px-4 py-2.5 shadow-zacht">
      <p className="text-sm font-medium text-ink">{kop}</p>
      <p className="text-xs text-muted">{delegatieSamenvatting(d)}</p>
      <Lijst label={`${kop}: de deelopdrachten`} className="mt-1">
        {d.taken.map((t, i) => (
          <LijstRij key={t.gesprek_id || i} data-delegatie-taak={t.stand}
            titel={t.titel}
            meta={taakMeta(t) || undefined}
            status={<StatusLabel toon={standToon(t.stand)}>{STAND_TEKST[t.stand]}</StatusLabel>}
            acties={t.gesprek_id && onOpenGesprek ? (
              // Een echte link (een nieuw tabblad kan), die in de werkplek zelf het deelgesprek opent.
              <a href={`/workbench?gesprek=${encodeURIComponent(t.gesprek_id)}`} data-deelgesprek-link={t.gesprek_id}
                onClick={(e) => {
                  if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
                  e.preventDefault();
                  onOpenGesprek(t.gesprek_id!);
                }}
                className={`${knopKlasse("secondary", "xs")} w-full sm:w-auto`}>
                Open het deelgesprek
              </a>
            ) : undefined}
          />
        ))}
      </Lijst>
    </section>
  );
}

/** De delegaties van een gesprek bij de api; `null` zolang ze er niet zijn (of zolang de beurt loopt). Het ophalen is
 *  gedeeld per gesprek (`haalDelegaties`), dus tien blokken in een gesprek doen één verzoek. */
function useDelegatiesVan(gesprekId: string | null): Delegatie[] | null {
  const [stand, setStand] = useState<{ id: string; lijst: Delegatie[] } | null>(null);
  const [versie, setVersie] = useState(0);
  useEffect(() => {
    if (!gesprekId) return;
    return luisterNaarDelegaties((id) => { if (!id || id === gesprekId) setVersie((v) => v + 1); });
  }, [gesprekId]);
  useEffect(() => {
    if (!gesprekId) return;
    let weg = false;
    void haalDelegaties(gesprekId).then((lijst) => { if (!weg) setStand({ id: gesprekId, lijst }); });
    return () => { weg = true; };
  }, [gesprekId, versie]);
  return gesprekId && stand?.id === gesprekId ? stand.lijst : null;
}
