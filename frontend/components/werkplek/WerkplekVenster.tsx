import { WorkbenchShell } from "@/components/werkplek/WorkbenchShell";

/** De werkplek beheert zijn eigen hoogte en scroll: vol-bleed, precies één viewport hoog. Die
 *  container stond eerder in de globale layout; nu die kaal is, draagt de werkplek hem zelf. Zonder
 *  deze klasse scrolt de chat als document en staat de invoerbalk niet meer gepind onderaan.
 *
 *  Waarom een eigen component en niet gewoon in de pagina: twee plekken renderen de werkplek – de
 *  pagina (`app/workbench/page.tsx`) en de `default` van het children-slot (`app/default.tsx`). Ze
 *  moeten dezelfde elementboom opleveren, anders remount React de hele schil zodra de router van de
 *  ene naar de andere valt – en dan is het openstaande gesprek weg. */
export function WerkplekVenster({
  beginGesprekId = null,
  beginArtefact,
}: {
  /** Gesprek dat bij binnenkomst open moet staan (deep-link vanuit het annotatie-overzicht). */
  beginGesprekId?: string | null;
  /** Annotatie die bij binnenkomst als artefact open moet staan. */
  beginArtefact?: string;
} = {}) {
  return (
    <div className="h-screen h-[100dvh] overflow-hidden">
      <WorkbenchShell beginGesprekId={beginGesprekId} beginArtefact={beginArtefact} />
    </div>
  );
}
