"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { foutTekst, lijstWerkgebieden, zoekBegrippen } from "@/lib/api";
import {
  BEGRIP_STATUSSEN, BEGRIP_STATUS_LABEL, filtersUitParams, kaartUrl, kort, paramsVan,
  type BegrippenOverzicht, type OverzichtFilters,
} from "@/lib/begrippenOverzicht";
import type { BegripStatus, WerkgebiedSamenvatting } from "@/lib/types";

const PIL: Record<BegripStatus, string> = {
  geaccordeerd: "border-lint/40 bg-lint/10 text-lint",
  concept: "border-line text-muted",
  vervangen: "border-line text-faint line-through",
};

/** Het overzicht van de begrippen over alle werkgebieden heen (spoor D, fase F4). Een leesingang:
 *  zoeken op naam, alternatieve term of definitie, filteren op status en werkgebied, en doorklikken
 *  naar de kaart in zijn werkgebied – daar gebeurt het werk. De filters staan in de URL, zodat
 *  terugbladeren en delen werken. */
export function BegrippenOverzichtClient() {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const filters = useMemo(() => filtersUitParams(new URLSearchParams(zoekParams.toString())), [zoekParams]);
  const [term, setTerm] = useState(filters.q);
  const [data, setData] = useState<BegrippenOverzicht | null>(null);
  const [werkgebieden, setWerkgebieden] = useState<WerkgebiedSamenvatting[]>([]);
  const [fout, setFout] = useState<string | null>(null);

  function zet(nieuw: OverzichtFilters) {
    const qs = paramsVan(nieuw, "pagina").toString();
    // `replace`: een filter is geen stap in de geschiedenis.
    router.replace(qs ? `${pad}?${qs}` : pad, { scroll: false });
  }

  // Typen zoekt na een korte pauze; elke toetsaanslag een verzoek is onnodig.
  useEffect(() => {
    if (term === filters.q) return;
    const t = setTimeout(() => zet({ ...filters, q: term }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  useEffect(() => {
    let weg = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFout(null);
    zoekBegrippen(paramsVan(filters, "api"))
      .then((d) => { if (!weg) setData(d); })
      .catch((e) => {
        if (weg) return;
        setFout(foutTekst(e, "De begrippen konden niet worden geladen."));
        setData({ resultaten: [], totaal: 0, volgende_offset: null });
      });
    return () => { weg = true; };
  }, [filters]);

  useEffect(() => {
    lijstWerkgebieden().then(setWerkgebieden).catch(() => setWerkgebieden([]));
  }, []);

  function wisselStatus(s: BegripStatus) {
    const status = filters.status.includes(s) ? filters.status.filter((x) => x !== s) : [...filters.status, s];
    zet({ ...filters, status });
  }

  return (
    <WerkgebiedSchil titel="Begrippen" onFout={setFout}>
      <header className="mb-5">
        <h1 className="font-display text-lg font-semibold text-lint">Begrippen</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          De begrippen uit alle werkgebieden. Een begrip is een analyse-uitkomst, geen wettelijke
          definitie; je werkt eraan op de kaart in zijn werkgebied.
        </p>
      </header>

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <input
          type="search"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          aria-label="Zoeken in begrippen"
          placeholder="Zoek op naam, term of definitie"
          className="w-full rounded-field border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-lint focus:ring-2 focus:ring-lint/20 coarse:min-h-[48px] sm:w-72"
        />
        <div role="group" aria-label="Status" className="flex flex-wrap gap-1.5">
          {BEGRIP_STATUSSEN.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={filters.status.includes(s)}
              onClick={() => wisselStatus(s)}
              className={`focus-ring min-h-[24px] rounded-full border px-2.5 py-0.5 text-[0.7rem] transition coarse:min-h-[44px] ${
                filters.status.includes(s) ? "border-lint bg-lint text-paper" : "border-line text-muted hover:border-lint hover:text-ink"
              }`}
            >
              {BEGRIP_STATUS_LABEL[s]}
            </button>
          ))}
        </div>
        <label className="inline-flex items-center gap-1.5 text-xs text-muted">
          Werkgebied
          <select
            value={filters.werkgebied}
            onChange={(e) => zet({ ...filters, werkgebied: e.target.value })}
            className="focus-ring max-w-[14rem] rounded-field border border-line bg-paper px-2 py-1.5 text-sm text-ink coarse:min-h-[44px]"
          >
            <option value="">Alle werkgebieden</option>
            {werkgebieden.map((w) => (
              <option key={w.id} value={w.id}>{w.naam}</option>
            ))}
          </select>
        </label>
      </div>

      {fout && (
        <Melding type="fout" className="mb-4">
          {fout}
        </Melding>
      )}

      {data === null ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-2 rounded-button border border-line bg-paper p-4">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-80" />
            </div>
          ))}
        </div>
      ) : data.resultaten.length === 0 ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          {filters.q || filters.status.length || filters.werkgebied
            ? "Geen begrippen bij deze filters."
            : "Nog geen begrippen. Begrippen ontstaan in een werkgebied, op de tab Begrippen."}
        </p>
      ) : (
        <>
          <p className="mb-2 text-xs text-muted" aria-live="polite">
            {data.totaal === 1 ? "1 begrip" : `${data.totaal} begrippen`}
            {data.resultaten.length < data.totaal ? ` (de eerste ${data.resultaten.length})` : ""}
          </p>
          <ul className="space-y-2" data-testid="begrippen-overzicht">
            {data.resultaten.map((b) => (
              <li key={b.id}>
                <Link
                  href={kaartUrl(b.werkgebied_id, b.id)}
                  className="focus-ring block rounded-button border border-line bg-paper p-4 transition-shadow hover:shadow-kaart"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <span className="min-w-0 font-display text-sm font-semibold text-lint">{b.naam}</span>
                    <span className={`inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${PIL[b.status]}`}>
                      {BEGRIP_STATUS_LABEL[b.status]}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted">
                    {b.werkgebied_naam}
                    {b.alternatieve_termen.length > 0 && ` · ook: ${b.alternatieve_termen.join(", ")}`}
                  </p>
                  {b.definitie ? (
                    <p className="mt-1.5 text-sm text-ink">{kort(b.definitie)}</p>
                  ) : (
                    <p className="mt-1.5 text-sm italic text-faint">Nog geen definitie.</p>
                  )}
                  {b.vervangen_door && (
                    <p className="mt-1 text-xs text-muted">Vervangen door {b.vervangen_door.naam}</p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </WerkgebiedSchil>
  );
}
