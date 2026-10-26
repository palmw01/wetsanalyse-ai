"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Archief, ChevronOmlaag, Mapje, Meer, Plus } from "@/components/ui/Icoon";
import { Skeleton } from "@/components/ui/Skeleton";
import { GesprekActies } from "@/components/werkplek/GesprekActies";
import { bewaarDicht, deelIn, leesDicht } from "@/lib/gesprekGroepen";
import type { GesprekSamenvatting } from "@/lib/types";

function korteDatum(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const nu = new Date();
  const zelfdeDag = d.toDateString() === nu.toDateString();
  return zelfdeDag
    ? d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("nl-NL", { day: "numeric", month: "short" });
}

interface Props {
  gesprekken: GesprekSamenvatting[];
  activeId?: string | null;
  onOpen: (id: string) => void;
  onHernoem: (id: string, titel: string) => void;
  onVerwijder: (id: string) => void;
  onArchiveer: (id: string, gearchiveerd: boolean) => void;
  onVerplaats: (id: string, werkgebiedId: string) => void;
  /** Een nieuw gesprek dat meteen bij dit werkgebied hoort. */
  onNieuwInWerkgebied?: (werkgebiedId: string) => void;
  /** Eerste fetch loopt nog: toon skeleton-rijen i.p.v. de lege-staat. */
  laden?: boolean;
}

type RijActies = Pick<Props, "onOpen" | "onHernoem" | "onVerwijder" | "onArchiveer" | "onVerplaats">;

const KOP = "px-2 pb-1 pt-3 text-[0.65rem] font-semibold uppercase tracking-wide text-faint";

/** De gesprekken in de sidebar (spoor G1), zoals een project-app: per werkgebied een uitklapbare
 *  groep met de eigen gesprekken erin, daaronder de losse gesprekken (*Recente gesprekken*) en
 *  ingeklapt het archief. Een klik opent altijd dezelfde werkplek; de groep bepaalt alleen welke
 *  context Lex meekrijgt. */
export function GesprekLijst({ gesprekken, activeId, onNieuwInWerkgebied, laden, ...acties }: Props) {
  const indeling = useMemo(() => deelIn(gesprekken), [gesprekken]);
  const [dicht, setDicht] = useState<Set<string>>(() => new Set());
  const [archiefOpen, setArchiefOpen] = useState(false);
  // Na het mounten: de server kent `localStorage` niet, en een verschil tussen server- en
  // client-render geeft een hydratiefout.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setDicht(leesDicht()), []);

  function wissel(id: string) {
    setDicht((oud) => {
      const nieuw = new Set(oud);
      if (nieuw.has(id)) nieuw.delete(id);
      else nieuw.add(id);
      bewaarDicht(nieuw);
      return nieuw;
    });
  }

  if (gesprekken.length === 0) {
    if (laden) {
      return (
        <div className="flex flex-col gap-1 px-1 py-1" aria-hidden>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      );
    }
    return <p className="px-2 py-3 text-xs text-muted">Nog geen gesprekken.</p>;
  }

  const rijen = (lijst: GesprekSamenvatting[]) => (
    <ul className="flex flex-col gap-0.5">
      {lijst.map((g) => (
        <Rij key={g.id} gesprek={g} actief={g.id === activeId} acties={acties} />
      ))}
    </ul>
  );

  return (
    <div className="flex flex-col" data-gesprekken>
      {indeling.werkgebieden.length > 0 && (
        <section aria-label="Gesprekken per werkgebied" data-groep="werkgebieden">
          <p className={KOP}>Werkgebieden</p>
          {indeling.werkgebieden.map((w) => {
            const open = !dicht.has(w.id);
            return (
              <div key={w.id} className="mb-0.5" data-werkgebied-groep={w.id}>
                <div className="group flex items-center rounded-lg hover:bg-paper">
                  <button
                    type="button"
                    onClick={() => wissel(w.id)}
                    aria-expanded={open}
                    className="focus-ring flex min-h-[32px] min-w-0 flex-1 items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-sm font-medium text-ink coarse:min-h-[44px]"
                  >
                    <ChevronOmlaag className={`text-faint transition-transform ${open ? "" : "-rotate-90"}`} />
                    <Mapje className="text-lint" />
                    <span className="truncate">{w.naam}</span>
                  </button>
                  {onNieuwInWerkgebied && (
                    <button
                      type="button"
                      onClick={() => onNieuwInWerkgebied(w.id)}
                      aria-label={`Nieuw gesprek in ${w.naam}`}
                      title="Nieuw gesprek in dit werkgebied"
                      className="focus-ring mr-1 rounded p-1 text-muted opacity-100 hover:text-lint lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
                    >
                      <Plus />
                    </button>
                  )}
                </div>
                {open && <div className="ml-3 border-l border-line pl-1">{rijen(w.gesprekken)}</div>}
              </div>
            );
          })}
        </section>
      )}

      <section aria-label="Recente gesprekken" data-groep="recent">
        <p className={KOP}>Recente gesprekken</p>
        {indeling.recent.length > 0 ? rijen(indeling.recent) : (
          <p className="px-2 py-1.5 text-xs text-muted">Geen losse gesprekken.</p>
        )}
      </section>

      {indeling.archief.length > 0 && (
        <section aria-label="Archief" data-groep="archief" className="mt-2">
          <button
            type="button"
            onClick={() => setArchiefOpen((v) => !v)}
            aria-expanded={archiefOpen}
            className={`focus-ring flex w-full items-center gap-1.5 rounded-md ${KOP} hover:text-muted`}
          >
            <ChevronOmlaag className={`transition-transform ${archiefOpen ? "" : "-rotate-90"}`} />
            <Archief /> Archief ({indeling.archief.length})
          </button>
          {archiefOpen && rijen(indeling.archief)}
        </section>
      )}
    </div>
  );
}

function Rij({ gesprek, actief, acties }: { gesprek: GesprekSamenvatting; actief: boolean; acties: RijActies }) {
  const [bewerk, setBewerk] = useState(false);
  const [menu, setMenu] = useState(false);
  const [titel, setTitel] = useState(gesprek.titel);
  const label = gesprek.titel || "Nieuw gesprek";
  // `Enter` sluit de bewerk-modus (unmount van de input) → `onBlur` vuurt daarná óók: guard tegen 2× PATCH.
  const bewaardRef = useRef(false);

  function bewaar() {
    if (bewaardRef.current) return;
    bewaardRef.current = true;
    const schoon = titel.trim();
    if (schoon && schoon !== gesprek.titel) acties.onHernoem(gesprek.id, schoon);
    setBewerk(false);
  }

  if (bewerk) {
    return (
      <li className="px-1 py-0.5">
        <input
          autoFocus
          value={titel}
          onChange={(e) => setTitel(e.target.value)}
          onBlur={bewaar}
          onKeyDown={(e) => {
            if (e.key === "Enter") bewaar();
            if (e.key === "Escape") {
              setTitel(gesprek.titel);
              setBewerk(false);
            }
          }}
          className="w-full rounded-field border border-lint bg-paper px-2 py-1.5 text-sm text-ink focus:outline-none"
        />
      </li>
    );
  }

  return (
    <li data-gesprek-rij={gesprek.id}>
      <div
        className={`group relative flex items-center rounded-lg transition-colors ${
          actief ? "bg-lint/10" : "hover:bg-paper"
        }`}
      >
        <button
          type="button"
          onClick={() => acties.onOpen(gesprek.id)}
          aria-current={actief ? "page" : undefined}
          className="min-w-0 flex-1 px-2.5 py-2 text-left focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-lint"
        >
          <span className={`block truncate text-sm ${actief ? "font-medium text-lint" : "text-ink"}`}>
            {label}
          </span>
          <span className="mt-0.5 block text-[0.65rem] text-faint">
            {gesprek.aantal_berichten} berichten{korteDatum(gesprek.updated) ? ` · ${korteDatum(gesprek.updated)}` : ""}
          </span>
        </button>
        {/* Alleen op fijne pointers verborgen tot hover; op touch altijd zichtbaar. */}
        <button
          type="button"
          onClick={() => setMenu((v) => !v)}
          aria-expanded={menu}
          aria-label={`Acties voor ${label}`}
          title="Meer"
          className={`focus-ring mr-1.5 shrink-0 rounded p-1 text-muted transition-opacity hover:text-lint ${
            menu ? "opacity-100" : "opacity-100 lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
          }`}
        >
          <Meer />
        </button>
      </div>
      {menu && (
        <div className="mx-1 mb-1 rounded-lg border border-line bg-paper shadow-zacht">
          <GesprekActies
            werkgebiedId={gesprek.werkgebied_id}
            gearchiveerd={Boolean(gesprek.gearchiveerd)}
            onHernoem={() => {
              setTitel(gesprek.titel);
              bewaardRef.current = false;
              setBewerk(true);
            }}
            onArchiveer={(a) => acties.onArchiveer(gesprek.id, a)}
            onVerplaats={(w) => acties.onVerplaats(gesprek.id, w)}
            onVerwijder={() => acties.onVerwijder(gesprek.id)}
            onKlaar={() => setMenu(false)}
          />
        </div>
      )}
    </li>
  );
}
