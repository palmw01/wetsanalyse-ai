"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ModelLabel } from "@/components/werkwijze/ModelLabel";
import { foutTekst, haalCatalogus } from "@/lib/api";
import {
  SOORTEN, SOORT_LABEL, filterOnderdelen, onderdeelPad, perSoort, telling, type Catalogus, type Soort,
} from "@/lib/catalogus";

/** De werkwijze van Lex (ADR-014): wat Lex kan, per soort, met per onderdeel of er een model aan te pas komt. Een
 *  leesingang voor iedereen; een onderdeel toevoegen of wijzigen gaat via de repo. Soort en zoekterm staan in de URL. */
export function WerkwijzeClient() {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const soort = (SOORTEN as readonly string[]).includes(zoekParams.get("soort") ?? "")
    ? (zoekParams.get("soort") as Soort) : "";
  const [zoek, setZoek] = useState(zoekParams.get("q") ?? "");
  const [data, setData] = useState<Catalogus | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  function zet(nieuw: { soort: Soort | ""; q: string }) {
    const qs = new URLSearchParams();
    if (nieuw.soort) qs.set("soort", nieuw.soort);
    if (nieuw.q) qs.set("q", nieuw.q);
    // `replace`: een filter is geen stap in de geschiedenis.
    router.replace(qs.size ? `${pad}?${qs}` : pad, { scroll: false });
  }

  useEffect(() => {
    if (zoek === (zoekParams.get("q") ?? "")) return;
    const t = setTimeout(() => zet({ soort, q: zoek }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoek]);

  useEffect(() => {
    haalCatalogus().then(setData).catch((e) => setFout(foutTekst(e, "De werkwijze van Lex kon niet worden geladen.")));
  }, []);

  const tel = useMemo(() => (data ? telling(data.onderdelen) : null), [data]);
  const groepen = useMemo(() => (data ? perSoort(filterOnderdelen(data.onderdelen, { soort, zoek })) : []), [data, soort, zoek]);
  const filters = [{ waarde: "" as const, label: "Alles", aantal: data?.onderdelen.length },
    ...SOORTEN.filter((s) => !!tel && tel[s] > 0).map((s) => ({ waarde: s, label: SOORT_LABEL[s].meer, aantal: tel?.[s] }))];

  return (
    <WerkgebiedSchil titel="Werkwijze van Lex" onFout={setFout}>
      <header className="mb-5">
        <h1 className="font-display text-lg font-semibold text-lint">Werkwijze van Lex</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Hoe Lex tot een voorstel komt: de methode die hij volgt, de vaste regels en ketens, en waar een taalmodel
          meedoet. Elk onderdeel noemt zijn bron en de tests die het bewaken.
        </p>
      </header>

      <OverzichtBalk<Soort | "">
        filters={filters}
        gekozen={soort}
        onKies={(s) => zet({ soort: s, q: zoek })}
        filterLabel="Soort"
        zoekterm={zoek}
        onZoek={setZoek}
        zoekLabel="Zoeken in de werkwijze"
        placeholder="Zoek op naam of doel"
      />

      {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}

      {data === null && !fout ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : groepen.length === 0 && data ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          Niets gevonden bij deze zoekterm.
        </p>
      ) : (
        <div className="space-y-6" data-testid="werkwijze">
          {groepen.map((g) => (
            <Groep key={g.soort} kop={SOORT_LABEL[g.soort].meer} telling={g.onderdelen.length}
              sub={SOORT_LABEL[g.soort].uitleg} label={SOORT_LABEL[g.soort].meer} data-soort={g.soort}>
              {g.onderdelen.map((o) => (
                <GroepRij key={o.id} href={onderdeelPad(o.id)} titel={o.label} sub={o.doel} data-onderdeel={o.id}
                  status={<ModelLabel model={o.model} aan={o.aan} />} />
              ))}
            </Groep>
          ))}
        </div>
      )}
    </WerkgebiedSchil>
  );
}
