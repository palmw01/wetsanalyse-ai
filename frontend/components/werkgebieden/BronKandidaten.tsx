"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BronBoom } from "@/components/ui/BronBoom";
import { KNOP_XS } from "@/components/ui/Button";
import { Sectie } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { foutTekst, haalKandidaten, haalLaatsteBronnenRun } from "@/lib/api";
import {
  FILTER_LABEL, KANDIDAAT_ROL_LABEL, KANDIDAAT_ROL_UITLEG, METHODE_LABEL, bewijsSamenvatting, bewijsZin, bijDeelvraag, filterVan, plekNaam,
  sorteerKandidaten, telPerFilter, type KandidaatFilter,
} from "@/lib/bronKandidaten";
import type { BronKandidaat, BronMethode, BronnenRun, KandidatenAntwoord } from "@/lib/types";
import { bouwBoom, regelingUitLabel } from "@/lib/bronPlaats";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { bronPad } from "@/lib/werkgebiedPaden";

const KNOP = KNOP_XS;
const ROL_STIJL: Record<BronKandidaat["rol"], string> = {
  kern: "border-lint/40 bg-lint/10 text-lint",
  afhankelijkheid: "border-line bg-surface text-ink",
  aanverwant: "border-line bg-paper text-muted",
};
const FILTERS: KandidaatFilter[] = ["open", "uitgesloten", "opgenomen"];

/** De bronverkenner: alle bepalingen die Lex voor een werkgebied vond (spoor D, fase A), om rond te kijken.
 *
 *  Sinds spoor J beslis je hier niets: kiezen gaat per deelvraag, in de bronselectie (in het gesprek, of op de
 *  pagina Bronselectie). De boom toont per regeling › hoofdstuk › artikel › lid (`BronBoom`, de plek uit
 *  `usePlaatsen`) de rol en één zin bewijs (`bewijsSamenvatting`); een klik op een regel toont het hele bewijs.
 *  Een oud besluit *later* telt als voorstel. Met `deelvraagId` (het deelvraagpaneel) alleen wat Lex bij die
 *  deelvraag vond. */
export function BronKandidaten({ id, deelvraagId, labels }: {
  id: string;
  deelvraagId?: string;
  /** bron-IRI → naam, voor het bewijs ("verwezen vanuit …"); de selecties van het werkgebied. */
  labels?: Map<string, string>;
  /** Niet meer gebruikt: de verkenner wijzigt niets. Blijft staan voor aanroepers van vóór spoor J. */
  onGewijzigd?: () => void;
}) {
  const [data, setData] = useState<KandidatenAntwoord | null>(null);
  const [laatste, setLaatste] = useState<BronnenRun | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [filter, setFilter] = useState<KandidaatFilter>("open");
  // Welke regel haar hele bewijs toont (hoogstens één); geen regel standaard.
  const [open, setOpen] = useState<string | null>(null);

  const laad = useCallback(async () => {
    try {
      const [d, l] = await Promise.all([haalKandidaten(id), haalLaatsteBronnenRun(id)]);
      setData(d);
      setLaatste(l);
    } catch (e) {
      setFout(foutTekst(e, "De gevonden bepalingen konden niet worden geladen."));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  const alle = useMemo(() => sorteerKandidaten((data?.kandidaten ?? [])
    .filter((k) => !deelvraagId || bijDeelvraag(k, deelvraagId))), [data, deelvraagId]);
  const plaatsen = usePlaatsen(alle.map((k) => k.bron_iri));
  const telling = useMemo(() => telPerFilter(alle), [alle]);
  const getoond = useMemo(() => alle.filter((k) => filterVan(k) === filter), [alle, filter]);
  const boom = useMemo(() => bouwBoom(getoond, {
    iri: (k) => k.bron_iri, naam: (k) => k.label || plekNaam(k.bron_iri), plaatsen,
    regelingNaam: (k) => regelingUitLabel(k.label),
  }), [getoond, plaatsen]);
  const run = laatste ?? data?.run ?? null;

  return (
    <Sectie data-bronkandidaten titel={deelvraagId ? "Bepalingen die Lex hierbij vond" : "Bepalingen gevonden door Lex"}
      toelichting={deelvraagId ? undefined : run?.status === "klaar"
        ? `Gezocht vanuit ${run.aantal_kern} ${run.aantal_kern === 1 ? "bepaling" : "bepalingen"}${run.verouderd ? " – de selectie is sindsdien veranderd" : ""}. Kiezen doe je per deelvraag, in de bronselectie.`
        : "Lex zoekt in de bronselectie, per deelvraag (Bepaal de bronnen per deelvraag); hier kijk je rond in wat hij vond."}>
      {fout && <Melding type="fout" compact>{fout}</Melding>}

      {!deelvraagId && run?.status === "klaar" && run.meting && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Per methode">
          {(Object.entries(run.meting) as [BronMethode, { aantal: number; volledig: boolean }][]).map(([m, x]) => (
            <li key={m}>
              {METHODE_LABEL[m]}: {x.aantal}
              {!x.volledig && <span className="text-aandacht-geel-tekst"> (onvolledig)</span>}
            </li>
          ))}
        </ul>
      )}

      {alle.length > 0 && (
        <div role="tablist" aria-label="Filter" className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button key={f} type="button" role="tab" aria-selected={filter === f}
              onClick={() => { setFilter(f); setOpen(null); }}
              className={`${KNOP} ${filter === f ? "border-lint bg-lint text-white" : "border-line text-ink hover:bg-surface"}`}>
              {FILTER_LABEL[f]} ({telling[f]})
            </button>
          ))}
        </div>
      )}

      {data && alle.length === 0 && (
        <p className="text-sm text-muted">
          {deelvraagId ? "Lex vond bij deze deelvraag nog geen bepalingen." : "Nog niets gevonden. Bepaal de bronnen per deelvraag met Lex in het gesprek."}
        </p>
      )}
      {alle.length > 0 && getoond.length === 0 && <p className="text-sm text-muted">Geen bepalingen in dit filter.</p>}

      {getoond.length > 0 && (
        <div role="group" aria-label={`Bepalingen – ${FILTER_LABEL[filter].toLowerCase()}`}>
          <BronBoom boom={boom} label={`Bepalingen per regeling – ${FILTER_LABEL[filter].toLowerCase()}`}
            bladAttrs={(b) => ({ "data-kandidaat": b.bron_iri })}
            renderBlad={(b) => (
              <KandidaatRegel werkgebiedId={id} k={b.data} plek={b.label} labels={labels}
                open={open === b.bron_iri} onWissel={() => setOpen((o) => (o === b.bron_iri ? null : b.bron_iri))} />
            )} />
        </div>
      )}
    </Sectie>
  );
}

/** Eén kandidaat in de boom: de plek onder het artikel (een link naar de bepaling), de rol, en één zin
 *  bewijs; *Bewijs* klapt het hele bewijs uit. Geen besluitknoppen: kiezen gaat per deelvraag (spoor J). */
function KandidaatRegel({ werkgebiedId, k, plek, labels, open, onWissel }: {
  werkgebiedId: string; k: BronKandidaat; plek: string; labels?: Map<string, string>; open: boolean; onWissel: () => void;
}) {
  const naam = k.label || plekNaam(k.bron_iri);
  return (
    <div className={`rounded-md px-2 py-1.5 ${open ? "bg-lint/[0.06] ring-1 ring-lint/20" : ""}`}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <Link href={bronPad(k.bron_iri, werkgebiedId)} title={naam}
          className="focus-ring rounded text-sm font-medium text-lint hover:underline">{plek}</Link>
        <span title={KANDIDAAT_ROL_UITLEG[k.rol]}
          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${ROL_STIJL[k.rol]}`}>
          {KANDIDAAT_ROL_LABEL[k.rol]}
        </span>
        {!k.in_laatste_run && filterVan(k) === "open" && (
          <span className="text-xs text-aandacht-geel-tekst">niet meer gevonden bij de laatste zoekopdracht</span>
        )}
      </div>
      <button type="button" onClick={onWissel} aria-expanded={open} aria-label={`Bewijs voor ${naam}`}
        className="focus-ring mt-0.5 block w-full rounded text-left text-xs text-muted hover:text-ink">
        {open ? "Bewijs verbergen" : <span className="block truncate">{bewijsSamenvatting(k.bewijs, labels)}</span>}
      </button>
      {open && (
        <ul className="mt-1 space-y-0.5 text-xs text-muted" aria-label={`Bewijs: ${naam}`}>
          {k.bewijs.map((b, i) => <li key={i}>· {bewijsZin(b, labels)}</li>)}
        </ul>
      )}
      {k.status === "uitgesloten" && k.reden && (
        <p className="mt-1 text-xs text-ink">Uitgesloten{k.besloten_door ? ` door ${k.besloten_door}` : ""}: {k.reden}</p>
      )}
    </div>
  );
}
