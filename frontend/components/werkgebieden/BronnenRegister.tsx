"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Select } from "@/components/ui/Field";
import { Meer } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { BronOpnemen } from "@/components/werkgebieden/BronOpnemen";
import { ProjectKop } from "@/components/werkgebieden/ProjectKop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { FilterChip } from "@/components/ui/FilterChip";
import { verwijderBron, wijzigBron } from "@/lib/api";
import { bronnenZin, deelvraagStand } from "@/lib/bronselectie";
import {
  bepalingEnRegeling, bronnenPerDeelvraag, filterGroepen, ookBijZin, uniekeBronnen, type BronInGroep,
} from "@/lib/bronnenPerDeelvraag";
import { splits } from "@/lib/deelvragen";
import type { BronRol } from "@/lib/types";
import { useBronselectieStand } from "@/lib/useBronselectieStand";
import { ROL_LABEL } from "@/lib/werkgebied";
import { artefactPad, bronPad, deelvraagPad, selectieStand, voorstellenPad } from "@/lib/werkgebiedPaden";

type RolFilter = "alle" | BronRol;

/** De bronnen van een werkgebied (mock-up v4, `projectSources`), per deelvraag (spoor K, methode 1f/1g): één
 *  bronselectie voor het werkgebied, getoond onder de deelvragen waar ze bij hoort, en wat bij geen deelvraag
 *  hoort onder *Zonder deelvraag*. Per bron een statuspil: *Geselecteerd* (om te analyseren), *Context*; per
 *  deelvraag de voorstellen van Lex die nog open staan als *Ter beoordeling*. Opnemen gaat in een venster. */
export function BronnenRegister() {
  const { wg, stand, muteer } = useWerkgebied();
  const [zoek, setZoek] = useState("");
  const [rol, setRol] = useState<RolFilter>("alle");
  const [opnemen, setOpnemen] = useState(false);
  const { actief } = splits(wg.deelvragen);
  const overzicht = useBronselectieStand(wg.id, wg.revisie, actief.length);

  const perSelectie = useMemo(() => new Map((stand.werkvoorraad?.selecties ?? []).map((s) => [s.id, s])), [stand.werkvoorraad]);
  const voortgang = useMemo(() => new Map((overzicht?.deelvragen ?? []).map((d) => [d.id, d])), [overzicht]);
  const open = stand.kandidaten?.filter((k) => k.status === "voorgesteld").length ?? 0;
  const term = zoek.trim().toLowerCase();
  const gefilterd = rol !== "alle" || !!term;
  const groepen = filterGroepen(bronnenPerDeelvraag(wg.bronnen, actief, overzicht),
    (b) => (rol === "alle" || b.rol === rol) && (!term || `${b.selectie.label} ${b.selectie.bwb_id} ${b.selectie.reden}`.toLowerCase().includes(term)),
    gefilterd);
  const weergegeven = uniekeBronnen(groepen);

  return (
    <div data-bronnen-register>
      <ProjectKop tab="bronnen" />
      {open > 0 && (
        <Link href={voorstellenPad(wg.id)} data-voorstellen-lex={open}
          className="focus-ring mb-4 flex items-center justify-between gap-3 rounded-kaart border-l-4 border-aandacht-geel-rand bg-aandacht-geel-bg/50 px-4 py-3 text-sm hover:bg-aandacht-geel-bg">
          <span className="text-ink">
            <span className="font-medium">{open} {open === 1 ? "bepaling" : "bepalingen"} voorgesteld door Lex</span>
            <span className="text-muted"> · bekijk ze, en kies per deelvraag in het gesprek</span>
          </span>
          <span className="shrink-0 font-medium text-lint">Bekijken</span>
        </Link>
      )}
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-base font-semibold text-lint">Bronnen van het werkgebied</h2>
          <p className="mt-0.5 text-xs text-muted">
            {wg.bronnen.length} {wg.bronnen.length === 1 ? "bronselectie" : "bronselecties"}
            {actief.length ? `, per deelvraag gekoppeld` : ""}. Verwijderen uit het werkgebied laat de bepaling en haar annotaties staan.
          </p>
        </div>
        <Button size="sm" onClick={() => setOpnemen(true)}>Bepaling opnemen</Button>
      </div>
      <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-center">
        <input type="search" value={zoek} onChange={(e) => setZoek(e.target.value)} placeholder="Zoek op regeling of bepaling"
          aria-label="Bronnen doorzoeken"
          className="focus-ring min-h-[36px] w-full rounded-field border border-line bg-paper px-3 text-sm sm:max-w-sm" />
        <div className="flex gap-1" role="group" aria-label="Rol">
          {(["alle", "analyseren", "context"] as const).map((r) => (
            <FilterChip key={r} gekozen={rol === r} onKies={() => setRol(r)}>
              {r === "alle" ? "Alle" : ROL_LABEL[r]}
            </FilterChip>
          ))}
        </div>
        <span className="text-xs text-muted sm:ml-auto">{weergegeven} weergegeven</span>
      </div>
      {wg.bronnen.length === 0 && !actief.length ? (
        <p className="text-sm text-muted">Nog geen bronnen. Neem een bepaling op, of bepaal ze per deelvraag met Lex in het gesprek.</p>
      ) : groepen.length === 0 ? (
        <p className="text-sm text-muted">Geen bronnen gevonden.</p>
      ) : (
        <div className="space-y-6">
          {groepen.map((g) => {
            const d = g.deelvraag, v = d ? deelvraagStand(voortgang.get(d.id)) : null;
            const n = g.bronnen.length;
            return (
              <Groep key={d?.id ?? "zonder"} data-bronnen-groep={d?.id ?? "zonder"}
                kop={d ? <Link href={deelvraagPad(wg.id, d.id)} className="focus-ring rounded hover:underline">{d.nr}. {d.vraag}</Link>
                  : actief.length ? "Zonder deelvraag" : "Bronnen"}
                sub={!d && actief.length ? "Bij geen enkele deelvraag gekoppeld, bijvoorbeeld een definitie of context." : undefined}
                telling={bronnenZin(n)}
                status={v && <StatusLabel toon={v.toon}>{v.label}</StatusLabel>}
                label={d ? `Bronnen bij deelvraag ${d.nr}` : "Bronnen zonder deelvraag"}
                leeg={d ? "Er hoort nog geen bron bij deze deelvraag. Bepaal de bronnen met Lex in het gesprek." : "Nog geen bronnen."}>
                {g.bronnen.map((b) => (
                  <BronRij key={b.selectie.id} wgId={wg.id} bron={b} muteer={muteer}
                    stand={b.rol === "analyseren" ? selectieStand(perSelectie.get(b.selectie.id)) : null} />
                ))}
                {d && g.voorstellen.map((k) => (
                  <GroepRij key={`k-${k.id}`} data-voorstel-hier={k.id} href={artefactPad(wg.id, "bronselectie")}
                    titel={bepalingEnRegeling(k.label || k.bron_iri).bepaling}
                    sub={<>{bepalingEnRegeling(k.label || k.bron_iri).regeling || "Voorgesteld door Lex"} · voorstel van Lex</>}
                    status={<StatusLabel toon="geel">Ter beoordeling</StatusLabel>} />
                ))}
              </Groep>
            );
          })}
        </div>
      )}
      {opnemen && (
        <Dialog label="Bepaling opnemen" variant="compact" onSluit={() => setOpnemen(false)}>
          <div className="overflow-y-auto p-5">
            <BronOpnemen wg={wg} muteer={muteer} onKlaar={() => setOpnemen(false)} />
          </div>
        </Dialog>
      )}
    </div>
  );
}

/** Eén bron als rij (de `itemrow` van de mock-up): de bepaling als titel, de regeling en wat ze hier doet
 *  eronder, de status rechts; de rij opent de pagina van de bepaling. Rol en verwijderen staan achter ⋯. */
function BronRij({ wgId, bron, muteer, stand }: {
  wgId: string;
  bron: BronInGroep;
  muteer: ReturnType<typeof useWerkgebied>["muteer"];
  stand: { tekst: string; toon: "groen" | "geel" | "neutraal" } | null;
}) {
  const [open, setOpen] = useState(false);
  const s = bron.selectie;
  const naam = s.label || s.bron_iri;
  const { bepaling, regeling } = bepalingEnRegeling(naam);
  const sub = [regeling, ROL_LABEL[bron.rol].toLowerCase(), stand?.tekst.toLowerCase(), ookBijZin(bron.ook)].filter(Boolean).join(" · ");
  return (
    <GroepRij data-bron={s.id} href={bronPad(s.bron_iri, wgId)} titel={bepaling} sub={sub}
      status={bron.rol === "context" ? <StatusLabel>Context</StatusLabel> : <StatusLabel toon="groen">Geselecteerd</StatusLabel>}
      eind={(
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={`Rol en verwijderen: ${naam}`}
          className="focus-ring shrink-0 rounded p-1.5 text-muted hover:bg-paper hover:text-lint">
          <Meer />
        </button>
      )}
      onder={open && (
        <div className="mx-2 mb-2 flex flex-col gap-2 rounded-md border border-line bg-surface p-3 sm:flex-row sm:items-center" data-bron-acties>
          <label className="text-xs text-muted" htmlFor={`rol-${s.id}`}>Rol</label>
          <Select id={`rol-${s.id}`} value={s.rol} className="sm:w-48"
            onChange={(e) => {
              const rol = e.target.value as BronRol;
              void muteer((r) => wijzigBron(wgId, s.id, { verwachte_revisie: r, rol }), {
                gelukt: `Rol gewijzigd naar ${ROL_LABEL[rol].toLowerCase()}.`,
              });
            }}>
            {(["analyseren", "context"] as const).map((r) => <option key={r} value={r}>{ROL_LABEL[r]}</option>)}
          </Select>
          <BevestigKnop
            bevestigTekst="Verwijderen?"
            titel="Haalt de bepaling uit dit werkgebied; de bepaling en haar annotaties blijven bestaan."
            onBevestig={async () => {
              await muteer((r) => verwijderBron(wgId, s.id, r), {
                gelukt: "Uit het werkgebied verwijderd. De bepaling en haar annotaties blijven bestaan.",
              });
            }}
            className="focus-ring inline-flex min-h-[32px] items-center justify-center rounded-full border border-line bg-paper px-3 text-sm font-medium text-muted hover:text-ink sm:ml-auto"
            bevestigClassName="border-fout/40 text-fout"
          >
            Verwijderen uit werkgebied
          </BevestigKnop>
        </div>
      )} />
  );
}
