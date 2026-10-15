"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { foutTekst, lijstWerkgebieden, maakWerkgebied } from "@/lib/api";
import type { WerkgebiedSamenvatting } from "@/lib/types";
import { STATUS_LABEL } from "@/lib/werkgebied";

const datum = (iso: string) =>
  new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });

/** Het overzicht van de werkgebieden: benoemde analyses met hun bronselecties, gedeeld tussen
 *  analisten zoals de annotaties. Een nieuw werkgebied begint leeg; bronnen voeg je toe op de
 *  pagina van het werkgebied zelf. */
export function WerkgebiedenClient() {
  const router = useRouter();
  const [lijst, setLijst] = useState<WerkgebiedSamenvatting[] | null>(null);
  const [gearchiveerd, setGearchiveerd] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [nieuwOpen, setNieuwOpen] = useState(false);
  const [naam, setNaam] = useState("");
  const [vraag, setVraag] = useState("");
  const [afbakening, setAfbakening] = useState("");
  const [bezig, setBezig] = useState(false);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setLijst(await lijstWerkgebieden(gearchiveerd));
    } catch (e) {
      setFout(foutTekst(e, "De werkgebieden konden niet worden geladen."));
      setLijst([]);
    }
  }, [gearchiveerd]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  async function maak(e: React.FormEvent) {
    e.preventDefault();
    if (!naam.trim() || bezig) return;
    setBezig(true);
    setFout(null);
    try {
      const wg = await maakWerkgebied({ naam: naam.trim(), analysevraag: vraag, afbakening });
      router.push(`/werkgebieden/${encodeURIComponent(wg.id)}`);
    } catch (e) {
      setFout(foutTekst(e, "Het werkgebied kon niet worden aangemaakt."));
      setBezig(false);
    }
  }

  return (
    <WerkgebiedSchil titel="Werkgebieden" onFout={setFout}>
      <header className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold text-lint">Werkgebieden</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Een werkgebied brengt bepalingen samen rond één analysevraag. De bepalingen en hun
            annotaties blijven gedeeld; een werkgebied legt alleen vast welke erbij horen en waarom.
          </p>
        </div>
        {!nieuwOpen && (
          <Button className="w-full sm:w-auto" onClick={() => setNieuwOpen(true)}>
            Nieuw werkgebied
          </Button>
        )}
      </header>

      {nieuwOpen && (
        <form onSubmit={maak} className="mb-6 space-y-4 rounded-button border border-line bg-paper p-4">
          <h2 className="font-display text-base font-semibold text-lint">Nieuw werkgebied</h2>
          <Field label="Naam" required>
            <Input value={naam} onChange={(e) => setNaam(e.target.value)} maxLength={200} autoFocus required />
          </Field>
          <Field label="Analysevraag" hint="optioneel">
            <Textarea value={vraag} onChange={(e) => setVraag(e.target.value)} rows={2} maxLength={4000} />
          </Field>
          <Field label="Afbakening" hint="optioneel">
            <Textarea value={afbakening} onChange={(e) => setAfbakening(e.target.value)} rows={2} maxLength={4000} />
          </Field>
          <ButtonRow>
            <Button type="submit" disabled={!naam.trim() || bezig}>
              {bezig ? "Bezig…" : "Aanmaken"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setNieuwOpen(false)}>
              Annuleren
            </Button>
          </ButtonRow>
        </form>
      )}

      <label className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted">
        <input
          type="checkbox"
          checked={gearchiveerd}
          onChange={(e) => setGearchiveerd(e.target.checked)}
          className="focus-ring h-3.5 w-3.5 accent-lint"
        />
        Gearchiveerde werkgebieden
      </label>

      {fout && (
        <Melding type="fout" className="mb-4">
          {fout}
        </Melding>
      )}

      {lijst === null ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {[1, 2].map((i) => (
            <div key={i} className="space-y-3 rounded-button border border-line bg-paper p-4">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-64" />
            </div>
          ))}
        </div>
      ) : lijst.length === 0 ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          {gearchiveerd ? "Geen gearchiveerde werkgebieden." : "Nog geen werkgebieden. Begin met een nieuw werkgebied."}
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {lijst.map((wg) => (
            <article
              key={wg.id}
              className="flex flex-col gap-2 rounded-button border border-line bg-paper p-4 transition-shadow hover:shadow-kaart"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="min-w-0 truncate font-display text-sm font-semibold text-lint">
                  <Link href={`/werkgebieden/${encodeURIComponent(wg.id)}`} className="focus-ring rounded hover:underline">
                    {wg.naam}
                  </Link>
                </h2>
                <span className="inline-flex shrink-0 items-center rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-muted">
                  {STATUS_LABEL[wg.status]}
                </span>
              </div>
              {wg.analysevraag && <p className="line-clamp-2 text-xs text-ink">{wg.analysevraag}</p>}
              <p className="text-xs text-muted">
                {wg.aantal_bronnen === 1 ? "1 bron" : `${wg.aantal_bronnen ?? 0} bronnen`} · gewijzigd{" "}
                {datum(wg.gewijzigd)}
              </p>
            </article>
          ))}
        </div>
      )}
    </WerkgebiedSchil>
  );
}
