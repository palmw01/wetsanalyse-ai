"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { foutTekst, maakWerkgebied, voegBronToe } from "@/lib/api";
import { bepalingenVanOverzicht } from "@/lib/overzicht";
import type { Overzicht } from "@/lib/types";

const hoofdletter = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** *Maak hier een werkgebied van* onder een overzicht (spoor D, fase A).
 *
 *  Het overzicht is het eerste voorstel van Lex: de bepalingen staan voorgeselecteerd, de analist vinkt
 *  uit wat er niet bij hoort. Aanmaken legt het werkgebied vast met die bepalingen als *analyseren*;
 *  daarna staat de werkplek in dat werkgebied, waar Lex verder kan zoeken. Een bepaling die de api niet
 *  kan opnemen (niet in de graaf), staat daarna in de melding – nooit stil weg. */
export function WerkgebiedUitOverzicht({ overzicht, onKlaar, onSluit }: {
  overzicht: Overzicht;
  /** Het werkgebied staat er; `mislukt` zijn de bepalingen die niet konden worden opgenomen. */
  onKlaar: (werkgebiedId: string, mislukt: string[]) => void;
  onSluit: () => void;
}) {
  const bepalingen = useMemo(() => bepalingenVanOverzicht(overzicht), [overzicht]);
  const [naam, setNaam] = useState(hoofdletter(overzicht.gevraagd));
  const [vraag, setVraag] = useState(`Welke bepalingen gaan over ${overzicht.gevraagd}?`);
  const [gekozen, setGekozen] = useState<Set<string>>(() => new Set(bepalingen.map((b) => b.iri)));
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);

  function wissel(iri: string) {
    setGekozen((g) => {
      const nieuw = new Set(g);
      if (nieuw.has(iri)) nieuw.delete(iri);
      else nieuw.add(iri);
      return nieuw;
    });
  }

  async function maak(e: React.FormEvent) {
    e.preventDefault();
    if (bezig || !naam.trim()) return;
    setBezig(true);
    setFout(null);
    try {
      let wg = await maakWerkgebied({ naam: naam.trim(), analysevraag: vraag.trim() });
      const mislukt: string[] = [];
      for (const b of bepalingen.filter((x) => gekozen.has(x.iri))) {
        try {
          wg = (await voegBronToe(wg.id, { bron_iri: b.iri, rol: "analyseren", verwachte_revisie: wg.revisie,
            reden: "Uit het overzicht van Lex." })).werkgebied;
        } catch {
          mislukt.push(b.naam);
        }
      }
      onKlaar(wg.id, mislukt);
    } catch (err) {
      setFout(foutTekst(err, "Het werkgebied kon niet worden aangemaakt."));
      setBezig(false);
    }
  }

  return (
    <Dialog label="Werkgebied maken uit het overzicht" variant="compact" onSluit={onSluit}>
      <form onSubmit={maak} className="flex min-h-0 flex-1 flex-col">
        <div className="shrink-0 border-b border-line px-5 py-3.5">
          <h2 className="font-display text-base font-semibold text-lint">Maak hier een werkgebied van</h2>
          <p className="mt-0.5 text-xs text-muted">
            De bepalingen uit het overzicht worden de bronnen om te analyseren. Vink uit wat er niet bij hoort; Lex
            kan daarna verder zoeken.
          </p>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <Field label="Naam" required>
            <Input value={naam} onChange={(e) => setNaam(e.target.value)} maxLength={200} required />
          </Field>
          <Field label="Analysevraag" hint="Lex zoekt hier ook vanuit">
            <Textarea value={vraag} onChange={(e) => setVraag(e.target.value)} rows={2} maxLength={4000} />
          </Field>
          <fieldset>
            <legend className="mb-1 text-sm font-medium text-ink">
              Bepalingen ({gekozen.size} van {bepalingen.length})
            </legend>
            <ul className="max-h-64 space-y-1 overflow-y-auto">
              {bepalingen.map((b) => (
                <li key={b.iri}>
                  <label className="flex items-center gap-2 text-sm text-ink">
                    <input type="checkbox" className="focus-ring accent-lint" checked={gekozen.has(b.iri)}
                      onChange={() => wissel(b.iri)} />
                    {b.naam}
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
          {fout && <Melding type="fout" compact>{fout}</Melding>}
        </div>
        <div className="shrink-0 border-t border-line px-5 py-3">
          <ButtonRow>
            <Button type="button" variant="secondary" onClick={onSluit} disabled={bezig}>Annuleren</Button>
            <Button type="submit" disabled={bezig || !naam.trim()}>
              {bezig ? "Aanmaken…" : "Werkgebied maken"}
            </Button>
          </ButtonRow>
        </div>
      </form>
    </Dialog>
  );
}
