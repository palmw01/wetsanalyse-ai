"use client";

import { ChevronOmlaag } from "@/components/ui/Icoon";
import type { VragenGroep } from "@/lib/vraagkaart";

/** De vragen van Lex bij het samenstellen van een werkgebied, zoals ze in de thread staan: één kaart met
 *  per vraag de vraag (grijs) en je antwoord (zwart) – geen losse antwoordbubbels, zoals bij Claude.
 *  Daaronder "Een vraag stellen ›" zolang er een vraag openstaat (die opent de vraag onderaan weer), of
 *  "Nadenken…" terwijl Lex de volgende voorbereidt. */
export function VragenKaart({ groep, onOpen }: { groep: VragenGroep; onOpen: () => void }) {
  return (
    <div data-vragenkaart={groep.intake_id}>
      {groep.paren.length > 0 && (
        <div className="mt-1 rounded-[20px] border border-line bg-white px-5 py-4 shadow-zacht">
          <p className="text-sm text-muted">{groep.paren.length === 1 ? "Vraag" : "Vragen"}</p>
          <dl className="mt-2 space-y-3">
            {groep.paren.map((p, i) => (
              <div key={`${p.stap}-${i}`} data-vraagpaar={p.stap}>
                <dt className="text-[15px] text-muted">{p.vraag}</dt>
                <dd className={`mt-0.5 whitespace-pre-line text-[15px] ${p.overgeslagen ? "italic text-faint" : "text-ink"}`}>
                  {p.overgeslagen ? "Overgeslagen" : p.antwoord}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {groep.denkt ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted" data-vraag-denkt>
          <span className="inline-flex gap-0.5" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-soft" style={{ animationDelay: `${i * 150}ms` }} />
            ))}
          </span>
          Nadenken…
        </p>
      ) : groep.open ? (
        <button type="button" onClick={onOpen} data-vraag-open
          className="focus-ring mt-3 inline-flex items-center gap-2 rounded-full py-1 pr-2 text-sm text-muted hover:text-ink">
          <span className="relative inline-flex h-3.5 w-3.5 items-center justify-center" aria-hidden>
            <span className="absolute h-3.5 w-3.5 rounded-full bg-accent-soft/30" />
            <span className="h-2 w-2 rounded-full bg-accent-soft" />
          </span>
          Een vraag stellen
          <ChevronOmlaag className="-rotate-90" />
        </button>
      ) : null}
    </div>
  );
}
