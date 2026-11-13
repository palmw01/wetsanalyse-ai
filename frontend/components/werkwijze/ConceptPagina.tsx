"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { MeerMenu, MenuVerwijder } from "@/components/ui/MeerMenu";
import { PaginaKop } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ConceptEditor } from "@/components/werkwijze/ConceptEditor";
import { ConceptLabels } from "@/components/werkwijze/Concepten";
import { VersieWeergave, VersiesKaart } from "@/components/werkwijze/ConceptVersies";
import { foutTekst, haalConcept, haalConceptVersie, haalWerkplaatsStand, isApiError, trekConceptIn } from "@/lib/api";
import {
  WERKPLAATS_SOORT_LABEL, conceptPad, versieKeuze, type Bestanden, type WerkplaatsOnderdeel, type WerkplaatsStand,
  type WerkplaatsVersie,
} from "@/lib/werkplaats";

/** Eén concept uit de werkplaats (ADR-016 §B7): de bestanden van de laatste versie en wat de controle ervan vond.
 *  Een concept is een artefact: je leest het hier, de eigenaar bewerkt het hier (`ConceptEditor`) en trekt het hier in.
 *  Niets op deze pagina start Lex. Het gekozen bestand staat in de URL. */
export function ConceptPagina({ id }: { id: string }) {
  const { data: sessie } = useSession();
  const [stand, setStand] = useState<WerkplaatsStand | null>(null);
  const [o, setO] = useState<WerkplaatsOnderdeel | null>(null);
  const [versie, setVersie] = useState<WerkplaatsVersie | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  // Na een nieuwe versie of intrekken: opnieuw lezen.
  const [lading, setLading] = useState(0);
  // De bestanden van een eerdere versie, teruggezet als wijziging op de laatste (*Zet terug als concept*).
  const [klaargezet, setKlaargezet] = useState<{ bestanden: Bestanden; van: number } | null>(null);
  const herlaad = useCallback(() => { setKlaargezet(null); setLading((n) => n + 1); }, []);
  // Een eerdere versie om te lezen, en de versie waarmee ze vergeleken wordt: uit de URL.
  const router = useRouter();
  const pad = usePathname();
  const zoekParams = useSearchParams();
  const nummers = (o?.versielijst ?? []).map((v) => v.nummer);
  const keuze = versieKeuze(zoekParams.get("versie"), zoekParams.get("met"), nummers);
  // Een versie verandert nooit, dus wat gelezen is, blijft bruikbaar.
  const [gelezen, setGelezen] = useState<Record<number, WerkplaatsVersie>>({});
  const bekeken = keuze.versie !== null ? gelezen[keuze.versie] ?? null : null;
  const vergeleken = keuze.met !== null ? gelezen[keuze.met] ?? null : null;
  const teLezen = [keuze.versie, keuze.versie !== null ? keuze.met : null].filter((n): n is number => n !== null && !gelezen[n]).join(",");

  useEffect(() => {
    if (!teLezen) return;
    let weg = false;
    for (const n of teLezen.split(",").map(Number)) {
      haalConceptVersie(id, n).then((v) => { if (!weg) setGelezen((g) => ({ ...g, [n]: v })); })
        .catch((e) => { if (!weg) setMelding(foutTekst(e, `Versie ${n} kon niet worden geladen.`)); });
    }
    return () => { weg = true; };
  }, [id, teLezen]);

  function zetParam(naam: string, waarde: string) {
    const qs = new URLSearchParams(zoekParams.toString());
    qs.set(naam, waarde);
    // `replace`: een ander bestand of een andere vergelijking is geen stap in de geschiedenis.
    router.replace(`${pad}?${qs}`, { scroll: false });
  }

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
  }, [id, lading]);

  async function trekIn() {
    setMelding(null);
    try {
      await trekConceptIn(id);
      herlaad();
    } catch (e) {
      setMelding(foutTekst(e, "Het concept kon niet worden ingetrokken."));
    }
  }

  const kruimels = [{ label: "Werkwijze van Lex", href: "/werkwijze" },
    { label: "Concepten", href: "/werkwijze?concept=skill" }, { label: o?.naam ?? "Concept" }];
  const vanMij = !!o && o.eigenaar === sessie?.user?.userid;
  const bewerkbaar = vanMij && o?.stand !== "ingetrokken";

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
              <span>versie {o.laatste?.nummer ?? 0}</span>{!vanMij && <span>van {o.eigenaar}</span>}</>}
            acties={bewerkbaar ? (
              <MeerMenu label="Meer over dit concept" maat="sm">
                {() => <MenuVerwijder vraag="Intrekken?" ariaLabel="Concept intrekken" onBevestig={trekIn}
                  titel="Het concept is daarna alleen nog te lezen; de versies blijven bewaard en de naam is weer vrij.">Intrekken</MenuVerwijder>}
              </MeerMenu>) : undefined} />
          {melding && <Melding type="fout" className="mb-4">{melding}</Melding>}
          {o.basis_verouderd && (
            <div className="mb-4" data-melding="loopt-achter">
              <Melding type="waarschuwing">Er draait intussen een andere versie dan waar dit concept op voortbouwt.</Melding>
            </div>
          )}
          {!versie || !stand ? <Skeleton className="h-40 w-full" />
            : keuze.versie !== null ? (!bekeken || (keuze.met !== null && !vergeleken) ? <Skeleton className="h-40 w-full" /> : (
              <VersieWeergave o={o} versie={bekeken} met={keuze.met !== null ? vergeleken : null}
                andere={nummers.filter((n) => n !== keuze.versie).sort((a, b) => b - a)}
                bestand={zoekParams.get("bestand") ?? ""} onKiesBestand={(p) => zetParam("bestand", p)}
                onKiesMet={(n) => zetParam("met", String(n ?? 0))}
                onTerugzetten={bewerkbaar && bekeken.nummer !== o.laatste?.nummer && bekeken.bestanden ? () => {
                  setKlaargezet({ bestanden: bekeken.bestanden!, van: bekeken.nummer });
                  router.push(conceptPad(o.id));
                } : undefined}
                zij={<VersiesKaart o={o} gekozen={keuze.versie} />} />
            ))
            // Een nieuwe versie is een nieuwe editor: de bewaarde stand is dan het vertrekpunt.
            : <ConceptEditor key={`${o.id}.${versie.nummer}`} o={o} versie={versie} grenzen={stand.grenzen} bewerkbaar={bewerkbaar}
                onOpgeslagen={herlaad} klaargezet={klaargezet} onVerworpen={() => setKlaargezet(null)}
                zij={<VersiesKaart o={o} gekozen={null} />} />}
        </>
      )}
    </WerkgebiedSchil>
  );
}
