"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart, PaginaKop } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ConceptLabels } from "@/components/werkwijze/Concepten";
import { foutTekst, haalConcept, haalConceptVersie, haalWerkplaatsStand, isApiError } from "@/lib/api";
import {
  WERKPLAATS_SOORT_LABEL, bestandsvolgorde, type WerkplaatsOnderdeel, type WerkplaatsStand, type WerkplaatsVersie,
} from "@/lib/werkplaats";

/** Eén concept uit de werkplaats (ADR-016 §B7): de bestanden van de laatste versie en wat de controle ervan vond.
 *  Een concept is een artefact: je leest het hier, en bewerkt en besluit er later ook hier over. Niets op deze pagina
 *  start Lex. Het gekozen bestand staat in de URL. */
export function ConceptPagina({ id }: { id: string }) {
  const { data: sessie } = useSession();
  const [stand, setStand] = useState<WerkplaatsStand | null>(null);
  const [o, setO] = useState<WerkplaatsOnderdeel | null>(null);
  const [versie, setVersie] = useState<WerkplaatsVersie | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    let weg = false;
    (async () => {
      const s = await haalWerkplaatsStand();
      if (weg) return;
      setStand(s);
      if (!s.aan) return;
      try {
        const onderdeel = await haalConcept(id);
        if (weg) return;
        setO(onderdeel);
        if (onderdeel.laatste) {
          const v = await haalConceptVersie(id, onderdeel.laatste.nummer);
          if (!weg) setVersie(v);
        }
      } catch (e) {
        if (!weg) setFout(isApiError(e) && e.status === 404
          ? "Dit concept bestaat niet, of het is niet met je gedeeld." : foutTekst(e, "Dit concept kon niet worden geladen."));
      }
    })();
    return () => { weg = true; };
  }, [id]);

  const kruimels = [{ label: "Werkwijze van Lex", href: "/werkwijze" },
    { label: "Concepten", href: "/werkwijze?concept=skill" }, { label: o?.naam ?? "Concept" }];
  const vanMij = !!o && o.eigenaar === sessie?.user?.userid;

  return (
    <WerkgebiedSchil titel={o?.naam ?? "Concept"} onFout={setFout}>
      {stand && !stand.aan ? (
        <>
          <PaginaKop kruimels={kruimels} titel="Concept" />
          <div data-werkplaats="uit"><Melding type="uitleg">De werkplaats staat op deze omgeving niet aan. Concepten zijn hier niet te lezen of te maken.</Melding></div>
        </>
      ) : fout ? (
        <>
          <PaginaKop kruimels={kruimels} titel="Concept" />
          <Melding type="fout">{fout}</Melding>
        </>
      ) : !o ? (
        <div className="space-y-3"><Skeleton className="h-6 w-64" /><Skeleton className="h-40 w-full" /></div>
      ) : (
        <>
          <PaginaKop kruimels={kruimels} titel={o.naam}
            meta={<><StatusLabel toon="lint">{WERKPLAATS_SOORT_LABEL[o.soort]}</StatusLabel><ConceptLabels o={o} />
              <span>versie {o.laatste?.nummer ?? 0}</span>{!vanMij && <span>van {o.eigenaar}</span>}</>} />
          {o.basis_verouderd && (
            <div className="mb-4" data-melding="loopt-achter">
              <Melding type="waarschuwing">Er draait intussen een andere versie dan waar dit concept op voortbouwt.</Melding>
            </div>
          )}
          {!versie ? <Skeleton className="h-40 w-full" /> : <Bestanden versie={versie} />}
        </>
      )}
    </WerkgebiedSchil>
  );
}

/** De bestanden van een versie: links de lijst, rechts het gekozen bestand; op een telefoon onder elkaar. */
function Bestanden({ versie }: { versie: WerkplaatsVersie }) {
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const bestanden = versie.bestanden ?? {};
  const paden = bestandsvolgorde(Object.keys(bestanden));
  const gevraagd = zoekParams.get("bestand") ?? "";
  const gekozen = paden.includes(gevraagd) ? gevraagd : paden[0] ?? "";
  const perBestand = (p: string) => versie.bevindingen.filter((b) => b.bestand === p);
  const algemeen = versie.bevindingen.filter((b) => !paden.includes(b.bestand));

  function kies(p: string) {
    const qs = new URLSearchParams(zoekParams.toString());
    qs.set("bestand", p);
    // `replace`: een ander bestand is geen stap in de geschiedenis.
    router.replace(`${pad}?${qs}`, { scroll: false });
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]" data-concept-versie={versie.nummer}>
      <div className="min-w-0 space-y-4">
        <Kaart titel="Bestanden" telling={paden.length} data-blok="bestanden">
          <ul aria-label="Bestanden van dit concept" className="-mx-1 space-y-0.5">
            {paden.map((p) => {
              const n = perBestand(p).length;
              return (
                <li key={p}>
                  <button type="button" onClick={() => kies(p)} aria-current={p === gekozen ? "true" : undefined} data-bestand={p}
                    className="focus-ring flex min-h-[32px] w-full items-center gap-2 rounded-knop px-2 py-1 text-left text-sm text-ink transition-colors hover:bg-surface aria-[current=true]:bg-lint/[0.06] aria-[current=true]:font-medium aria-[current=true]:text-lint coarse:min-h-[44px]">
                    <span className="min-w-0 flex-1 font-mono text-xs [overflow-wrap:anywhere]">{p}</span>
                    {n > 0 && <StatusLabel toon="geel" uitleg={n === 1 ? "1 bevinding in dit bestand" : `${n} bevindingen in dit bestand`}>{n}</StatusLabel>}
                  </button>
                </li>
              );
            })}
          </ul>
        </Kaart>
        <Kaart titel="Controle" telling={versie.bevindingen.length} data-blok="controle"
          toelichting={versie.geldig ? "Deze versie haalt de controle." : "Deze versie haalt de controle niet. Ze is bewaard, maar kan zo niet verder."}>
          {versie.bevindingen.length > 0 && (
            <ul aria-label="Bevindingen van de controle" className="space-y-2 text-sm">
              {[...algemeen, ...paden.flatMap(perBestand)].map((b, i) => (
                <li key={i} data-bevinding={b.code} className="[overflow-wrap:anywhere]">
                  {b.bestand && <span className="block font-mono text-xs text-muted">{b.bestand}</span>}
                  {b.melding}
                </li>
              ))}
            </ul>
          )}
        </Kaart>
      </div>
      <Kaart titel={<span className="font-mono text-sm [overflow-wrap:anywhere]">{gekozen || "Geen bestanden"}</span>} data-blok="inhoud">
        {gekozen && (
          <pre data-bestand-inhoud={gekozen}
            className="max-w-full whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink [overflow-wrap:anywhere]">{bestanden[gekozen]}</pre>
        )}
      </Kaart>
    </div>
  );
}
