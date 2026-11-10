/** Gesprekken die buiten de sidebar verdwenen of verhuisden (instellingen → Gesprekken): de sidebar laadt dan opnieuw,
 *  en staat het open gesprek ertussen, dan blijft de werkplek leeg achter. Eén venster-event, zoals
 *  `BRONSELECTIE_GEWIJZIGD`, zodat het instellingenvenster de werkplek niet hoeft te kennen. */
export const GESPREKKEN_GEWIJZIGD = "wa:gesprekken-gewijzigd";

export interface GesprekkenGewijzigd {
  /** Wat er gebeurde: `verwijderd` sluit een open gesprek, `gearchiveerd` ververst alleen de lijst. */
  soort: "verwijderd" | "gearchiveerd";
  ids: string[];
}

export function meldGesprekkenGewijzigd(detail: GesprekkenGewijzigd): void {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(GESPREKKEN_GEWIJZIGD, { detail }));
}

/** Wat de werkplek met de melding doet: altijd verversen, en het open gesprek sluiten als het weg is. */
export function gevolgVoorWerkplek(detail: GesprekkenGewijzigd, activeId: string | null): { sluit: boolean } {
  return { sluit: detail.soort === "verwijderd" && activeId !== null && detail.ids.includes(activeId) };
}
