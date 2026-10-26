"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Sectie } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedProject";
import { foutTekst, isApiError, voegBronToe } from "@/lib/api";
import type { BronBereik, BronRol, Werkgebied } from "@/lib/types";
import { ROL_LABEL, ROL_UITLEG, bronInvoer, isAlOpgenomen } from "@/lib/werkgebied";

const ROLLEN: BronRol[] = ["analyseren", "context"];

/** Een bepaling opnemen in het werkgebied: regeling + artikel (+ lid) of een bron-IRI, met rol, bereik en
 *  reden. De api zoekt de bepaling op in de actuele wettekst. Op de tab Bronnen in een venster. */
export function BronOpnemen({ wg, muteer, onKlaar }: { wg: Werkgebied; muteer: Mutatie; onKlaar?: () => void }) {
  const [regeling, setRegeling] = useState("");
  const [artikel, setArtikel] = useState("");
  const [lid, setLid] = useState("");
  const [rol, setRol] = useState<BronRol>("analyseren");
  const [bereik, setBereik] = useState<BronBereik>("onderliggend");
  const [reden, setReden] = useState("");
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);

  async function voegToe(e: React.FormEvent) {
    e.preventDefault();
    if (bezig) return;
    const gelezen = bronInvoer({ regeling, artikel, lid });
    if ("fout" in gelezen) {
      setFout(gelezen.fout);
      return;
    }
    setFout(null);
    setBezig(true);
    let alAanwezig = false;
    const gelukt = await muteer(
      async (r) => {
        const uit = await voegBronToe(wg.id, { ...gelezen.invoer, rol, bereik, reden, verwachte_revisie: r });
        alAanwezig = !uit.nieuw;
        return uit.werkgebied;
      },
      {
        gelukt: () => (alAanwezig ? "Deze bepaling stond er al in, met dezelfde rol en hetzelfde bereik." : "Opgenomen."),
        // Wat over déze invoer gaat staat bij het formulier: een andere selectie van dezelfde bron,
        // een bepaling die de graaf niet kent (422). De rest meldt de pagina boven de tabs.
        opFout: (err) => {
          if (isAlOpgenomen(err)) {
            setFout("Deze bepaling staat al in het werkgebied, met een andere rol of een ander bereik. Pas die selectie aan.");
            return true;
          }
          if (isApiError(err) && err.status === 422) {
            setFout(foutTekst(err));
            return true;
          }
          return false;
        },
      },
    );
    setBezig(false);
    if (gelukt) {
      setRegeling("");
      setArtikel("");
      setLid("");
      setReden("");
      onKlaar?.();
    }
  }

  return (
    <Sectie titel="Bepaling opnemen"
      toelichting="Regeling als BWB-id (bijvoorbeeld BWBR0004770) met artikel en eventueel lid, of een bron-IRI uit de graaf. De api zoekt de bepaling op in de actuele wettekst.">
      <form onSubmit={voegToe} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-[2fr_1fr_1fr]">
          <Field label="Regeling of bron-IRI" required>
            <Input value={regeling} onChange={(e) => setRegeling(e.target.value)} placeholder="BWBR0004770" required />
          </Field>
          <Field label="Artikel">
            <Input value={artikel} onChange={(e) => setArtikel(e.target.value)} placeholder="9" />
          </Field>
          <Field label="Lid" hint="optioneel">
            <Input value={lid} onChange={(e) => setLid(e.target.value)} placeholder="2" />
          </Field>
        </div>
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-ink">Rol</legend>
          <div className="space-y-1.5">
            {ROLLEN.map((r) => (
              <label key={r} className="flex items-start gap-2 text-sm text-ink">
                <input
                  type="radio"
                  name="rol"
                  value={r}
                  checked={rol === r}
                  onChange={() => setRol(r)}
                  className="focus-ring mt-1 accent-lint"
                />
                <span>
                  {ROL_LABEL[r]} <span className="text-xs text-muted">– {ROL_UITLEG[r]}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <Field label="Bereik">
          <Select value={bereik} onChange={(e) => setBereik(e.target.value as BronBereik)}>
            <option value="onderliggend">De bepaling met alles eronder (standaard; bij een artikel: alle leden)</option>
            <option value="node">Alleen deze bepaling zelf</option>
          </Select>
        </Field>
        <Field label="Reden" hint="optioneel">
          <Textarea value={reden} onChange={(e) => setReden(e.target.value)} rows={2} maxLength={2000} />
        </Field>
        {fout && (
          <Melding type="fout" compact>
            {fout}
          </Melding>
        )}
        <ButtonRow align="start">
          <Button type="submit" disabled={bezig || !regeling.trim()}>
            {bezig ? "Opzoeken…" : "Opnemen"}
          </Button>
        </ButtonRow>
      </form>
    </Sectie>
  );
}
