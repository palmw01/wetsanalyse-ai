"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { FilterChip } from "@/components/ui/FilterChip";
import { BronnenBijDeelvraag } from "@/components/werkgebieden/BronnenBijDeelvraag";
import { BronOpnemen } from "@/components/werkgebieden/BronOpnemen";
import { ProjectKop } from "@/components/werkgebieden/ProjectKop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import type { BronRol } from "@/lib/types";
import { ROL_LABEL } from "@/lib/werkgebied";

type RolFilter = "alle" | BronRol;

/** De bronnen van een werkgebied (mock-up v4, `projectSources`): één plek voor de bronselectie per deelvraag
 *  (spoor K en L, methode 1f/1g). Eén lijst voor het werkgebied, getoond onder de deelvragen waar ze bij hoort,
 *  met de voorstellen van Lex en hun besluiten, en wat bij geen deelvraag hoort onder *Zonder deelvraag*
 *  (`BronnenBijDeelvraag`, ook op de deelvraagpagina en naast het gesprek). Het artefact Bronselectie is deze tab.
 *  Erboven de afbakening als tekst, zoeken, de rol en *Bepaling opnemen* (in een venster). */
export function BronnenRegister() {
  const { wg, stand, muteer, laad } = useWerkgebied();
  const [zoek, setZoek] = useState("");
  const [rol, setRol] = useState<RolFilter>("alle");
  const [opnemen, setOpnemen] = useState(false);

  const term = zoek.trim().toLowerCase();
  const actief = rol !== "alle" || !!term;
  const past = (s: { label: string; bwb_id?: string; reden?: string } | undefined, label: string, r: BronRol) =>
    (rol === "alle" || r === rol) && (!term || `${label} ${s?.bwb_id ?? ""} ${s?.reden ?? ""}`.toLowerCase().includes(term));
  const weergegeven = wg.bronnen.filter((b) => past(b, b.label, b.rol)).length;

  return (
    <div data-bronnen-register>
      <ProjectKop tab="bronnen" />
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-base font-semibold text-lint">Bronnen per deelvraag</h2>
          <p className="mt-0.5 text-xs text-muted">
            {wg.bronnen.length} {wg.bronnen.length === 1 ? "bronselectie" : "bronselecties"}. Kiezen per deelvraag doe je
            hier of met Lex in het gesprek (<em>Bepaal de bronnen per deelvraag</em>). Verwijderen uit het werkgebied laat de
            bepaling en haar annotaties staan.
          </p>
          {wg.afbakening.trim() && (
            <p className="mt-2 whitespace-pre-line text-xs text-ink" data-afbakening>
              <span className="font-medium text-muted">Afbakening · </span>{wg.afbakening}
            </p>
          )}
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
      <BronnenBijDeelvraag werkgebiedId={wg.id} revisie={wg.revisie}
        beheer={{ wg, muteer, laad, werkvoorraad: stand.werkvoorraad }} filter={{ past, actief }} />
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
