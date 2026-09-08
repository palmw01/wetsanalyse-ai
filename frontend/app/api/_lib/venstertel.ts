// Een teller per sleutel binnen een tijdvenster: "hoogstens N per minuut, per gebruiker".
//
// Bewust een eigen, piepklein ding en geen bibliotheek: de enige gebruiker is `/api/ui-spoor`, waar
// een rem nodig is omdat de meldingen uit de browser komen en een lus in de client anders een
// logstroom wordt. De klok gaat als parameter mee zodat het gedrag te testen is zonder te wachten.
//
// In-memory en dus per replica. Als rem is dat genoeg — een gedeelde teller zou meer machinerie
// kosten dan het probleem waard is. Verwacht daar dus geen exacte handhaving van.

interface Venster {
  /** Wanneer dit venster afloopt (ms sinds epoch). */
  tot: number;
  aantal: number;
}

export class Venstertel {
  private readonly vensters = new Map<string, Venster>();

  constructor(
    private readonly max: number,
    private readonly vensterMs: number,
    /** Boven dit aantal sleutels worden verlopen vensters opgeruimd; zonder dat groeit de map met
     *  elke gebruiker die ooit langskwam. */
    private readonly opruimenVanaf = 500,
  ) {}

  /** Telt deze gebeurtenis mee, of zit de sleutel over zijn grens? */
  mag(sleutel: string, nu: number = Date.now()): boolean {
    const venster = this.vensters.get(sleutel);
    if (!venster || nu > venster.tot) {
      if (this.vensters.size >= this.opruimenVanaf) {
        for (const [k, v] of this.vensters) if (nu > v.tot) this.vensters.delete(k);
      }
      this.vensters.set(sleutel, { tot: nu + this.vensterMs, aantal: 1 });
      return true;
    }
    venster.aantal += 1;
    return venster.aantal <= this.max;
  }

  /** Alleen voor tests: hoeveel sleutels staan er nog. */
  get omvang(): number {
    return this.vensters.size;
  }
}
