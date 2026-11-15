import type { ReactNode } from "react";

/** Wat een klik op de chip doet. Eén werkwoord per handeling, zodat dezelfde soort overal hetzelfde zegt. */
export type ChipHandeling = "bekijken" | "beoordelen";

/** De ondertitel van een chip: soort · handeling ("Bepaling · bekijken", "Annotatie · beoordelen"). */
export function chipSub(soort: string | undefined, handeling: ChipHandeling): string {
  return soort ? `${soort} · ${handeling}` : handeling;
}

const KAART = "flex w-full items-center gap-3 rounded-kaart border border-line bg-surface px-4 py-3 text-left";

/** Het kaartje in het gesprek dat iets naast het gesprek opent (generieke componenten, 15 nov 2026): een bepaling onder
 *  een antwoord, een annotatie, een ander artefact, een overzicht of een kandidaat om te annoteren. Icoontegel, titel en
 *  ondertitel (afgekapt, of op twee regels met `subRegels={2}`) en een chevron. Zonder `onClick` staat er een kaart met
 *  een gestippelde rand die niets opent en dat zegt (een gereserveerd artefact). `app/paneelChip.test.ts` bewaakt dat
 *  er geen tweede vorm naast komt. */
export function PaneelChip({ titel, sub, icoon, onClick, uitgeschakeld = false, subRegels = 1, label, ...data }: {
  titel: ReactNode;
  sub?: ReactNode;
  /** Een icoon van 18 px; zonder icoon geen tegel. */
  icoon?: ReactNode;
  onClick?: () => void;
  uitgeschakeld?: boolean;
  subRegels?: 1 | 2;
  /** De voorleesnaam, als die meer zegt dan titel en sub samen. */
  label?: string;
} & Record<`data-${string}`, string | number | undefined>) {
  const tekst = (
    <span className="min-w-0 flex-1">
      <span className="block truncate text-sm font-medium text-ink">{titel}</span>
      {sub && <span className={`block text-xs text-muted ${subRegels === 2 ? "mt-0.5 line-clamp-2" : "truncate"}`}>{sub}</span>}
    </span>
  );
  const tegel = icoon && (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-lint/10 text-lint" aria-hidden>{icoon}</span>
  );
  if (!onClick) {
    return <div className={`${KAART} border-dashed`} {...data}>{tegel}{tekst}</div>;
  }
  return (
    <button type="button" onClick={onClick} disabled={uitgeschakeld} aria-label={label} {...data}
      className={`${KAART} shadow-zacht transition-all hover:-translate-y-0.5 hover:border-lint/40 hover:shadow-kaart disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint motion-reduce:hover:translate-y-0`}>
      {tegel}
      {tekst}
      <span className="shrink-0 text-muted" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6" /></svg>
      </span>
    </button>
  );
}
