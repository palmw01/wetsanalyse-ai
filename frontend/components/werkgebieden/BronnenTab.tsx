"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { BronKandidaten } from "@/components/werkgebieden/BronKandidaten";
import { Deelvragen } from "@/components/werkgebieden/Deelvragen";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedClient";
import { foutTekst, isApiError, verwijderBron, voegBronToe, wijzigBron } from "@/lib/api";
import type { BronBereik, BronRol, Bronselectie, Werkgebied } from "@/lib/types";
import {
  BEREIK_LABEL, ROL_LABEL, ROL_UITLEG, annotatieHref, bronInvoer, isAlOpgenomen,
} from "@/lib/werkgebied";

const ROLLEN: BronRol[] = ["analyseren", "context"];

/** De bronselecties: welke bepalingen bij dit werkgebied horen, met rol, bereik en reden.
 *
 *  Een selectie is een eigen object, geen kopie van de bron: dezelfde bepaling kan in een ander
 *  werkgebied staan met een andere rol, en weghalen laat de bepaling en haar annotaties staan. */
export function BronnenTab({ wg, muteer, onHerlaad }: { wg: Werkgebied; muteer: Mutatie; onHerlaad: () => void }) {
  const labels = useMemo(() => new Map(wg.bronnen.map((b) => [b.bron_iri, b.label || b.bron_iri])), [wg.bronnen]);
  return (
    <div className="space-y-6">
      {/* Optioneel: de analysevraag in deelvragen; Lex zoekt daarna ook per deelvraag. */}
      <Deelvragen wg={wg} muteer={muteer} onHerlaad={onHerlaad} />
      {/* Lex zoekt bepalingen die erbij kunnen horen (fase A); opnemen maakt een selectie hieronder. */}
      <BronKandidaten id={wg.id} labels={labels} onGewijzigd={onHerlaad} />
      {wg.bronnen.length === 0 ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          Nog geen bronnen. Neem hieronder een bepaling op.
        </p>
      ) : (
        <ul className="space-y-3" aria-label="Bronselecties">
          {wg.bronnen.map((s) => (
            <SelectieRij key={s.id} wgId={wg.id} selectie={s} muteer={muteer} />
          ))}
        </ul>
      )}
      <BronToevoegen wg={wg} muteer={muteer} />
    </div>
  );
}

function SelectieRij({ wgId, selectie: s, muteer }: { wgId: string; selectie: Bronselectie; muteer: Mutatie }) {
  return (
    <li className="rounded-button border border-line bg-paper p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="font-display text-sm font-semibold text-lint">
            <Link href={annotatieHref(s.bron_iri)} className="focus-ring rounded hover:underline">
              {s.label || s.bron_iri}
            </Link>
          </p>
          <p className="text-xs text-muted">
            {s.bwb_id} · {BEREIK_LABEL[s.bereik]} · opgenomen door {s.toegevoegd_door}
          </p>
          {s.reden && <p className="mt-1 whitespace-pre-line text-sm text-ink">{s.reden}</p>}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="sr-only" htmlFor={`rol-${s.id}`}>
            Rol van {s.label}
          </label>
          <Select
            id={`rol-${s.id}`}
            value={s.rol}
            className="sm:w-44"
            onChange={(e) => {
              const rol = e.target.value as BronRol;
              void muteer((r) => wijzigBron(wgId, s.id, { verwachte_revisie: r, rol }), {
                gelukt: `Rol gewijzigd naar ${ROL_LABEL[rol].toLowerCase()}.`,
              });
            }}
          >
            {ROLLEN.map((r) => (
              <option key={r} value={r}>
                {ROL_LABEL[r]}
              </option>
            ))}
          </Select>
          <BevestigKnop
            bevestigTekst="Weghalen?"
            titel="Haalt de bepaling uit dit werkgebied; de bepaling en haar annotaties blijven bestaan."
            onBevestig={async () => {
              await muteer((r) => verwijderBron(wgId, s.id, r), {
                gelukt: "Uit het werkgebied gehaald. De annotaties van de bepaling blijven staan.",
              });
            }}
            className="focus-ring inline-flex min-h-[40px] items-center justify-center rounded-button border border-line px-3 py-1.5 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink coarse:min-h-[48px]"
            bevestigClassName="border-fout/40 text-fout"
          >
            Weghalen
          </BevestigKnop>
        </div>
      </div>
    </li>
  );
}

function BronToevoegen({ wg, muteer }: { wg: Werkgebied; muteer: Mutatie }) {
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
    }
  }

  return (
    <form onSubmit={voegToe} className="space-y-4 rounded-button border border-line bg-paper p-4">
      <div>
        <h2 className="font-display text-base font-semibold text-lint">Bepaling opnemen</h2>
        <p className="mt-0.5 text-xs text-muted">
          Regeling als BWB-id (bijvoorbeeld BWBR0004770) met artikel en eventueel lid, of een bron-IRI uit
          de graaf. De api zoekt de bepaling op in de actuele wettekst.
        </p>
      </div>
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
  );
}
