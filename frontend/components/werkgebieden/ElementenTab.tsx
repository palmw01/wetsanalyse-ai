"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { foutTekst, haalInventaris } from "@/lib/api";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { BronRol, Inventaris, InventarisElement } from "@/lib/types";
import {
  ROL_LABEL, annotatieHref, filterElementen, groepeerPerSelectie, isBeoordeeld, klasseTelling, voortgang,
  type ElementFilter,
} from "@/lib/werkgebied";

const ROL_KNOPPEN: { waarde: BronRol | "alle"; label: string }[] = [
  { waarde: "alle", label: "Alles" },
  { waarde: "analyseren", label: "Werkvoorraad" },
  { waarde: "context", label: "Context" },
];

/** De inventaris: alle actuele, niet-verworpen elementen binnen de selecties, elk één keer.
 *
 *  Wat de api meldt, laat deze tab zien in plaats van weg te poetsen: een onbereikbare bron is een
 *  open punt (de inventaris is dan niet volledig), een gewijzigde brontekst een signaal, en een
 *  element dat deels buiten de selecties valt staat er met een melding bij. Een onbeoordeeld element
 *  mag als input dienen, maar draagt dat voorbehoud zichtbaar. */
export function ElementenTab({ id }: { id: string }) {
  const [inv, setInv] = useState<Inventaris | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [filter, setFilter] = useState<ElementFilter>({ rol: "alle", klasse: "alle", term: "" });

  const laad = useCallback(async () => {
    setFout(null);
    setInv(null);
    try {
      setInv(await haalInventaris(id));
    } catch (e) {
      setFout(foutTekst(e, "De inventaris kon niet worden geladen."));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  if (fout)
    return (
      <Melding type="fout">
        <p>{fout}</p>
        <Button variant="secondary" size="sm" className="mt-2" onClick={laad}>
          Opnieuw proberen
        </Button>
      </Melding>
    );
  if (!inv)
    return (
      <div className="space-y-3" aria-busy="true">
        <p className="text-sm text-muted">De wettekst en de annotaties van de bronnen worden opgehaald…</p>
        <Skeleton className="h-4 w-56" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  if (inv.selecties.length === 0)
    return <p className="text-sm text-muted">Nog geen bronnen, dus nog geen elementen. Neem eerst een bepaling op.</p>;

  const getoond = filterElementen(inv.elementen, filter);
  const groepen = groepeerPerSelectie(inv.selecties, getoond).filter(
    (g) => g.elementen.length > 0 || g.selectie.onbereikbaar || filter.rol === "alle",
  );
  const { totaal, beoordeeld } = voortgang(inv.elementen);
  const afgewezen = inv.selecties.reduce((n, s) => n + s.afgewezen, 0);
  const klassen = klasseTelling(inv.elementen);

  return (
    <div className="space-y-5">
      {!inv.volledig && (
        <Melding type="waarschuwing" titel="De inventaris is niet volledig">
          Niet elke bron kon worden opgehaald; die staan hieronder als open punt. Wat er wel staat klopt,
          maar er kunnen elementen ontbreken.
        </Melding>
      )}

      <p className="text-sm text-ink">
        {inv.elementen.length === 1 ? "1 element" : `${inv.elementen.length} elementen`} in{" "}
        {inv.selecties.length === 1 ? "1 bron" : `${inv.selecties.length} bronnen`} ·{" "}
        {beoordeeld} van {totaal} in de werkvoorraad beoordeeld
        {afgewezen > 0 && <span className="text-muted"> · {afgewezen} verworpen (niet getoond)</span>}
      </p>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="group" aria-label="Rol" className="flex gap-1.5">
          {ROL_KNOPPEN.map((k) => (
            <button
              key={k.waarde}
              type="button"
              aria-pressed={filter.rol === k.waarde}
              onClick={() => setFilter({ ...filter, rol: k.waarde })}
              className={`focus-ring min-h-[24px] rounded-full border px-2.5 py-0.5 text-[0.7rem] transition coarse:min-h-[44px] ${
                filter.rol === k.waarde ? "border-lint bg-lint text-paper" : "border-line text-muted hover:border-lint hover:text-ink"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select
            aria-label="Klasse"
            value={filter.klasse}
            onChange={(e) => setFilter({ ...filter, klasse: e.target.value })}
            className="sm:w-56"
          >
            <option value="alle">Alle klassen</option>
            {klassen.map((k) => (
              <option key={k.klasse} value={k.klasse}>
                {k.klasse} ({k.aantal})
              </option>
            ))}
          </Select>
          <input
            type="search"
            value={filter.term}
            onChange={(e) => setFilter({ ...filter, term: e.target.value })}
            aria-label="Zoeken in elementen"
            placeholder="Zoek in tekst of toelichting"
            className="w-full rounded-field border border-line bg-paper px-3 py-2 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-lint focus:ring-2 focus:ring-lint/20 coarse:min-h-[48px] sm:w-60"
          />
        </div>
      </div>

      {groepen.length === 0 ? (
        <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          Geen element dat hierop past.
        </p>
      ) : (
        groepen.map(({ selectie: s, elementen }) => (
          <section key={s.id} aria-label={s.label || s.bron_iri}>
            <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line pb-2">
              <h3 className="font-display text-sm font-semibold text-lint">{s.label || s.bron_iri}</h3>
              <span className="text-xs text-muted">{ROL_LABEL[s.rol]}</span>
              {s.bron_gewijzigd && (
                <span className="inline-flex items-center rounded-full border border-aandacht-geel-rand bg-aandacht-geel-bg px-2 py-0.5 text-[11px] font-medium text-aandacht-geel-tekst">
                  Brontekst gewijzigd sinds opname
                </span>
              )}
            </div>
            {s.onbereikbaar ? (
              <Melding type="waarschuwing" compact>
                Open punt: {s.onbereikbaar}
              </Melding>
            ) : elementen.length === 0 ? (
              <p className="text-xs text-muted">
                {s.aantal > 0 ? "Geen element dat hierop past." : "Nog geen annotaties binnen deze selectie."}
              </p>
            ) : (
              <ul className="space-y-2">
                {elementen.map((e) => (
                  <ElementRij key={e.id} element={e} />
                ))}
              </ul>
            )}
          </section>
        ))
      )}
    </div>
  );
}

function ElementRij({ element: e }: { element: InventarisElement }) {
  const beoordeeld = isBeoordeeld(e);
  return (
    <li className="rounded-kaart border border-line bg-paper px-3 py-2">
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${jasStyle(e.klasse)}`}>
              {klasseLabel(e.klasse)}
            </span>
            {e.rol === "context" && (
              <span className="inline-flex items-center rounded-full border border-line px-2 py-0.5 text-[11px] text-muted">
                context
              </span>
            )}
            <span className={`text-[11px] ${beoordeeld ? "text-muted" : "text-aandacht-geel-tekst"}`}>
              {beoordeeld ? LIFECYCLE_LABEL[e.lifecycle] : `${LIFECYCLE_LABEL[e.lifecycle]} · nog niet beoordeeld`}
            </span>
          </div>
          <p className="text-sm text-ink">“{e.tekst}”</p>
          {e.deels_buiten && (
            <p className="text-xs text-aandacht-geel-tekst">
              Valt deels buiten de selecties van dit werkgebied; het werkgebied is niet stil verbreed.
            </p>
          )}
        </div>
        <Link
          href={annotatieHref(e.eigenaar_iri)}
          className="focus-ring inline-flex min-h-[24px] shrink-0 items-center self-start rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface coarse:min-h-[44px]"
        >
          Annotatie openen
        </Link>
      </div>
    </li>
  );
}
