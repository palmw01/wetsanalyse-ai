"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Lijst, LijstRij, Sectie } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import {
  besluitKandidaat, foutTekst, haalKandidaten, haalLaatsteBronnenRun, neemKandidaatOp,
} from "@/lib/api";
import {
  FILTER_LABEL, KANDIDAAT_ROL_LABEL, KANDIDAAT_ROL_UITLEG, METHODE_LABEL, bewijsZin, bijDeelvraag, filterVan, plekNaam,
  sorteerKandidaten,
  standaardRol, telPerFilter, type KandidaatFilter,
} from "@/lib/bronKandidaten";
import type { BronKandidaat, BronMethode, BronRol, BronnenRun, KandidatenAntwoord } from "@/lib/types";
import { ROL_LABEL, annotatieHref } from "@/lib/werkgebied";

const KNOP =
  "focus-ring inline-flex min-h-[24px] items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50 coarse:min-h-[44px]";
const ROL_STIJL: Record<BronKandidaat["rol"], string> = {
  kern: "border-lint/40 bg-lint/10 text-lint",
  afhankelijkheid: "border-line bg-surface text-ink",
  aanverwant: "border-line bg-paper text-muted",
};
const FILTERS: KandidaatFilter[] = ["open", "later", "uitgesloten", "opgenomen"];

/** De bepalingen die Lex voor een werkgebied vond (spoor D, fase A), als reviewlijst.
 *
 *  Eén inhoud, twee schillen: bovenaan de tab Bronnen en als artefact naast het gesprek. Lex zoekt met
 *  vaste graafqueries (geen model); per kandidaat staat zijn rol en het bewijs per methode. De analist
 *  beslist: opnemen (als analyseren of context), later, of uitsluiten met een reden – een uitgesloten
 *  kandidaat stelt Lex niet opnieuw voor.
 *
 *  Toetsenbord, alleen met de focus in de lijst: `j`/`k` door de kandidaten, `a` opnemen met de
 *  voorgestelde rol, `x` uitsluiten (de reden krijgt de focus).
 *
 *  Zoeken vraag je Lex in het gesprek (*Zoek bepalingen bij alle deelvragen*, of *Zoek bepalingen hierbij*
 *  op een deelvraag, F3e); hier staat wat hij vond. Met `deelvraagId` (het deelvraagpaneel, F3d) alleen
 *  wat Lex bij die deelvraag vond. */
export function BronKandidaten({ id, deelvraagId, labels, onGewijzigd }: {
  id: string;
  deelvraagId?: string;
  /** bron-IRI → naam, voor het bewijs ("verwezen vanuit …"); de selecties van het werkgebied. */
  labels?: Map<string, string>;
  /** De selectie van het werkgebied is veranderd (opnemen maakt een bronselectie). */
  onGewijzigd: () => void;
}) {
  const [data, setData] = useState<KandidatenAntwoord | null>(null);
  const [laatste, setLaatste] = useState<BronnenRun | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [filter, setFilter] = useState<KandidaatFilter>("open");
  const [actief, setActief] = useState(0);
  const [uitsluiten, setUitsluiten] = useState<string | null>(null);   // kandidaat-id met open redenveld
  const [bezig, setBezig] = useState<string | null>(null);
  const lijstRef = useRef<HTMLUListElement & HTMLOListElement>(null);

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

  async function besluit(k: BronKandidaat, actie: () => Promise<unknown>, gelukt: string) {
    setFout(null);
    setMelding(null);
    setBezig(k.id);
    try {
      await actie();
      setUitsluiten(null);
      await laad();
      setMelding(gelukt);
      return true;
    } catch (e) {
      setFout(foutTekst(e));
      return false;
    } finally {
      setBezig(null);
    }
  }

  const opnemen = (k: BronKandidaat, rol: BronRol) => besluit(k, async () => {
    await neemKandidaatOp(id, k.id, rol);
    onGewijzigd();
  }, `${k.label || k.bron_iri} opgenomen als ${ROL_LABEL[rol].toLowerCase()}.`);

  const alle = useMemo(() => sorteerKandidaten((data?.kandidaten ?? [])
    .filter((k) => !deelvraagId || bijDeelvraag(k, deelvraagId))), [data, deelvraagId]);
  const telling = useMemo(() => telPerFilter(alle), [alle]);
  const getoond = useMemo(() => alle.filter((k) => filterVan(k) === filter), [alle, filter]);
  const run = laatste ?? data?.run ?? null;
  const huidig = getoond[Math.min(actief, Math.max(0, getoond.length - 1))];

  function opToets(e: React.KeyboardEvent) {
    const doel = e.target as HTMLElement;
    if (doel.closest("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setActief((i) => Math.min(i + 1, getoond.length - 1)); }
    else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setActief((i) => Math.max(i - 1, 0)); }
    else if (e.key === "a" && huidig && filterVan(huidig) !== "opgenomen") { e.preventDefault(); void opnemen(huidig, standaardRol(huidig)); }
    else if (e.key === "x" && huidig && filterVan(huidig) !== "opgenomen" && huidig.status !== "uitgesloten") {
      e.preventDefault();
      setUitsluiten(huidig.id);
    }
  }

  useEffect(() => {
    lijstRef.current?.querySelector<HTMLElement>(`[data-index="${actief}"]`)?.scrollIntoView({ block: "nearest" });
  }, [actief]);

  return (
    <Sectie data-bronkandidaten titel={deelvraagId ? "Bepalingen die Lex hierbij vond" : "Bepalingen gevonden door Lex"}
      toelichting={deelvraagId ? undefined : run?.status === "klaar"
        ? `Gezocht vanuit ${run.aantal_kern} ${run.aantal_kern === 1 ? "bepaling" : "bepalingen"}${run.verouderd ? " – de selectie is sindsdien veranderd" : ""}.`
        : "Vraag Lex in het gesprek om bepalingen te zoeken; hij zoekt vanuit de bepalingen die je analyseert en de analysevraag, zonder model."}>
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {melding && <Melding type="uitleg" compact>{melding}</Melding>}

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
              onClick={() => { setFilter(f); setActief(0); }}
              className={`${KNOP} ${filter === f ? "border-lint bg-lint text-white" : "border-line text-ink hover:bg-surface"}`}>
              {FILTER_LABEL[f]} ({telling[f]})
            </button>
          ))}
        </div>
      )}

      {data && alle.length === 0 && (
        <p className="text-sm text-muted">
          {deelvraagId ? "Lex vond bij deze deelvraag nog geen bepalingen." : "Nog niets gevonden. Vraag Lex in het gesprek om bepalingen te zoeken."}
        </p>
      )}
      {alle.length > 0 && getoond.length === 0 && <p className="text-sm text-muted">Geen kandidaten in dit filter.</p>}

      {getoond.length > 0 && (
        <Lijst ref={lijstRef} label={`Kandidaten – ${FILTER_LABEL[filter].toLowerCase()}`}
          tabIndex={0} onKeyDown={opToets} className="focus-ring rounded-lg">
          {getoond.map((k, i) => (
            <KandidaatKaart key={k.id} werkgebiedId={id} k={k} index={i} actief={i === actief} labels={labels} bezig={bezig === k.id}
              uitsluitenOpen={uitsluiten === k.id}
              onKies={() => setActief(i)}
              onOpnemen={(rol) => void opnemen(k, rol)}
              onLater={() => void besluit(k, () => besluitKandidaat(id, k.id, "later"), "Voor later bewaard.")}
              onHeropenen={() => void besluit(k, () => besluitKandidaat(id, k.id, "heropenen"), "Weer een open voorstel.")}
              onUitsluitenOpen={(open) => setUitsluiten(open ? k.id : null)}
              onUitsluiten={(reden) => besluit(k, () => besluitKandidaat(id, k.id, "uitsluiten", reden),
                "Uitgesloten; Lex stelt deze bepaling niet opnieuw voor.")} />
          ))}
        </Lijst>
      )}
    </Sectie>
  );
}

function KandidaatKaart({ werkgebiedId, k, index, actief, labels, bezig, uitsluitenOpen, onKies, onOpnemen, onLater, onHeropenen,
  onUitsluitenOpen, onUitsluiten }: {
  werkgebiedId: string; k: BronKandidaat; index: number; actief: boolean; labels?: Map<string, string>; bezig: boolean; uitsluitenOpen: boolean;
  onKies: () => void; onOpnemen: (rol: BronRol) => void; onLater: () => void; onHeropenen: () => void;
  onUitsluitenOpen: (open: boolean) => void; onUitsluiten: (reden: string) => Promise<boolean>;
}) {
  const [reden, setReden] = useState("");
  const redenRef = useRef<HTMLInputElement>(null);
  const f = filterVan(k);
  const naam = k.label || plekNaam(k.bron_iri);
  const voorkeur = standaardRol(k);
  const ander: BronRol = voorkeur === "analyseren" ? "context" : "analyseren";

  useEffect(() => {
    if (uitsluitenOpen) redenRef.current?.focus();
  }, [uitsluitenOpen]);

  return (
    <LijstRij data-index={index} data-kandidaat={k.bron_iri} onClick={onKies} actief={actief}
      titel={
        <Link href={annotatieHref(k.bron_iri)} className="focus-ring rounded font-medium text-lint hover:underline">
          {naam}
        </Link>
      }
      status={
        <span title={KANDIDAAT_ROL_UITLEG[k.rol]}
          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${ROL_STIJL[k.rol]}`}>
          {KANDIDAAT_ROL_LABEL[k.rol]}
        </span>
      }
      meta={
        <>
          <ul className="space-y-0.5" aria-label={`Bewijs voor ${naam}`}>
            {k.bewijs.map((b, i) => <li key={i}>· {bewijsZin(b, labels)}</li>)}
          </ul>
          {k.status === "uitgesloten" && k.reden && (
            <p className="mt-1 text-ink">Uitgesloten{k.besloten_door ? ` door ${k.besloten_door}` : ""}: {k.reden}</p>
          )}
          {!k.in_laatste_run && f === "open" && (
            <p className="mt-1 text-aandacht-geel-tekst">Niet meer gevonden bij de laatste zoekopdracht.</p>
          )}
        </>
      }
      acties={f !== "opgenomen" && (
        <div className="flex flex-wrap gap-1.5">
          {(f === "open" || f === "later") && (
            <>
              <button type="button" disabled={bezig} className={`${KNOP} border-lint bg-lint text-white hover:bg-lint/90`}
                aria-label={`Opnemen als ${ROL_LABEL[voorkeur].toLowerCase()}: ${naam}`} onClick={() => onOpnemen(voorkeur)}>
                Opnemen als {ROL_LABEL[voorkeur].toLowerCase()}
              </button>
              <button type="button" disabled={bezig} className={`${KNOP} border-line text-lint hover:bg-surface`}
                aria-label={`Opnemen als ${ROL_LABEL[ander].toLowerCase()}: ${naam}`} onClick={() => onOpnemen(ander)}>
                als {ROL_LABEL[ander].toLowerCase()}
              </button>
            </>
          )}
          {f === "open" && (
            <button type="button" disabled={bezig} className={`${KNOP} border-line text-ink hover:bg-surface`}
              aria-label={`Later: ${naam}`} onClick={onLater}>Later</button>
          )}
          {(f === "open" || f === "later") && (
            <button type="button" disabled={bezig} className={`${KNOP} border-line text-ink hover:bg-surface`}
              aria-label={`Uitsluiten: ${naam}`} aria-expanded={uitsluitenOpen} onClick={() => onUitsluitenOpen(!uitsluitenOpen)}>
              Uitsluiten
            </button>
          )}
          {(f === "later" || f === "uitgesloten") && (
            <button type="button" disabled={bezig} className={`${KNOP} border-line text-ink hover:bg-surface`}
              aria-label={`Heropenen: ${naam}`} onClick={onHeropenen}>Heropenen</button>
          )}
          <VraagLexKnop onderwerp={{ soort: "kandidaat", werkgebied_id: werkgebiedId, id: k.id, label: naam }} />
        </div>
      )}>
      {uitsluitenOpen && (
        <form className="mt-2 flex flex-col gap-2 sm:flex-row" onClick={(e) => e.stopPropagation()}
          onSubmit={(e) => { e.preventDefault(); if (reden.trim()) void onUitsluiten(reden.trim()).then((ok) => ok && setReden("")); }}>
          <label className="sr-only" htmlFor={`reden-${k.id}`}>Reden om {naam} uit te sluiten</label>
          <Input id={`reden-${k.id}`} ref={redenRef} value={reden} onChange={(e) => setReden(e.target.value)}
            placeholder="Waarom hoort deze bepaling er niet bij?" maxLength={2000}
            onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onUitsluitenOpen(false); } }} />
          <Button type="submit" size="sm" disabled={bezig || !reden.trim()} className="w-full sm:w-auto">Uitsluiten</Button>
        </form>
      )}
    </LijstRij>
  );
}
