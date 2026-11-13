"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Melding } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { StatusLabel } from "@/components/ui/Lijst";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ConceptenGroep, useWerkplaats } from "@/components/werkwijze/Concepten";
import { ModelLabel } from "@/components/werkwijze/ModelLabel";
import { foutTekst, haalCatalogus } from "@/lib/api";
import {
  CONCEPT_LABEL, CONCEPT_VOLGORDE, SOORT_LABEL, filterOnderdelen, onderdeelPad, perConcept, type Catalogus, type Concept,
} from "@/lib/catalogus";

/** De werkwijze van Lex (ADR-014): wat Lex kan, per concept (§7: kennis, vaste ketens, agents, handelingen, ingangen,
 *  controles), met per onderdeel zijn soort en of er een model aan te pas komt. Een leesingang voor iedereen. Staat de
 *  werkplaats aan (ADR-016 deel B), dan staan bovenaan de eigen concepten en *Nieuw concept*; wat Lex gebruikt,
 *  verandert pas via de repo. Concept en zoekterm staan in de URL. */
export function WerkwijzeClient() {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const concept = (CONCEPT_VOLGORDE as string[]).includes(zoekParams.get("concept") ?? "")
    ? (zoekParams.get("concept") as Concept) : "";
  const [zoek, setZoek] = useState(zoekParams.get("q") ?? "");
  const [data, setData] = useState<Catalogus | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const werkplaats = useWerkplaats();

  function zet(nieuw: { concept: Concept | ""; q: string }) {
    const qs = new URLSearchParams();
    if (nieuw.concept) qs.set("concept", nieuw.concept);
    if (nieuw.q) qs.set("q", nieuw.q);
    // `replace`: een filter is geen stap in de geschiedenis.
    router.replace(qs.size ? `${pad}?${qs}` : pad, { scroll: false });
  }

  useEffect(() => {
    if (zoek === (zoekParams.get("q") ?? "")) return;
    const t = setTimeout(() => zet({ concept, q: zoek }), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoek]);

  useEffect(() => {
    haalCatalogus().then(setData).catch((e) => setFout(foutTekst(e, "De werkwijze van Lex kon niet worden geladen.")));
  }, []);

  const groepen = useMemo(() => (data ? perConcept(filterOnderdelen(data.onderdelen, { concept, zoek })) : []), [data, concept, zoek]);
  const alle = useMemo(() => (data ? perConcept(data.onderdelen) : []), [data]);
  const filters = [{ waarde: "" as const, label: "Alles", aantal: data?.onderdelen.length },
    ...alle.map((g) => ({ waarde: g.concept, label: CONCEPT_LABEL[g.concept].kop, aantal: g.onderdelen.length }))];

  return (
    <WerkgebiedSchil titel="Werkwijze van Lex" onFout={setFout}>
      <header className="mb-5">
        <h1 className="font-display text-lg font-semibold text-lint">Werkwijze van Lex</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Hoe Lex tot een voorstel komt: de methode die hij volgt, de vaste regels en ketens, en waar een taalmodel
          meedoet. Elk onderdeel noemt zijn bron en de tests die het bewaken.
        </p>
      </header>

      <OverzichtBalk<Concept | "">
        filters={filters}
        gekozen={concept}
        onKies={(c) => zet({ concept: c, q: zoek })}
        filterLabel="Soort onderdeel"
        zoekterm={zoek}
        onZoek={setZoek}
        zoekLabel="Zoeken in de werkwijze"
        placeholder="Zoek op naam of doel"
      />

      {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}

      {/* De eigen concepten (ADR-016 §B7) horen bij kennis en methode; met de werkplaats uit staat hier niets. */}
      {(concept === "" || concept === "skill") && (
        <div className="mb-6 empty:hidden"><ConceptenGroep werkplaats={werkplaats} zoek={zoek} /></div>
      )}

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
            <Groep key={g.concept} kop={CONCEPT_LABEL[g.concept].kop} telling={g.onderdelen.length}
              sub={CONCEPT_LABEL[g.concept].uitleg} label={CONCEPT_LABEL[g.concept].kop} data-concept={g.concept}>
              {g.onderdelen.map((o) => (
                <GroepRij key={o.id} href={onderdeelPad(o.id)} titel={o.label} sub={o.doel} data-onderdeel={o.id}
                  status={<><StatusLabel data-soort={o.soort}>{SOORT_LABEL[o.soort].een}</StatusLabel>
                    <ModelLabel model={o.model} aan={o.aan} /></>} />
              ))}
            </Groep>
          ))}
        </div>
      )}
    </WerkgebiedSchil>
  );
}
