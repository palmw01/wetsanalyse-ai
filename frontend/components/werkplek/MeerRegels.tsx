"use client";

import { useState } from "react";

import { Vinkje } from "@/components/ui/Icoon";
import { regelNamen, type Regel } from "@/lib/vraagkaart";

/** Meer dan één eigen antwoord op een kaartje van Lex (4 nov 2026): één regel is één ding – een deelvraag, een
 *  bepaling –, Enter in een gevulde regel of *+ Nog een …* opent de volgende, Ctrl/⌘+Enter stuurt in. Wat één regel
 *  is, zegt het kaartje (`regel`); zo is het overal dezelfde invoer: in het `VraagDock` en op het compacte kaartje van
 *  de bronselectie. Lege regels tellen niet (`antwoordActie`). */
export function MeerRegels({ teksten, onTeksten, regel, uitgeschakeld, onInsturen, maxLengte = 1000 }: {
  teksten: string[];
  onTeksten: (t: string[]) => void;
  regel: Regel | null;
  uitgeschakeld: boolean;
  /** Ctrl/⌘+Enter: insturen. */
  onInsturen: () => void;
  maxLengte?: number;
}) {
  const [nieuw, setNieuw] = useState<number | null>(null);
  const namen = regelNamen(regel);
  const regels = teksten.length ? teksten : [""];
  const erbij = (na: number) => {
    onTeksten([...regels.slice(0, na + 1), "", ...regels.slice(na + 1)]);
    setNieuw(na + 1);
  };
  return (
    <div data-meer-regels={namen.enkel}>
      <ul className="space-y-1" aria-label={namen.lijst}>
        {regels.map((t, i) => (
          <li key={i} className="flex items-center gap-3 py-1.5">
            <label className="min-w-0 flex-1">
              <span className="sr-only">{`${namen.label} ${i + 1}`}</span>
              <textarea
                rows={1}
                value={t}
                disabled={uitgeschakeld}
                maxLength={maxLengte}
                autoFocus={nieuw === i}
                placeholder={i === 0 ? namen.eerste : namen.volgende}
                onChange={(e) => onTeksten(regels.map((x, j) => (j === i ? e.target.value : x)))}
                onKeyDown={(e) => {
                  if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing) return;
                  e.preventDefault();
                  if (e.ctrlKey || e.metaKey) onInsturen();
                  else if (t.trim()) erbij(i);
                }}
                className="block w-full resize-none border-0 bg-transparent p-0 text-[15px] text-ink placeholder:text-faint focus:outline-none focus:ring-0 disabled:opacity-50"
              />
            </label>
            {t.trim() && <Vinkje className="text-lg text-lint" />}
          </li>
        ))}
      </ul>
      <button type="button" disabled={uitgeschakeld} onClick={() => erbij(regels.length - 1)}
        className="focus-ring mt-1 rounded text-sm font-medium text-lint hover:underline disabled:opacity-50">
        + Nog een {namen.enkel}
      </button>
    </div>
  );
}
