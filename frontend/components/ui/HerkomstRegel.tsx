import type { Herkomst } from "@/lib/herkomst";
import { herkomstRegel } from "@/lib/herkomst";

/** De herkomst van een bepaling op één regel: regeling · plek · stand, met de link naar de officiële bron. Dezelfde regel
 *  in de kop van het paneel en bij een fragment elders (een passage, een definitie, de citatiekaart): waar de tekst
 *  vandaan komt, staat er overal hetzelfde bij. De plek voluit staat in de tooltip. */
export function HerkomstRegel({ herkomst: h, link = true, className = "" }: {
  herkomst: Herkomst;
  /** Zonder link als de plek er zelf al een heeft. */
  link?: boolean;
  className?: string;
}) {
  const delen = herkomstRegel(h);
  if (!delen.length && !(link && h.href)) return null;
  return (
    <span className={`block min-w-0 truncate text-xs text-muted ${className}`} data-herkomst={h.bwb_id || undefined}
      title={[h.regeling, h.plekVoluit].filter(Boolean).join(" › ") || undefined}>
      {delen.join(" · ")}
      {link && h.href && <>{delen.length ? " · " : ""}<a href={h.href} target="_blank" rel="noopener noreferrer"
        className="focus-ring rounded text-lint underline-offset-2 hover:underline" data-herkomst-link>wetten.overheid.nl</a></>}
    </span>
  );
}
