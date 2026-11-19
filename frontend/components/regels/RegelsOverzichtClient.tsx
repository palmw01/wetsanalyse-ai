"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { RegelOverzichtKaart } from "@/components/regels/RegelOverzichtKaart";
import { Select } from "@/components/ui/Field";
import { Leeg } from "@/components/ui/Leeg";
import { Melding } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { OverzichtRaster, OverzichtSkelet } from "@/components/ui/Pagina";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { aantal } from "@/lib/aantal";
import { foutTekst, lijstWerkgebieden, verwijderRegel, zoekRegels } from "@/lib/api";
import { REGEL_STATUS_LABEL, type RegelStatus } from "@/lib/regels";
import {
  REGEL_FILTER_STATUSSEN, regelFiltersUitParams, regelParamsVan,
  type RegelFilters, type RegelOverzichtRij, type RegelsOverzicht,
} from "@/lib/regelsOverzicht";
import type { WerkgebiedSamenvatting } from "@/lib/types";
import { metSpoor } from "@/lib/uiSpoor";

/** Het overzicht van de afleidingsregels over alle werkgebieden heen (ADR-018, de zijbalk), in de vorm van de andere
 *  overzichten (`OverzichtBalk`, `OverzichtKaart`). Een leesingang: zoeken in naam, uitvoer en regeltekst, filteren op
 *  status en werkgebied, en doorklikken naar de regel in zijn werkgebied – daar gebeurt het werk. De filters staan in de
 *  URL, zodat terugbladeren en delen werken. */
export function RegelsOverzichtClient() {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const filters = useMemo(() => regelFiltersUitParams(new URLSearchParams(zoekParams.toString())), [zoekParams]);
  const [term, setTerm] = useState(filters.q);
  const [data, setData] = useState<RegelsOverzicht | null>(null);
  const [werkgebieden, setWerkgebieden] = useState<WerkgebiedSamenvatting[]>([]);
  const [fout, setFout] = useState<string | null>(null);

  function zet(nieuw: RegelFilters) {
    const qs = regelParamsVan(nieuw, "pagina").toString();
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
    zoekRegels(regelParamsVan(filters, "api"))
      .then((d) => { if (!weg) { setData(d); setFout(null); } })
      .catch((e) => {
        if (weg) return;
        setFout(foutTekst(e, "De afleidingsregels konden niet worden geladen."));
        setData({ resultaten: [], totaal: 0 });
      });
    return () => { weg = true; };
  }, [filters]);

  useEffect(() => {
    lijstWerkgebieden().then(setWerkgebieden).catch(() => setWerkgebieden([]));
  }, []);

  /** Echt wissen, zoals een begrip (`lib/verwijderen.ts`): de rij gaat meteen weg en komt bij een fout terug. */
  async function verwijder(r: RegelOverzichtRij) {
    const voor = data;
    setData((d) => d && { ...d, resultaten: d.resultaten.filter((x) => x.id !== r.id), totaal: d.totaal - 1 });
    setFout(null);
    try {
      await metSpoor("regel_verwijderen", () => verwijderRegel(r.werkgebied_id, r.id, r.revisie));
    } catch (e) {
      setData(voor);
      setFout(foutTekst(e, "De afleidingsregel is niet verwijderd."));
    }
  }

  const telling = data?.per_status;
  const keuzes = [{ waarde: "" as const, label: "Alle",
      aantal: telling ? Object.values(telling).reduce((a, b) => a + (b ?? 0), 0) : undefined },
    ...REGEL_FILTER_STATUSSEN.map((s) => ({ waarde: s,
      // Kort op de knop; de kaart noemt de status voluit.
      label: s === "geaccordeerd_als_beleidsregel" ? "Beleidsregel" : REGEL_STATUS_LABEL[s], aantal: telling ? telling[s] ?? 0 : undefined }))];

  return (
    <WerkgebiedSchil titel="Afleidingsregels" onFout={setFout}>
      <header className="mb-5">
        <h1 className="font-display text-lg font-semibold text-lint">Afleidingsregels</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          De afleidingsregels uit alle werkgebieden: hoe een uitkomst uit de begrippen volgt. Een regel is een
          analyse-uitkomst, geen wettekst; je werkt eraan op zijn pagina.
        </p>
      </header>

      <OverzichtBalk<RegelStatus | "">
        filters={keuzes}
        gekozen={filters.status}
        onKies={(status) => zet({ ...filters, status })}
        filterLabel="Status"
        mijn={filters.mijn}
        onMijn={(mijn) => zet({ ...filters, mijn })}
        extra={
          <Select aria-label="Werkgebied" value={filters.werkgebied} className="w-full sm:w-auto sm:max-w-[12rem]"
            onChange={(e) => zet({ ...filters, werkgebied: e.target.value })}>
            <option value="">Alle werkgebieden</option>
            {werkgebieden.map((w) => <option key={w.id} value={w.id}>{w.naam}</option>)}
          </Select>
        }
        zoekterm={term}
        onZoek={setTerm}
        zoekLabel="Zoeken in afleidingsregels"
        placeholder="Zoek op naam, uitvoer of regeltekst"
      />

      {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}

      {data === null ? (
        <OverzichtSkelet />
      ) : data.resultaten.length === 0 ? (
        <Leeg kader>
          {filters.q || filters.status || filters.werkgebied || filters.mijn
            ? "Geen afleidingsregels bij deze filters."
            : "Nog geen afleidingsregels. Afleidingsregels ontstaan in een werkgebied."}
        </Leeg>
      ) : (
        <>
          <p className="mb-2 text-xs text-muted" aria-live="polite">{aantal(data.totaal, "afleidingsregel", "afleidingsregels")}</p>
          <OverzichtRaster data-testid="regels-overzicht">
            {data.resultaten.map((r) => <RegelOverzichtKaart key={r.id} r={r} onVerwijder={() => verwijder(r)} />)}
          </OverzichtRaster>
        </>
      )}
    </WerkgebiedSchil>
  );
}
