"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { BegripOverzichtKaart } from "@/components/begrippen/BegripOverzichtKaart";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { foutTekst, lijstWerkgebieden, verwijderBegrip, zoekBegrippen } from "@/lib/api";
import {
  BEGRIP_STATUSSEN, BEGRIP_STATUS_LABEL, filtersUitParams, paramsVan,
  type BegripOverzichtRij, type BegrippenOverzicht, type OverzichtFilters,
} from "@/lib/begrippenOverzicht";
import { metSpoor } from "@/lib/uiSpoor";
import type { BegripStatus, WerkgebiedSamenvatting } from "@/lib/types";


/** Het overzicht van de begrippen over alle werkgebieden heen (spoor D, fase F4). Een leesingang:
 *  zoeken op naam, alternatieve term of definitie, filteren op status en werkgebied, en doorklikken
 *  naar de kaart in zijn werkgebied – daar gebeurt het werk. De filters staan in de URL, zodat
 *  terugbladeren en delen werken. */
export function BegrippenOverzichtClient() {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const filters = useMemo(() => filtersUitParams(new URLSearchParams(zoekParams.toString())), [zoekParams]);
  const [term, setTerm] = useState(filters.q);
  const [data, setData] = useState<BegrippenOverzicht | null>(null);
  const [werkgebieden, setWerkgebieden] = useState<WerkgebiedSamenvatting[]>([]);
  const [fout, setFout] = useState<string | null>(null);

  function zet(nieuw: OverzichtFilters) {
    const qs = paramsVan(nieuw, "pagina").toString();
    // `replace`: een filter is geen stap in de geschiedenis.
    router.replace(qs ? `${pad}?${qs}` : pad, { scroll: false });
  }

  // Typen zoekt na een korte pauze; elke toetsaanslag een verzoek is onnodig.
  useEffect(() => {
    if (term === filters.q) return;
    const t = setTimeout(() => zet({ ...filters, q: term }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  useEffect(() => {
    let weg = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFout(null);
    zoekBegrippen(paramsVan(filters, "api"))
      .then((d) => { if (!weg) setData(d); })
      .catch((e) => {
        if (weg) return;
        setFout(foutTekst(e, "De begrippen konden niet worden geladen."));
        setData({ resultaten: [], totaal: 0, volgende_offset: null });
      });
    return () => { weg = true; };
  }, [filters]);

  useEffect(() => {
    lijstWerkgebieden().then(setWerkgebieden).catch(() => setWerkgebieden([]));
  }, []);

  /** Echt wissen, zoals een annotatie (`lib/verwijderen.ts`): de rij gaat meteen weg en komt bij een fout
   *  terug. */
  async function verwijder(b: BegripOverzichtRij) {
    const voor = data;
    setData((d) => d && { ...d, resultaten: d.resultaten.filter((x) => x.id !== b.id), totaal: d.totaal - 1 });
    setFout(null);
    try {
      await metSpoor("begrip_verwijderen", () => verwijderBegrip(b.werkgebied_id, b.id, b.revisie));
    } catch (e) {
      setData(voor);
      setFout(foutTekst(e, "Het begrip is niet verwijderd."));
    }
  }

  const telling = data?.per_status;
  const filters_ = [{ waarde: "" as const, label: "Alle",
      aantal: telling ? Object.values(telling).reduce((a, b) => a + (b ?? 0), 0) : undefined },
    ...BEGRIP_STATUSSEN.map((s) => ({ waarde: s, label: BEGRIP_STATUS_LABEL[s], aantal: telling ? telling[s] ?? 0 : undefined }))];

  return (
    <WerkgebiedSchil titel="Begrippen" onFout={setFout}>
      <header className="mb-5">
        <h1 className="font-display text-lg font-semibold text-lint">Begrippen</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          De begrippen uit alle werkgebieden. Een begrip is een analyse-uitkomst, geen wettelijke
          definitie; je werkt eraan op de kaart in zijn werkgebied.
        </p>
      </header>

      <OverzichtBalk<BegripStatus | "">
        filters={filters_}
        gekozen={filters.status}
        onKies={(status) => zet({ ...filters, status })}
        filterLabel="Status"
        mijn={filters.mijn}
        onMijn={(mijn) => zet({ ...filters, mijn })}
        extra={
          // Compact, zonder zichtbaar label: met label paste de balk niet meer op één regel naast het zoekveld.
          <select
            aria-label="Werkgebied"
            value={filters.werkgebied}
            onChange={(e) => zet({ ...filters, werkgebied: e.target.value })}
            className="focus-ring w-full rounded-field border border-line bg-paper px-2 py-1.5 text-xs text-ink coarse:min-h-[44px] sm:w-auto sm:max-w-[10rem]"
          >
            <option value="">Alle werkgebieden</option>
            {werkgebieden.map((w) => (
              <option key={w.id} value={w.id}>{w.naam}</option>
            ))}
          </select>
        }
        zoekterm={term}
        onZoek={setTerm}
        zoekLabel="Zoeken in begrippen"
        placeholder="Zoek op naam, term of definitie"
      />

      {fout && (
        <Melding type="fout" className="mb-4">
          {fout}
        </Melding>
      )}

      {data === null ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[1, 2].map((i) => (
            <div key={i} className="space-y-3 rounded-kaart border border-line bg-paper shadow-zacht p-4">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-64" />
            </div>
          ))}
        </div>
      ) : data.resultaten.length === 0 ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          {filters.q || filters.status || filters.werkgebied || filters.mijn
            ? "Geen begrippen bij deze filters."
            : "Nog geen begrippen. Begrippen ontstaan in een werkgebied, op de tab Begrippen."}
        </p>
      ) : (
        <>
          <p className="mb-2 text-xs text-muted" aria-live="polite">
            {data.totaal === 1 ? "1 begrip" : `${data.totaal} begrippen`}
            {data.resultaten.length < data.totaal ? ` (de eerste ${data.resultaten.length})` : ""}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="begrippen-overzicht">
            {data.resultaten.map((b) => <BegripOverzichtKaart key={b.id} b={b} onVerwijder={() => verwijder(b)} />)}
          </div>
        </>
      )}
    </WerkgebiedSchil>
  );
}
