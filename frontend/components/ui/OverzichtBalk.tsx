"use client";

import { FilterChip } from "./FilterChip";

/** De ene balk boven een overzicht – Annotaties, Werkgebieden, Begrippen: links de filterknoppen met
 *  tellers, in het midden *Door mij bewerkt* (en wat een overzicht extra nodig heeft), rechts het
 *  zoekveld. Gedeeld, zodat de drie overzichten niet uit elkaar lopen. Twee of vier knoppen in plaats
 *  van een keuzelijst: bij zo weinig standen is kiezen sneller dan uitklappen. */
export function OverzichtBalk<T extends string>({
  filters, gekozen, onKies, filterLabel, mijn, onMijn, extra, zoekterm, onZoek, zoekLabel, placeholder,
}: {
  filters: { waarde: T; label: string; aantal?: number }[];
  gekozen: T;
  onKies: (waarde: T) => void;
  filterLabel: string;
  mijn: boolean;
  onMijn: (mijn: boolean) => void;
  extra?: React.ReactNode;
  zoekterm: string;
  onZoek: (term: string) => void;
  zoekLabel: string;
  placeholder: string;
}) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <div role="group" aria-label={filterLabel} className="flex flex-wrap gap-1.5">
        {filters.map((f) => (
          <FilterChip key={f.waarde} gekozen={gekozen === f.waarde} onKies={() => onKies(f.waarde)}>
            {f.label}
            {typeof f.aantal === "number" ? ` (${f.aantal})` : ""}
          </FilterChip>
        ))}
      </div>

      <label className="inline-flex items-center gap-1.5 text-xs text-muted">
        <input
          type="checkbox"
          checked={mijn}
          onChange={(e) => onMijn(e.target.checked)}
          className="focus-ring h-3.5 w-3.5 accent-lint"
        />
        Door mij bewerkt
      </label>

      {extra}

      <input
        type="search"
        value={zoekterm}
        onChange={(e) => onZoek(e.target.value)}
        aria-label={zoekLabel}
        placeholder={placeholder}
        className="w-full rounded-field border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-lint focus:ring-2 focus:ring-lint/20 coarse:min-h-[48px] sm:w-72"
      />
    </div>
  );
}
