"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Input } from "@/components/ui/Field";
import { OordeelKeuze, OordeelLabel } from "@/components/werkgebieden/Voorbeelden";
import { Melding } from "@/components/ui/Melding";
import {
  VERGELIJKING_LABEL, aandachtTekst, herkomstLabel, isDefinitie, voorstelTekst, type Verouderd,
} from "@/lib/kaartVoorstel";
import type { KaartVoorstel, TekstWaarde, VoorbeeldOordeel } from "@/lib/types";

const TINT = {
  groen: "border-l-aandacht-groen-rand bg-aandacht-groen-bg/40",
  geel: "border-l-aandacht-geel-rand bg-aandacht-geel-bg/40",
} as const;

/** Eén voorstel van Lex, onder het veld waar het bij hoort. Niets gebeurt vanzelf: *Overnemen* zet het in
 *  het begrip (een nieuwe revisie), *Aanpassen* eerst in een eigen veld, *Afwijzen* vraagt een reden. Is
 *  de definitie veranderd sinds Lex het voorstelde, dan staan toen, nu en het voorstel naast elkaar en
 *  neemt de kaart niets over zonder dat de analist het opnieuw kiest. */
export function KaartVoorstelKaart({ v, verouderd, onbewaard, geaccordeerd, onOvernemen, onAfwijzen }: {
  v: KaartVoorstel;
  verouderd: Verouderd | null;
  onbewaard: boolean;
  geaccordeerd: boolean;
  onOvernemen: (extra: { aanpassing?: string; oordeel?: VoorbeeldOordeel; nu_gezien?: string }) => Promise<boolean>;
  onAfwijzen: (reden: string) => Promise<boolean>;
}) {
  const [stand, setStand] = useState<"rust" | "aanpassen" | "afwijzen">("rust");
  const [tekst, setTekst] = useState(voorstelTekst(v));
  const [oordeel, setOordeel] = useState<VoorbeeldOordeel | undefined>((v.waarde as TekstWaarde).oordeel);
  const [reden, setReden] = useState("");
  const [bezig, setBezig] = useState(false);
  const w = v.waarde;
  const isVerouderd = !!verouderd || !!v.verouderd;
  const uit = onbewaard || bezig;
  // Wat er nu staat, zoals de analist het naast het voorstel ziet; meegestuurd maakt het vervangen bewust.
  const nuTekst = verouderd?.nu ?? v.nu?.definitie ?? "";
  const bewust = isVerouderd ? { nu_gezien: nuTekst } : {};

  async function doe(actie: () => Promise<boolean>) {
    setBezig(true);
    const gelukt = await actie();
    setBezig(false);
    if (gelukt) setStand("rust");
  }

  return (
    <section
      aria-label={`Voorstel van Lex: ${voorstelTekst(v).slice(0, 80)}`}
      className={`space-y-2 rounded-kaart border border-line border-l-4 p-3 text-sm ${TINT[v.aandacht]}`}
      data-voorstel={v.id}
    >
      <p className="text-xs font-medium text-ink">
        Voorstel van Lex · <span className="font-normal text-muted">{herkomstLabel(v)}</span>
      </p>

      {isVerouderd ? (
        <div className="space-y-1.5" aria-label="Vergelijking">
          <p className="text-xs text-aandacht-geel-tekst">
            De definitie veranderde nadat Lex dit voorstelde. Er wordt niets overschreven: vergelijk en kies opnieuw.
          </p>
          <dl className="grid gap-1 text-xs sm:grid-cols-[6rem_minmax(0,1fr)]">
            <dt className="text-muted">Toen</dt>
            <dd className="text-ink">{(verouderd?.toen ?? v.basis.definitie) || <em>geen definitie</em>}</dd>
            <dt className="text-muted">Nu</dt>
            <dd className="text-ink">{nuTekst || <em>geen definitie</em>}</dd>
            <dt className="text-muted">Voorstel</dt>
            <dd className="text-ink">{voorstelTekst(v)}</dd>
          </dl>
        </div>
      ) : (
        <blockquote className="whitespace-pre-line text-ink">{voorstelTekst(v)}</blockquote>
      )}

      {!isDefinitie(v) && (w as TekstWaarde).oordeel && (
        <p className="flex items-center gap-1.5 text-xs text-muted">
          Verwacht oordeel: <OordeelLabel oordeel={(w as TekstWaarde).oordeel!} />
        </p>
      )}
      {!isDefinitie(v) && (w as TekstWaarde).vergelijking && (
        <p className="text-xs text-muted">Uitkomst: {VERGELIJKING_LABEL[(w as TekstWaarde).vergelijking!]}</p>
      )}
      {v.motivatie && <p className="text-xs text-muted">{v.motivatie}</p>}
      {w.fragmenten && w.fragmenten.length > 0 && (
        <details className="text-xs">
          <summary className="focus-ring cursor-pointer rounded text-muted">
            Rust op {w.fragmenten.length === 1 ? "1 fragment" : `${w.fragmenten.length} fragmenten`} uit de bron
          </summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink">
            {w.fragmenten.map((f) => <li key={f.id}>“{f.tekst}”</li>)}
          </ul>
        </details>
      )}
      {v.aandachtspunten.length > 0 && (
        <ul className="space-y-0.5 text-xs text-aandacht-geel-tekst" aria-label="Aandachtspunten">
          {v.aandachtspunten.map((a) => <li key={a}>{aandachtTekst(a)}</li>)}
        </ul>
      )}

      {stand === "aanpassen" && (
        <div className="space-y-2">
          {isDefinitie(v) ? (
            <AutoTextarea value={tekst} onChange={(e) => setTekst(e.target.value)} rows={3} aria-label="Aangepaste definitie" />
          ) : (
            <AutoTextarea value={tekst} onChange={(e) => setTekst(e.target.value)} rows={2} aria-label="Aangepaste tekst" />
          )}
          {v.veld === "voorbeelden" && (
            <OordeelKeuze waarde={oordeel ?? "wel"} onKies={setOordeel} label="Verwacht oordeel" naam={`oordeel-voorstel-${v.id}`} />
          )}
          {isDefinitie(v) && tekst.trim() !== v.waarde.definitie && (
            <p className="text-xs text-muted">Een aangepaste definitie wordt “geformuleerd”, door de analist.</p>
          )}
        </div>
      )}
      {stand === "afwijzen" && (
        <Input value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom niet? (optioneel)"
          aria-label="Reden van afwijzen" autoFocus
          onKeyDown={(e) => {
            // In het formulier van de kaart: Enter mag het begrip niet opslaan.
            if (e.key === "Enter") { e.preventDefault(); void doe(() => onAfwijzen(reden)); }
            if (e.key === "Escape") { e.preventDefault(); setStand("rust"); }
          }} />
      )}

      {onbewaard && <p className="text-xs text-muted">Sla eerst je wijzigingen op; overnemen werkt op het bewaarde begrip.</p>}
      {geaccordeerd && !onbewaard && stand !== "afwijzen" && (
        <p className="text-xs text-muted">Het begrip is geaccordeerd; overnemen maakt het weer een concept.</p>
      )}

      <div className="flex flex-col gap-1.5 sm:flex-row sm:flex-wrap">
        {stand === "rust" && (
          <>
            <Button type="button" size="sm" className="w-full sm:w-auto" disabled={uit} onClick={() => void doe(() => onOvernemen(bewust))}>
              {isVerouderd ? "Toch overnemen" : "Overnemen"}
            </Button>
            <Button type="button" size="sm" variant="secondary" className="w-full sm:w-auto" disabled={uit} onClick={() => setStand("aanpassen")}>
              Aanpassen
            </Button>
            <Button type="button" size="sm" variant="ghost" className="w-full sm:w-auto" disabled={bezig} onClick={() => setStand("afwijzen")}>
              Afwijzen
            </Button>
          </>
        )}
        {stand === "aanpassen" && (
          <>
            <Button type="button" size="sm" className="w-full sm:w-auto" disabled={uit || !tekst.trim()}
              onClick={() => void doe(() => onOvernemen({ ...bewust, aanpassing: tekst.trim(), ...(oordeel ? { oordeel } : {}) }))}>
              Aangepast overnemen
            </Button>
            <Button type="button" size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => setStand("rust")}>Terug</Button>
          </>
        )}
        {stand === "afwijzen" && (
          <>
            <Button type="button" size="sm" variant="secondary" className="w-full sm:w-auto" disabled={bezig} onClick={() => void doe(() => onAfwijzen(reden))}>
              Afwijzen
            </Button>
            <Button type="button" size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => setStand("rust")}>Terug</Button>
          </>
        )}
      </div>
      {isVerouderd && stand === "rust" && (
        <Melding type="uitleg" compact>“Toch overnemen” vervangt de definitie die er nu staat door het voorstel.</Melding>
      )}
    </section>
  );
}
