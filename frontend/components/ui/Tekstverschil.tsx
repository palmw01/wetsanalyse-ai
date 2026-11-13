"use client";

import { useMemo, useState } from "react";

import { blokken, tekstverschil, verschilZin, type VerschilRegel } from "@/lib/tekstverschil";

const KLEUR: Record<VerschilRegel["soort"], string> = {
  gelijk: "",
  erbij: "bg-aandacht-groen-bg text-aandacht-groen-tekst",
  weg: "bg-aandacht-rood-bg text-aandacht-rood-tekst",
};
const TEKEN: Record<VerschilRegel["soort"], string> = { gelijk: " ", erbij: "+", weg: "-" };
const WOORD: Record<VerschilRegel["soort"], string> = { gelijk: "", erbij: "erbij: ", weg: "weg: " };

/** Twee teksten vergeleken, regel voor regel (`lib/tekstverschil.ts`): wat erbij kwam groen met een +, wat wegviel
 *  rood met een −, met een paar gelijke regels eromheen. Een lange gelijke reeks is ingeklapt en klapt open met een
 *  klik. Eén kolom, dus ook op een telefoon zonder zijwaarts scrollen; een lange regel breekt af. Kleur draagt het
 *  verschil nooit alleen: het teken staat ervoor en een schermlezer hoort "erbij" of "weg". */
export function Tekstverschil({ oud, nieuw, label }: {
  oud: string;
  nieuw: string;
  /** De toegankelijke naam, bv. "Verschil in SKILL.md tussen versie 2 en versie 3". */
  label: string;
}) {
  const verschil = useMemo(() => tekstverschil(oud, nieuw), [oud, nieuw]);
  const delen = useMemo(() => blokken(verschil.regels), [verschil]);
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set());

  if (!verschil.erbij && !verschil.weg) return <p className="text-sm text-muted" data-verschil="geen">Geen verschil in dit bestand.</p>;
  return (
    <div role="group" aria-label={label} data-verschil={`${verschil.erbij}+${verschil.weg}`}>
      <p className="mb-2 text-xs text-muted">{verschilZin(verschil)}{verschil.grof && " · te lang om regel voor regel te vergelijken: het gewijzigde deel staat als één blok"}</p>
      <div className="overflow-hidden rounded-knop border border-line font-mono text-xs leading-relaxed">
        {delen.map((blok, i) => (blok.soort === "gelijk" && !open.has(i) ? (
          <button key={i} type="button" onClick={() => setOpen(new Set([...open, i]))} data-verschil-ingeklapt
            className="focus-ring block w-full border-y border-line bg-surface px-2 py-1 text-left font-sans text-xs text-muted first:border-t-0 last:border-b-0 hover:text-lint">
            {blok.regels.length === 1 ? "1 regel gelijk" : `${blok.regels.length} regels gelijk`} · toon
          </button>
        ) : blok.regels.map((r, j) => (
          <div key={`${i}.${j}`} data-regel={r.soort} className={`flex gap-2 px-2 ${KLEUR[r.soort]}`}>
            <span aria-hidden="true" className="w-3 shrink-0 select-none text-center">{TEKEN[r.soort]}</span>
            <span className="min-w-0 flex-1 whitespace-pre-wrap [overflow-wrap:anywhere]">
              {WOORD[r.soort] && <span className="sr-only">{WOORD[r.soort]}</span>}{r.tekst || " "}
            </span>
          </div>
        ))))}
      </div>
    </div>
  );
}
