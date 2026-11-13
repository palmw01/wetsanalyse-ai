/** Een lijst bestanden om er één uit te kiezen (de werkplaats: de bestanden van een concept of van een versie). Het
 *  pad staat in vaste letterbreedte en breekt af binnen de kolom; `bij` zet labels achter een pad (gewijzigd, nieuw,
 *  het aantal bevindingen). De volgorde bepaalt de aanroeper. Het gekozen bestand is `aria-current`. */
export function Bestandenlijst({ paden, gekozen, onKies, label, bij, stand }: {
  paden: readonly string[];
  gekozen: string;
  onKies: (pad: string) => void;
  /** De toegankelijke naam van de lijst. */
  label: string;
  bij?: (pad: string) => React.ReactNode;
  /** Een korte stand per bestand voor `data-bestand-stand` (gewijzigd, nieuw, verwijderd), of leeg. */
  stand?: (pad: string) => string;
}) {
  return (
    <ul aria-label={label} className="-mx-1 space-y-0.5">
      {paden.map((p) => (
        <li key={p}>
          <button type="button" onClick={() => onKies(p)} aria-current={p === gekozen ? "true" : undefined} data-bestand={p}
            data-bestand-stand={stand?.(p) || undefined}
            className="focus-ring flex min-h-[32px] w-full items-center gap-2 rounded-knop px-2 py-1 text-left text-sm text-ink transition-colors hover:bg-surface aria-[current=true]:bg-lint/[0.06] aria-[current=true]:font-medium aria-[current=true]:text-lint coarse:min-h-[44px]">
            <span className="min-w-0 flex-1 font-mono text-xs [overflow-wrap:anywhere]">{p}</span>
            {bij?.(p)}
          </button>
        </li>
      ))}
    </ul>
  );
}
