"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { Select } from "@/components/ui/Field";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding, MeldingActie } from "@/components/ui/Melding";
import { foutTekst, getAccount, haalModelkeuzes, haalModelkeuzesBeheer, zetModelkeuze } from "@/lib/api";
import { STANDAARD, keuzesVoor, modelTekst, type Keuze, type Overzicht, type Sleutel, type Stand } from "@/lib/modelkeuzes";

/** De modelkeuzes voor de tab Agents (plan instellingen-aanpassingen, PR 5). Een beheerder leest het overzicht van het
 *  beheer en kiest (met 2FA); iedereen anders leest welk model Lex gebruikt. Faalt het laden, dan staat er een melding en
 *  blijft de rest van de tab werken: het model is een toevoeging, geen voorwaarde. */
export function useModelkeuzes() {
  const { data: sessie } = useSession();
  const beheerder = sessie?.user?.role === "beheerder";
  const [overzicht, setOverzicht] = useState<Overzicht | null>(null);
  const [stand, setStand] = useState<Stand | null>(null);
  const [tfaNodig, setTfaNodig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState<string | null>(null);

  const laad = useCallback(async () => {
    try {
      if (beheerder) {
        const [o, a] = await Promise.all([haalModelkeuzesBeheer(), getAccount()]);
        setOverzicht(o);
        setTfaNodig(a.tfa_nodig);
      } else {
        setStand(await haalModelkeuzes());
      }
      setFout(null);
    } catch (e) {
      setFout(foutTekst(e, "Welk model Lex gebruikt, kon niet worden geladen."));
    }
  }, [beheerder]);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (sessie) void laad();
  }, [laad, sessie]);

  async function kies(sleutel: string, profiel: string | null) {
    setBezig(sleutel);
    try {
      await zetModelkeuze(sleutel, profiel);
      await laad();
    } catch (e) {
      setFout(foutTekst(e, "De keuze kon niet worden opgeslagen."));
    } finally {
      setBezig(null);
    }
  }

  /** De sleutels in de volgorde van de api: uit het overzicht (beheer) of uit de stand (lezen). */
  const sleutels: Sleutel[] = overzicht?.keuzes ?? stand?.sleutels ?? [];
  return { beheerder, overzicht, stand, tfaNodig, fout, bezig, kies, sleutels, geladen: !!(overzicht || stand) };
}

export type Modelkeuzes = ReturnType<typeof useModelkeuzes>;

/** Het model van één agentprofiel of stap: een keuzelijst voor een beheerder met 2FA, anders tekst. */
export function ModelKeuzeVeld({ m, sleutel, label }: { m: Modelkeuzes; sleutel: string; label: string }) {
  if (!m.geladen) return null;
  const keuze = m.overzicht?.keuzes.find((k) => k.sleutel === sleutel);
  if (m.overzicht && keuze && !m.tfaNodig) {
    return (
      <label className="flex min-w-0 items-center gap-2 text-xs text-muted" data-modelkeuze={sleutel}>
        <span className="shrink-0">Model</span>
        <Select value={keuze.profiel ?? STANDAARD} disabled={m.bezig === sleutel} aria-busy={m.bezig === sleutel}
          aria-label={`Model voor ${label}`} className="min-w-0 max-w-[20rem]"
          onChange={(e) => void m.kies(sleutel, e.target.value === STANDAARD ? null : e.target.value)}>
          {keuzesVoor(m.overzicht).map((k) => (
            <option key={k.waarde} value={k.waarde} disabled={k.uit} title={k.reden || undefined}>{k.label}</option>
          ))}
        </Select>
      </label>
    );
  }
  const tekst = keuze ? modelTekst(keuze.model ? { profiel: keuze.profiel ?? "", model: keuze.model, bron: keuze.profiel ? "keuze" : "standaard" } : null)
    : modelTekst(m.stand?.keuzes[sleutel]);
  return <span className="text-xs text-muted [overflow-wrap:anywhere]" data-modelkeuze={sleutel}>Model: {tekst}</span>;
}

/** Onder een rij: waarom het gekozen profiel niet werkt, of de waarschuwing als er een ander model dan de standaard
 *  gekozen is. Zonder iets te zeggen: niets. */
export function ModelKeuzeMelding({ m, sleutel }: { m: Modelkeuzes; sleutel: string }) {
  const k: Keuze | undefined = m.overzicht?.keuzes.find((x) => x.sleutel === sleutel);
  if (!k) return null;
  if (k.niet_bruikbaar) {
    return <Melding type="waarschuwing" compact className="text-xs">
      Het gekozen profiel {k.profiel} is niet bruikbaar: {k.niet_bruikbaar} Lex gebruikt nu de standaard.</Melding>;
  }
  if (k.profiel && k.waarschuwing) return <Melding type="waarschuwing" compact className="text-xs">{k.waarschuwing}</Melding>;
  return null;
}

/** Een label bij een sleutel met een waarschuwing, zodat de beheerder hem ziet vóór hij kiest. */
export function WaarschuwingLabel({ m, sleutel }: { m: Modelkeuzes; sleutel: string }) {
  const k = m.overzicht?.keuzes.find((x) => x.sleutel === sleutel);
  if (!k?.waarschuwing) return null;
  return <StatusLabel toon="geel" uitleg={k.waarschuwing}>meet eerst</StatusLabel>;
}

/** Boven de lijst: wat er speelt met de modelkeuzes (2FA, een standaard die Lex niet kan gebruiken, een laadfout). */
export function ModelkeuzesMelding({ m, onNaarBeveiliging }: { m: Modelkeuzes; onNaarBeveiliging: () => void }) {
  if (m.fout) return <Melding type="fout" compact>{m.fout}</Melding>;
  if (m.beheerder && m.overzicht && m.tfaNodig) {
    return (
      <Melding type="waarschuwing" compact>
        Een model kiezen gaat pas als er een authenticator-app aan je account hangt.{" "}
        <MeldingActie onClick={onNaarBeveiliging}>Naar Beveiliging</MeldingActie>
      </Melding>
    );
  }
  if (m.overzicht?.standaard_niet_bruikbaar) {
    return <Melding type="waarschuwing" compact>
      Lex kan het standaardprofiel niet gebruiken: {m.overzicht.standaard_niet_bruikbaar} Wat geen eigen keuze heeft, houdt het
      model van de omgeving.</Melding>;
  }
  return null;
}
