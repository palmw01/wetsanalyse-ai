"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BronBoom } from "@/components/ui/BronBoom";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Sectie } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import {
  besluitKandidaat, foutTekst, haalKandidaten, haalLaatsteBronnenRun, neemKandidaatOp,
} from "@/lib/api";
import {
  FILTER_LABEL, KANDIDAAT_ROL_LABEL, KANDIDAAT_ROL_UITLEG, METHODE_LABEL, bewijsSamenvatting, bewijsZin, bijDeelvraag, filterVan, plekNaam,
  sorteerKandidaten,
  standaardRol, telPerFilter, type KandidaatFilter,
} from "@/lib/bronKandidaten";
import type { BronKandidaat, BronMethode, BronRol, BronnenRun, KandidatenAntwoord } from "@/lib/types";
import { bladerenVan, bouwBoom, regelingUitLabel } from "@/lib/bronPlaats";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { ROL_LABEL } from "@/lib/werkgebied";
import { bronPad } from "@/lib/werkgebiedPaden";

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
 *  Spoor H: de kandidaten staan als boom per regeling › hoofdstuk › artikel › lid (`BronBoom`, de plek uit
 *  `usePlaatsen`), per regel één zin bewijs (`bewijsSamenvatting`; de gekozen regel toont alles). Geen knoppen
 *  per regel: je vinkt aan – een regel, of een heel artikel, hoofdstuk of regeling – en besluit in de
 *  actiebalk voor alles wat gekozen is. Elk besluit is een eigen verzoek, in volgorde. Een klik op een regel
 *  toont het hele bewijs; geen sneltoetsen (besluit gebruiker 26 okt 2026).
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
  // Welke regel haar hele bewijs toont (hoogstens één); geen regel standaard.
  const [open, setOpen] = useState<string | null>(null);
  const [gekozen, setGekozen] = useState<ReadonlySet<string>>(new Set());
  const [uitsluiten, setUitsluiten] = useState(false);
  const [bezig, setBezig] = useState<{ klaar: number; totaal: number } | null>(null);

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
  // De volgorde van de boom: die volgen de besluiten in de actiebalk.
  const volgorde = useMemo(() => boom.flatMap(bladerenVan).map((b) => b.data), [boom]);
  const run = laatste ?? data?.run ?? null;
  const doelen = volgorde.filter((k) => gekozen.has(k.bron_iri));
  const beslisbaar = filter !== "opgenomen";

  /** Eén besluit voor elke gekozen kandidaat, in volgorde; bij een fout stopt het en zegt het hoe ver. */
  async function voorAlle(lijst: BronKandidaat[], actie: (k: BronKandidaat) => Promise<unknown>, gelukt: (n: number) => string,
    wijzigtSelectie = false) {
    if (!lijst.length || bezig) return;
    setFout(null);
    setMelding(null);
    setBezig({ klaar: 0, totaal: lijst.length });
    let klaar = 0;
    try {
      for (const k of lijst) {
        await actie(k);
        klaar += 1;
        setBezig({ klaar, totaal: lijst.length });
      }
      setMelding(gelukt(klaar));
      setGekozen(new Set());
      setUitsluiten(false);
    } catch (e) {
      setFout(`${klaar ? `${klaar} van ${lijst.length} verwerkt; daarna ging het mis: ` : ""}${foutTekst(e)}`);
    } finally {
      setBezig(null);
      if (wijzigtSelectie && klaar) onGewijzigd();
      await laad();
    }
  }

  // Zonder gekozen rol neemt elke bepaling haar voorgestelde rol; de melding noemt die als ze voor alle gelijk is.
  const opnemen = (lijst: BronKandidaat[], rol?: BronRol) => {
    const rollen = new Set(lijst.map((k) => rol ?? standaardRol(k)));
    const als = rollen.size === 1 ? ` als ${ROL_LABEL[[...rollen][0]].toLowerCase()}` : "";
    return voorAlle(lijst, (k) => neemKandidaatOp(id, k.id, rol ?? standaardRol(k)),
      (n) => `${n} ${n === 1 ? "bepaling" : "bepalingen"} opgenomen${als}.`, true);
  };
  const later = (lijst: BronKandidaat[]) => voorAlle(lijst, (k) => besluitKandidaat(id, k.id, "later"),
    (n) => `${n} voor later bewaard.`);
  const heropenen = (lijst: BronKandidaat[]) => voorAlle(lijst, (k) => besluitKandidaat(id, k.id, "heropenen"),
    (n) => `${n} weer een open voorstel.`);
  const sluitUit = (lijst: BronKandidaat[], reden: string) => voorAlle(lijst, (k) => besluitKandidaat(id, k.id, "uitsluiten", reden),
    (n) => `${n} uitgesloten; Lex stelt ${n === 1 ? "deze bepaling" : "ze"} niet opnieuw voor.`);

  function zet(iris: string[], aan: boolean) {
    setGekozen((g) => {
      const n = new Set(g);
      for (const i of iris) if (aan) n.add(i); else n.delete(i);
      return n;
    });
  }

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
              onClick={() => { setFilter(f); setOpen(null); setGekozen(new Set()); setUitsluiten(false); }}
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
        <div role="group" aria-label={`Kandidaten – ${FILTER_LABEL[filter].toLowerCase()}`}>
          <BronBoom boom={boom} label={`Kandidaten per regeling – ${FILTER_LABEL[filter].toLowerCase()}`}
            vinkjes={beslisbaar ? { gekozen, onZet: zet, naam: (b) => `Kies ${b.data.label || plekNaam(b.bron_iri)}` } : undefined}
            bladAttrs={(b) => ({ "data-kandidaat": b.bron_iri })}
            renderBlad={(b) => (
              <KandidaatRegel werkgebiedId={id} k={b.data} plek={b.label} labels={labels}
                open={open === b.bron_iri} onWissel={() => setOpen((o) => (o === b.bron_iri ? null : b.bron_iri))} />
            )} />
        </div>
      )}

      {beslisbaar && doelen.length > 0 && (
        <ActieBalk filter={filter} aantal={doelen.length} bezig={bezig} uitsluiten={uitsluiten}
          onUitsluitenOpen={setUitsluiten}
          onOpnemen={(rol) => void opnemen(doelen, rol)}
          onLater={() => void later(doelen)}
          onHeropenen={() => void heropenen(doelen)}
          onUitsluiten={(reden) => void sluitUit(doelen, reden)}
          onWis={() => { setGekozen(new Set()); setUitsluiten(false); }} />
      )}
    </Sectie>
  );
}

/** Eén kandidaat in de boom: de plek onder het artikel (een link naar de bepaling), de rol, en één zin
 *  bewijs; *Bewijs* klapt het hele bewijs uit. Geen besluitknoppen: besluiten gaat in de actiebalk. */
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
      {open && (
        <div className="mt-1.5">
          <VraagLexKnop alleenInGesprek onderwerp={{ soort: "kandidaat", werkgebied_id: werkgebiedId, id: k.id, label: naam }} />
        </div>
      )}
    </div>
  );
}

/** De actiebalk: één besluit voor alles wat gekozen is (of de regel onder de cursor). */
function ActieBalk({ filter, aantal, bezig, uitsluiten, onUitsluitenOpen, onOpnemen, onLater, onHeropenen, onUitsluiten, onWis }: {
  filter: KandidaatFilter; aantal: number; bezig: { klaar: number; totaal: number } | null; uitsluiten: boolean;
  onUitsluitenOpen: (open: boolean) => void; onOpnemen: (rol: BronRol) => void; onLater: () => void; onHeropenen: () => void;
  onUitsluiten: (reden: string) => void; onWis: () => void;
}) {
  const [reden, setReden] = useState("");
  const redenRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (uitsluiten) redenRef.current?.focus();
  }, [uitsluiten]);
  const n = `(${aantal})`;
  return (
    <div data-actiebalk className="sticky bottom-0 z-10 -mx-1 rounded-kaart border border-line bg-paper p-3 shadow-kaart">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <span className="text-sm font-medium text-ink">
          {bezig ? `Bezig: ${bezig.klaar} van ${bezig.totaal}…` : `${aantal} ${aantal === 1 ? "bepaling" : "bepalingen"} gekozen`}
        </span>
        {(filter === "open" || filter === "later") && <>
          <Button size="sm" disabled={!!bezig} onClick={() => onOpnemen("analyseren")}>Opnemen om te analyseren {n}</Button>
          <Button size="sm" variant="secondary" disabled={!!bezig} onClick={() => onOpnemen("context")}>Opnemen als context {n}</Button>
        </>}
        {filter === "open" && <Button size="sm" variant="ghost" disabled={!!bezig} onClick={onLater}>Later {n}</Button>}
        {(filter === "open" || filter === "later") && (
          <Button size="sm" variant="ghost" disabled={!!bezig} aria-expanded={uitsluiten} onClick={() => onUitsluitenOpen(!uitsluiten)}>
            Uitsluiten… {n}
          </Button>
        )}
        {(filter === "later" || filter === "uitgesloten") && (
          <Button size="sm" variant="secondary" disabled={!!bezig} onClick={onHeropenen}>Heropenen {n}</Button>
        )}
        <button type="button" onClick={onWis} className="focus-ring rounded text-xs text-muted underline sm:ml-auto">Keuze wissen</button>
      </div>
      {uitsluiten && (
        <form className="mt-2 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => { e.preventDefault(); if (reden.trim()) { onUitsluiten(reden.trim()); setReden(""); } }}>
          <label className="sr-only" htmlFor="reden-uitsluiten">Reden om uit te sluiten</label>
          <Input id="reden-uitsluiten" ref={redenRef} value={reden} onChange={(e) => setReden(e.target.value)}
            placeholder="Waarom horen deze bepalingen er niet bij?" maxLength={2000}
            onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onUitsluitenOpen(false); } }} />
          <Button type="submit" size="sm" disabled={!!bezig || !reden.trim()} className="w-full sm:w-auto">Uitsluiten</Button>
        </form>
      )}
    </div>
  );
}
