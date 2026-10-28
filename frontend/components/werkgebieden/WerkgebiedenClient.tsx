"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedKaart } from "@/components/werkgebieden/WerkgebiedKaart";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { foutTekst, lijstWerkgebieden, verwijderWerkgebied } from "@/lib/api";
import type { WerkgebiedSamenvatting } from "@/lib/types";
import { metSpoor } from "@/lib/uiSpoor";
import { STATUS_LABEL, isRevisieConflict, WERKGEBIED_START_URL } from "@/lib/werkgebied";
import { STATUS_FILTERS, metStatus, perStatus, statusUitParam, zoek, type StatusFilter } from "@/lib/werkgebiedOverzicht";

/** Het overzicht van de werkgebieden, in de lijn van de annotaties: een statusfilter met tellers,
 *  *Door mij bewerkt* en zoeken, en kaarten in twee kolommen. Een werkgebied stel je samen met Lex in het
 *  gesprek (activiteit 1, de vraagkaarten); hier staat daarom geen formulier, maar een link naar de
 *  werkplek met de vraag klaar. */
export function WerkgebiedenClient() {
  const router = useRouter();
  const params = useSearchParams();
  const [lijst, setLijst] = useState<WerkgebiedSamenvatting[] | null>(null);
  const [status, setStatus] = useState<StatusFilter>(() => statusUitParam(params.get("status")));
  const [mijn, setMijn] = useState(false);
  const [term, setTerm] = useState("");
  const [fout, setFout] = useState<string | null>(null);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setLijst(await lijstWerkgebieden({ mijn }));
    } catch (e) {
      setFout(foutTekst(e, "De werkgebieden konden niet worden geladen."));
      setLijst([]);
    }
  }, [mijn]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  function kiesStatus(s: StatusFilter) {
    setStatus(s);
    // `replace`: een filterwissel is geen stap in de geschiedenis.
    router.replace(s === "alle" ? "/werkgebieden" : `/werkgebieden?status=${s}`, { scroll: false });
  }

  /** Echt wissen, zoals een annotatie (`lib/verwijderen.ts`): de kaart gaat meteen weg en komt bij een
   *  fout terug; een 412 laadt de lijst opnieuw. */
  async function verwijder(wg: WerkgebiedSamenvatting) {
    const voor = lijst;
    setLijst((l) => l?.filter((x) => x.id !== wg.id) ?? l);
    setFout(null);
    try {
      await metSpoor("werkgebied_verwijderen", () => verwijderWerkgebied(wg.id, wg.revisie));
    } catch (e) {
      setLijst(voor);
      setFout(foutTekst(e, "Het werkgebied is niet verwijderd."));
      if (isRevisieConflict(e)) await laad();
    }
  }

  const alles = lijst ?? [];
  const aantal = perStatus(alles);
  const getoond = zoek(metStatus(alles, status), term);
  const samenstellen = (
    <Link href={WERKGEBIED_START_URL} className="focus-ring rounded font-medium text-lint underline-offset-2 hover:underline">
      Samenstellen met Lex
    </Link>
  );

  return (
    <WerkgebiedSchil titel="Werkgebieden" onFout={setFout}>
      <header className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold text-lint">Werkgebieden</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Een werkgebied brengt bepalingen samen rond één analysevraag. De bepalingen en hun
            annotaties blijven gedeeld; een werkgebied legt alleen vast welke erbij horen en waarom.
          </p>
        </div>
        <p className="shrink-0 text-sm">{samenstellen}</p>
      </header>

      <OverzichtBalk
        filters={STATUS_FILTERS.map((s) => ({ waarde: s, label: s === "alle" ? "Alle" : STATUS_LABEL[s], aantal: aantal[s] }))}
        gekozen={status}
        onKies={kiesStatus}
        filterLabel="Status"
        mijn={mijn}
        onMijn={setMijn}
        zoekterm={term}
        onZoek={setTerm}
        zoekLabel="Zoeken in werkgebieden"
        placeholder="Zoek op naam of analysevraag"
      />

      {fout && (
        <Melding type="fout" className="mb-4">
          {fout}
        </Melding>
      )}

      {lijst === null ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[1, 2].map((i) => (
            <div key={i} className="space-y-3 rounded-kaart border border-line bg-paper shadow-zacht p-4">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-64" />
            </div>
          ))}
        </div>
      ) : alles.length === 0 && !mijn ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          Nog geen werkgebieden. Vraag Lex in het gesprek om er samen een samen te stellen: {samenstellen}.
        </p>
      ) : getoond.length === 0 ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          Geen werkgebied dat hierop past.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="werkgebieden-overzicht">
          {getoond.map((wg) => <WerkgebiedKaart key={wg.id} wg={wg} onVerwijder={() => verwijder(wg)} />)}
        </div>
      )}
    </WerkgebiedSchil>
  );
}
