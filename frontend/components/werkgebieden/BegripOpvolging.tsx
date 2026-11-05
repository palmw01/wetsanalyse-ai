"use client";

import { useEffect, useState } from "react";

import { BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Dialog } from "@/components/ui/Dialog";
import { Input, Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import {
  combineerBegrippen, combineerMetGeneriek, foutTekst, geefGeneriekNieuweBetekenis, geefNieuweBetekenis, zoekBegrippen,
} from "@/lib/api";
import type { BegripOverzichtRij } from "@/lib/begrippenOverzicht";
import type { Begrip, BegripSamenvatting } from "@/lib/types";
import { isRevisieConflict } from "@/lib/werkgebied";

/** Nieuwe betekenis en combineren (fase F2), uit het menu van het begrip. Beide leveren een ander begrip op en maken
 *  het ene `vervangen`: alleen te lezen, vindbaar, en terug te halen door de opvolger te verwijderen. De vergelijking
 *  staat vooraf in beeld, zodat de analist ziet welke definitie blijft; de reden is verplicht. */
export function BegripOpvolging({ soort, id, begrip, kandidaten, onSluit, onKlaar }: {
  soort: "nieuw" | "combineren" | "generiek";
  id: string;
  begrip: Begrip;
  kandidaten: readonly BegripSamenvatting[];
  onSluit: () => void;
  onKlaar: (begripId: string) => void;
}) {
  const [fout, setFout] = useState<string | null>(null);
  const [reden, setReden] = useState("");
  const [ander, setAnder] = useState("");
  const [blijft, setBlijft] = useState<"dit" | "ander">("dit");
  const [bezig, setBezig] = useState(false);
  const a = kandidaten.find((b) => b.id === ander);
  // Combineren met een generiek begrip (ADR-006): dat blijft altijd, en zijn inhoud verandert niet.
  const [generiek, setGeneriek] = useState<BegripOverzichtRij[]>([]);
  useEffect(() => {
    if (soort !== "generiek") return;
    let levend = true;
    zoekBegrippen(new URLSearchParams({ kader: "generiek", status: "geaccordeerd" }))
      .then((u) => levend && setGeneriek(u.resultaten))
      .catch((e) => levend && setFout(foutTekst(e, "De generieke begrippen konden niet worden geladen.")));
    return () => { levend = false; };
  }, [soort]);
  const g = generiek.find((b) => b.id === ander);
  const titel = soort === "nieuw" ? "Nieuwe betekenis" : soort === "generiek" ? "Combineren met generiek begrip" : "Combineren";

  async function voer(actie: () => Promise<Begrip>) {
    setBezig(true);
    try {
      const b = await actie();
      onKlaar(b.id);
    } catch (e) {
      setFout(isRevisieConflict(e) ? "Een van beide begrippen veranderde net; laad opnieuw en kijk of het nog klopt."
        : foutTekst(e));
    } finally {
      setBezig(false);
    }
  }

  return (
    <Dialog label={titel} variant="compact" onSluit={onSluit}>
      <div className="flex min-h-0 flex-1 flex-col" data-opvolging={soort}>
        <div className="shrink-0 border-b border-line px-5 py-3.5">
          <p className="text-xs text-muted">{titel}</p>
          <h2 className="font-display text-base font-semibold text-lint">{begrip.inhoud.naam}</h2>
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {fout && <Melding type="fout" compact>{fout}</Melding>}
          {soort === "nieuw" ? (
            <form aria-label="Nieuwe betekenis" className="space-y-2" onSubmit={(e) => {
              e.preventDefault();
              const body = { verwachte_revisie: begrip.revisie, reden: reden.trim() };
              if (reden.trim()) void voer(() => id ? geefNieuweBetekenis(id, begrip.id, body) : geefGeneriekNieuweBetekenis(begrip.id, body));
            }}>
              <p className="text-xs text-muted">
                Een andere betekenis is een nieuw begrip. De opvolger krijgt deze inhoud en de passages (opnieuw ter
                beoordeling); dit begrip wordt vervangen en blijft te lezen. Een tekstuele verbetering doe je gewoon met Bewerken.
              </p>
              <Input autoFocus value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom de betekenis verandert"
                aria-label="Reden voor de nieuwe betekenis" maxLength={2000} />
              <BewerkVoet submit onAnnuleer={onSluit} bezig={bezig} gewijzigd={!!reden.trim()} opslaanTekst="Maak opvolger" />
            </form>
          ) : soort === "generiek" ? (
            <form aria-label="Combineren met generiek begrip" className="space-y-2" onSubmit={(e) => {
              e.preventDefault();
              if (!g || !reden.trim()) return;
              void voer(() => combineerMetGeneriek(id, begrip.id, { verwachte_revisie: begrip.revisie, generiek_id: g.id, reden: reden.trim() }));
            }}>
              <Select value={ander} onChange={(e) => setAnder(e.target.value)} aria-label="Generiek begrip">
                <option value="">Kies een generiek begrip…</option>
                {generiek.map((b) => <option key={b.id} value={b.id}>{b.naam}</option>)}
              </Select>
              {g && (
                <div className="grid gap-2 text-xs sm:grid-cols-2">
                  <p className="rounded-knop border border-line p-2"><span className="font-medium text-ink">{begrip.inhoud.naam}</span>
                    <span className="mt-1 block text-muted">{begrip.inhoud.definitie || "Nog geen definitie."}</span></p>
                  <p className="rounded-knop border border-lint p-2"><span className="font-medium text-ink">{g.naam}</span> blijft
                    <span className="mt-1 block text-muted">{g.definitie || "Nog geen definitie."}</span></p>
                </div>
              )}
              <p className="text-xs text-muted">
                Dit begrip wordt vervangen en blijft vindbaar. Zijn passages gaan mee (opnieuw ter beoordeling); de inhoud van het
                generieke begrip verandert niet.
              </p>
              <Input value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom dit hetzelfde begrip is"
                aria-label="Reden om te combineren" maxLength={2000} />
              <BewerkVoet submit onAnnuleer={onSluit} bezig={bezig} gewijzigd={!!g && !!reden.trim()} opslaanTekst="Combineren" />
            </form>
          ) : (
            <form aria-label="Combineren" className="space-y-2" onSubmit={(e) => {
              e.preventDefault();
              if (!a || !reden.trim()) return;
              void voer(() => blijft === "dit"
                ? combineerBegrippen(id, begrip.id, { verwachte_revisie: begrip.revisie, ander_begrip_id: a.id, ander_revisie: a.revisie, reden: reden.trim() })
                : combineerBegrippen(id, a.id, { verwachte_revisie: a.revisie, ander_begrip_id: begrip.id, ander_revisie: begrip.revisie, reden: reden.trim() }));
            }}>
              <Select value={ander} onChange={(e) => setAnder(e.target.value)} aria-label="Combineren met">
                <option value="">Kies een begrip…</option>
                {kandidaten.map((b) => <option key={b.id} value={b.id}>{b.inhoud.naam}</option>)}
              </Select>
              {a && (
                <>
                  <div role="radiogroup" aria-label="Welk begrip blijft" className="grid gap-2 sm:grid-cols-2">
                    {([["dit", begrip.inhoud], ["ander", a.inhoud]] as const).map(([w, inh]) => (
                      <label key={w} className={`cursor-pointer rounded-knop border p-2 text-xs ${blijft === w ? "border-lint" : "border-line"}`}>
                        <input type="radio" name="blijft" className="focus-ring mr-1.5 accent-lint" checked={blijft === w}
                          onChange={() => setBlijft(w)} />
                        <span className="font-medium text-ink">{inh.naam}</span> blijft
                        <span className="mt-1 block text-muted">{inh.definitie || "Nog geen definitie."}</span>
                      </label>
                    ))}
                  </div>
                  <p className="text-xs text-muted">
                    Het begrip dat blijft krijgt de passages van het andere (opnieuw ter beoordeling) en diens naam als
                    alternatieve term; het andere wordt vervangen.
                  </p>
                </>
              )}
              <Input value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom dit één begrip is"
                aria-label="Reden om te combineren" maxLength={2000} />
              <BewerkVoet submit onAnnuleer={onSluit} bezig={bezig} gewijzigd={!!a && !!reden.trim()} opslaanTekst="Combineren" />
            </form>
          )}
        </div>
      </div>
    </Dialog>
  );
}
