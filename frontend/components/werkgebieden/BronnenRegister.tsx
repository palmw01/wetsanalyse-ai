"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Meer } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";
import { BronOpnemen } from "@/components/werkgebieden/BronOpnemen";
import { ProjectKop } from "@/components/werkgebieden/ProjectKop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { verwijderBron, wijzigBron } from "@/lib/api";
import type { BronRol, Bronselectie } from "@/lib/types";
import { BEREIK_LABEL, ROL_LABEL } from "@/lib/werkgebied";
import { bronPad, selectieStand, voorstellenPad } from "@/lib/werkgebiedPaden";

type RolFilter = "alle" | BronRol;

/** De bronnen van een werkgebied als doorzoekbaar register (mock-up v4, `projectSources`): per bepaling de
 *  regeling en bepaling, de rol en de stand van de annotatie. Wat Lex voorstelde staat in één regel
 *  erboven, met een eigen pagina om te beoordelen; opnemen gaat in een venster. */
export function BronnenRegister() {
  const { wg, stand, muteer } = useWerkgebied();
  const [zoek, setZoek] = useState("");
  const [rol, setRol] = useState<RolFilter>("alle");
  const [opnemen, setOpnemen] = useState(false);

  const perSelectie = useMemo(() => new Map((stand.werkvoorraad?.selecties ?? []).map((s) => [s.id, s])), [stand.werkvoorraad]);
  const open = stand.kandidaten?.filter((k) => k.status === "voorgesteld").length ?? 0;
  const term = zoek.trim().toLowerCase();
  const lijst = wg.bronnen.filter((b) => (rol === "alle" || b.rol === rol)
    && (!term || `${b.label} ${b.bwb_id} ${b.reden}`.toLowerCase().includes(term)));

  return (
    <div data-bronnen-register>
      <ProjectKop tab="bronnen" />
      {open > 0 && (
        <Link href={voorstellenPad(wg.id)} data-voorstellen-lex={open}
          className="focus-ring mb-4 flex items-center justify-between gap-3 rounded-kaart border-l-4 border-aandacht-geel-rand bg-aandacht-geel-bg/50 px-4 py-3 text-sm hover:bg-aandacht-geel-bg">
          <span className="text-ink">
            <span className="font-medium">{open} {open === 1 ? "bepaling" : "bepalingen"} voorgesteld door Lex</span>
            <span className="text-muted"> · neem op, zet op later of sluit uit</span>
          </span>
          <span className="shrink-0 font-medium text-lint">Beoordelen</span>
        </Link>
      )}
      <Kaart titel="Bronnen van het werkgebied" telling={wg.bronnen.length}
        toelichting="Een bronselectie is geen kopie van de bepaling: verwijderen uit het werkgebied laat de bepaling en haar annotaties staan."
        acties={<Button size="sm" onClick={() => setOpnemen(true)}>Bepaling opnemen</Button>}>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input type="search" value={zoek} onChange={(e) => setZoek(e.target.value)} placeholder="Zoek op regeling of bepaling"
            aria-label="Bronnen doorzoeken"
            className="focus-ring min-h-[36px] w-full rounded-field border border-line bg-paper px-3 text-sm sm:max-w-sm" />
          <div className="flex gap-1" role="group" aria-label="Rol">
            {(["alle", "analyseren", "context"] as const).map((r) => (
              <button key={r} type="button" onClick={() => setRol(r)} aria-pressed={rol === r}
                className={`focus-ring min-h-[32px] rounded-full border px-3 text-xs font-medium ${
                  rol === r ? "border-lint bg-lint/10 text-lint" : "border-line text-muted hover:text-lint"}`}>
                {r === "alle" ? "Alle" : ROL_LABEL[r]}
              </button>
            ))}
          </div>
          <span className="text-xs text-muted sm:ml-auto">{lijst.length} weergegeven</span>
        </div>
        {wg.bronnen.length === 0 ? (
          <p className="text-sm text-muted">Nog geen bronnen. Neem een bepaling op, of laat Lex ze zoeken in het gesprek.</p>
        ) : lijst.length === 0 ? (
          <p className="text-sm text-muted">Geen bronnen gevonden.</p>
        ) : (
          <ul aria-label="Bronnen" className="-mx-2 divide-y divide-line">
            {lijst.map((s) => (
              <BronRij key={s.id} wgId={wg.id} selectie={s} muteer={muteer}
                stand={s.rol === "analyseren" ? selectieStand(perSelectie.get(s.id)) : null} />
            ))}
          </ul>
        )}
      </Kaart>
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

/** Eén bron als rij: naam en wat hij in het werkgebied doet; de rij opent de pagina van de bepaling.
 *  Rol en verwijderen staan achter ⋯, niet als knoppen in elke rij. */
function BronRij({ wgId, selectie: s, muteer, stand }: {
  wgId: string;
  selectie: Bronselectie;
  muteer: ReturnType<typeof useWerkgebied>["muteer"];
  stand: { tekst: string; toon: "groen" | "geel" | "neutraal" } | null;
}) {
  const [open, setOpen] = useState(false);
  const naam = s.label || s.bron_iri;
  return (
    <li data-bron={s.id}>
      <div className="group flex items-center gap-2 rounded-md px-2 py-2.5 hover:bg-surface">
        <Link href={bronPad(s.bron_iri, wgId)} className="focus-ring min-w-0 flex-1 rounded">
          <span className="block text-sm font-medium text-ink [overflow-wrap:anywhere] group-hover:text-lint">{naam}</span>
          <span className="mt-0.5 block text-xs text-muted [overflow-wrap:anywhere]">
            {ROL_LABEL[s.rol]} · {BEREIK_LABEL[s.bereik]}{s.reden ? ` · ${s.reden}` : ""}
          </span>
        </Link>
        <span className="flex shrink-0 gap-1.5">
          {stand ? <StatusLabel toon={stand.toon}>{stand.tekst}</StatusLabel>
            : s.rol === "context" && <StatusLabel>Context</StatusLabel>}
        </span>
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={`Rol en verwijderen: ${naam}`}
          className="focus-ring shrink-0 rounded p-1 text-muted hover:text-lint">
          <Meer />
        </button>
      </div>
      {open && (
        <div className="mx-2 mb-2 flex flex-col gap-2 rounded-md border border-line bg-surface p-3 sm:flex-row sm:items-center" data-bron-acties>
          <label className="text-xs text-muted" htmlFor={`rol-${s.id}`}>Rol</label>
          <select id={`rol-${s.id}`} value={s.rol}
            className="focus-ring min-h-[32px] rounded-field border border-line bg-paper px-2 text-sm"
            onChange={(e) => {
              const rol = e.target.value as BronRol;
              void muteer((r) => wijzigBron(wgId, s.id, { verwachte_revisie: r, rol }), {
                gelukt: `Rol gewijzigd naar ${ROL_LABEL[rol].toLowerCase()}.`,
              });
            }}>
            {(["analyseren", "context"] as const).map((r) => <option key={r} value={r}>{ROL_LABEL[r]}</option>)}
          </select>
          <BevestigKnop
            bevestigTekst="Verwijderen?"
            titel="Haalt de bepaling uit dit werkgebied; de bepaling en haar annotaties blijven bestaan."
            onBevestig={async () => {
              await muteer((r) => verwijderBron(wgId, s.id, r), {
                gelukt: "Uit het werkgebied verwijderd. De bepaling en haar annotaties blijven bestaan.",
              });
            }}
            className="focus-ring inline-flex min-h-[32px] items-center justify-center rounded-button border border-line bg-paper px-3 text-sm font-medium text-muted hover:text-ink sm:ml-auto"
            bevestigClassName="border-fout/40 text-fout"
          >
            Verwijderen uit werkgebied
          </BevestigKnop>
        </div>
      )}
    </li>
  );
}
