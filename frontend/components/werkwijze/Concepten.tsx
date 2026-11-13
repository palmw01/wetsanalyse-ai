"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { Button, LinkButton } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { foutTekst, haalConcepten, haalWerkplaatsStand, maakConcept } from "@/lib/api";
import {
  UIT, WERKPLAATS_SOORT_LABEL, conceptPad, eigenConcept, geldigLabel, naamFout, standLabel, voorOverzicht,
  type WerkplaatsOnderdeel, type WerkplaatsSoort, type WerkplaatsStand,
} from "@/lib/werkplaats";

/** De werkplaats voor een scherm: staat ze aan, wat mag ik, en mijn concepten. Zolang de stand niet gelezen is, of
 *  de werkplaats uit staat, is `stand.aan` onwaar en tekent niemand iets: zo is een omgeving zonder werkplaats gelijk
 *  aan voorheen. */
export function useWerkplaats(): { stand: WerkplaatsStand; concepten: WerkplaatsOnderdeel[]; userid: string | undefined; fout: string | null } {
  const { data: sessie } = useSession();
  const [stand, setStand] = useState<WerkplaatsStand>(UIT);
  const [concepten, setConcepten] = useState<WerkplaatsOnderdeel[]>([]);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    let weg = false;
    haalWerkplaatsStand().then(async (s) => {
      if (weg || !s.aan) return;
      setStand(s);
      try {
        const lijst = await haalConcepten();
        if (!weg) setConcepten(lijst);
      } catch (e) {
        if (!weg) setFout(foutTekst(e, "De concepten konden niet worden geladen."));
      }
    });
    return () => { weg = true; };
  }, []);

  return { stand, concepten, userid: sessie?.user?.userid ?? undefined, fout };
}

/** De stand van een concept als labels: wat het is, en of de laatste versie de controle haalt. */
export function ConceptLabels({ o }: { o: WerkplaatsOnderdeel }) {
  const stand = standLabel(o);
  const geldig = o.stand === "ingetrokken" ? null : geldigLabel(o.laatste);
  return (
    <>
      <StatusLabel toon={stand.toon} uitleg={stand.uitleg} data-conceptstand={o.stand}>{stand.tekst}</StatusLabel>
      {geldig && <StatusLabel toon={geldig.toon} uitleg={geldig.uitleg} data-geldig={o.laatste?.geldig ? "ja" : "nee"}>{geldig.tekst}</StatusLabel>}
    </>
  );
}

/** De groep *Concepten* op het overzicht van de werkwijze (ADR-016 §B7): mijn concepten en wat met mij gedeeld is,
 *  en *Nieuw concept*. Staat de werkplaats uit, dan tekent deze component niets. */
export function ConceptenGroep({ werkplaats, zoek }: { werkplaats: ReturnType<typeof useWerkplaats>; zoek: string }) {
  const { stand, concepten, userid, fout } = werkplaats;
  const [nieuw, setNieuw] = useState(false);
  const [toonIngetrokken, setToonIngetrokken] = useState(false);
  if (!stand.aan) return null;
  const woorden = zoek.toLowerCase().split(/\s+/).filter(Boolean);
  const opNaam = (o: WerkplaatsOnderdeel) => woorden.every((w) => o.naam.toLowerCase().includes(w));
  const alles = voorOverzicht(concepten, userid).filter(opNaam);
  const ingetrokken = alles.filter((o) => o.stand === "ingetrokken").length;
  const lijst = toonIngetrokken ? alles : alles.filter((o) => o.stand !== "ingetrokken");
  if (alles.length === 0 && !stand.mag_maken && !fout) return null;
  return (
    <section className="space-y-3" data-concepten>
      <Groep kop="Concepten" telling={lijst.length} label="Concepten"
        sub="Wat je zelf maakt of aanpast. Een concept verandert Lex niet: het staat hier tot het is beoordeeld en uitgerold."
        status={stand.mag_maken && !nieuw
          ? <Button variant="secondary" size="sm" onClick={() => setNieuw(true)} data-actie="concept-nieuw">Nieuw concept</Button> : undefined}
        leeg={nieuw ? undefined : zoek ? "Geen concept bij deze zoekterm." : "Je hebt nog geen concepten."}>
        {lijst.map((o) => (
          <GroepRij key={o.id} href={conceptPad(o.id)} titel={o.naam} data-concept-id={o.id}
            sub={`${WERKPLAATS_SOORT_LABEL[o.soort]} · versie ${o.laatste?.nummer ?? 0}${o.eigenaar === userid ? "" : ` · van ${o.eigenaar}`}`}
            status={<ConceptLabels o={o} />} />
        ))}
      </Groep>
      {ingetrokken > 0 && (
        <Button variant="secondary" size="sm" aria-pressed={toonIngetrokken} onClick={() => setToonIngetrokken((t) => !t)}
          data-actie="concepten-ingetrokken">
          {toonIngetrokken ? "Verberg ingetrokken" : `Toon ingetrokken (${ingetrokken})`}</Button>
      )}
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {nieuw && <NieuwConcept soort="skill" onAnnuleer={() => setNieuw(false)} />}
    </section>
  );
}

/** Een nieuw, leeg concept: alleen de naam. De api begint met de verplichte bestanden en velden. */
function NieuwConcept({ soort, onAnnuleer }: { soort: WerkplaatsSoort; onAnnuleer: () => void }) {
  const router = useRouter();
  const [naam, setNaam] = useState("");
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const vormfout = naamFout(naam);

  async function maak(e: React.FormEvent) {
    e.preventDefault();
    if (!naam || vormfout || bezig) return;
    setBezig(true); setFout(null);
    try {
      router.push(conceptPad((await maakConcept({ soort, naam })).id));
    } catch (err) {
      setFout(foutTekst(err, "Het concept kon niet worden gemaakt."));
      setBezig(false);
    }
  }

  return (
    <form onSubmit={maak} className="rounded-kaart border border-line bg-paper p-3" data-concept-nieuw>
      <Field label={`Naam van de ${WERKPLAATS_SOORT_LABEL[soort].toLowerCase()}`} error={vormfout || fout || undefined}>
        <Input value={naam} onChange={(e) => setNaam(e.target.value.trim())} autoFocus autoComplete="off" spellCheck={false}
          placeholder="bijvoorbeeld jrm-scenario" aria-invalid={!!vormfout} />
      </Field>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <Button type="submit" size="sm" disabled={!naam || !!vormfout || bezig} data-actie="concept-maken">
          {bezig ? "Bezig…" : "Maak concept"}</Button>
        <Button type="button" variant="secondary" size="sm" onClick={onAnnuleer}>Annuleren</Button>
      </div>
    </form>
  );
}

/** *Bewerken* op de pagina van een methode: maakt een concept met de versie die draait en opent het. Heb ik er al
 *  een, dan opent de knop dat. Staat de werkplaats uit of mag ik niet maken, dan staat er niets. */
export function ConceptBewerken({ soort, naam }: { soort: WerkplaatsSoort; naam: string }) {
  const router = useRouter();
  const { stand, concepten, userid } = useWerkplaats();
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const eigen = eigenConcept(concepten, soort, naam, userid);

  const bewerk = useCallback(async () => {
    setBezig(true); setFout(null);
    try {
      router.push(conceptPad((await maakConcept({ soort, naam, uit_image: true })).id));
    } catch (e) {
      setFout(foutTekst(e, "Het concept kon niet worden gemaakt."));
      setBezig(false);
    }
  }, [router, soort, naam]);

  if (!stand.aan) return null;
  if (eigen) return (
    <span className="contents" data-actie="concept-openen">
      <LinkButton href={conceptPad(eigen.id)} variant="secondary" size="sm" className="w-full sm:w-auto">Open mijn concept</LinkButton>
    </span>
  );
  if (!stand.mag_maken) return null;
  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-end">
      <Button variant="secondary" size="sm" onClick={bewerk} disabled={bezig} data-actie="concept-bewerken">
        {bezig ? "Bezig…" : "Bewerken"}</Button>
      {fout && <Melding type="fout" compact className="max-w-xs">{fout}</Melding>}
    </div>
  );
}
