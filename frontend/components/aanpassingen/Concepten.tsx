"use client";

import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { Button, LinkButton } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import type { AanpassingGroep } from "@/components/instellingen/AanpassingLijst";
import { foutTekst, haalConcepten, haalWerkplaatsStand, maakConcept } from "@/lib/api";
import {
  IN_EDITOR, UIT, WERKPLAATS_SOORT_LABEL, conceptPad, eigenConcept, geldigLabel, naamFout, standLabel, voorOverzicht,
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

/** De concepten van één soort als rijen voor `AanpassingLijst` (segment *Concepten*, plan instellingen-aanpassingen):
 *  mijn concepten en wat met mij gedeeld is, de eigen eerst. Ingetrokken staat standaard verborgen (intrekken is de
 *  manier om een concept weg te doen; verwijderen kan niet) en komt met *Toon ingetrokken* terug. */
export function conceptGroep(werkplaats: ReturnType<typeof useWerkplaats>, soort: WerkplaatsSoort, toonIngetrokken: boolean,
  onToonIngetrokken: (t: boolean) => void): AanpassingGroep {
  const { concepten, userid } = werkplaats;
  const alles = voorOverzicht(concepten, userid).filter((o) => o.soort === soort);
  const ingetrokken = alles.filter((o) => o.stand === "ingetrokken").length;
  const lijst = toonIngetrokken ? alles : alles.filter((o) => o.stand !== "ingetrokken");
  return {
    kop: "Concepten",
    sub: "Wat je zelf maakt of aanpast. Een concept verandert Lex niet: het staat hier tot het is beoordeeld en uitgerold.",
    leeg: "Je hebt nog geen concepten.",
    status: ingetrokken > 0 ? (
      <Button variant="secondary" size="sm" aria-pressed={toonIngetrokken} onClick={() => onToonIngetrokken(!toonIngetrokken)}
        data-actie="concepten-ingetrokken">
        {toonIngetrokken ? "Verberg ingetrokken" : `Toon ingetrokken (${ingetrokken})`}</Button>
    ) : undefined,
    rijen: lijst.map((o) => ({
      id: o.id, naam: o.naam, titel: o.naam, href: conceptPad(o.id), zoektekst: o.naam,
      sub: `${WERKPLAATS_SOORT_LABEL[o.soort]} · versie ${o.laatste?.nummer ?? 0}${o.eigenaar === userid ? "" : ` · van ${o.eigenaar}`}`,
      status: <ConceptLabels o={o} />, data: { "data-concept-id": o.id },
    })),
  };
}

/** De keuzes van *+ Voeg toe* voor een soort: een leeg concept, of een concept van wat in Lex draait. Met de werkplaats
 *  uit, zonder recht om te maken of voor een soort die de editor nog niet opent: niets. */
export function magToevoegen(werkplaats: ReturnType<typeof useWerkplaats>, soort: WerkplaatsSoort): boolean {
  return werkplaats.stand.aan && werkplaats.stand.mag_maken && IN_EDITOR.includes(soort);
}

/** Het formulier van *Voeg toe*: een nieuw concept (alleen de naam), of een concept van iets dat in Lex draait. */
export function VoegToeFormulier({ soort, keuze, vanuitLex, onAnnuleer }: {
  soort: WerkplaatsSoort;
  keuze: "nieuw" | "vanuit";
  /** Wat in Lex draait, om uit te kiezen: naam en label. */
  vanuitLex: { naam: string; label: string }[];
  onAnnuleer: () => void;
}) {
  return keuze === "nieuw"
    ? <NieuwConcept soort={soort} onAnnuleer={onAnnuleer} />
    : <VanuitLex soort={soort} keuzes={vanuitLex} onAnnuleer={onAnnuleer} />;
}

/** Een concept van iets dat in Lex draait: dezelfde handeling als *Bewerken* bij een methode (`uit_image`). */
function VanuitLex({ soort, keuzes, onAnnuleer }: { soort: WerkplaatsSoort; keuzes: { naam: string; label: string }[]; onAnnuleer: () => void }) {
  const router = useRouter();
  const [bezig, setBezig] = useState<string | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  async function maak(naam: string) {
    setBezig(naam); setFout(null);
    try {
      router.push(conceptPad((await maakConcept({ soort, naam, uit_image: true })).id));
    } catch (e) {
      setFout(foutTekst(e, "Het concept kon niet worden gemaakt."));
      setBezig(null);
    }
  }
  return (
    <div className="rounded-kaart border border-line bg-paper p-3" data-concept-vanuit>
      <p className="mb-2 text-sm font-medium text-ink">Welke {WERKPLAATS_SOORT_LABEL[soort].toLowerCase()} wil je aanpassen?</p>
      <p className="mb-3 text-xs text-muted">Je concept begint met de versie die nu in Lex draait.</p>
      <div className="flex flex-wrap gap-2">
        {keuzes.map((k) => (
          <Button key={k.naam} variant="secondary" size="sm" disabled={!!bezig} onClick={() => maak(k.naam)} data-vanuit={k.naam}>
            {bezig === k.naam ? "Bezig…" : k.label}</Button>
        ))}
        <Button variant="secondary" size="sm" onClick={onAnnuleer}>Annuleren</Button>
      </div>
      {fout && <Melding type="fout" compact className="mt-3">{fout}</Melding>}
    </div>
  );
}

/** Een nieuw, leeg concept: alleen de naam. De api begint met de verplichte bestanden en velden. */
export function NieuwConcept({ soort, onAnnuleer }: { soort: WerkplaatsSoort; onAnnuleer: () => void }) {
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

/** *Bewerken* bij een methode in Lex (het tweede niveau van Methodes): maakt een concept met de versie die draait en opent het. Heb ik er al
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
