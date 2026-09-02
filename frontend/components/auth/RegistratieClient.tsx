"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";

export function RegistratieClient() {
  const [voornaam, setVoornaam] = useState("");
  const [achternaam, setAchternaam] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [herhaling, setHerhaling] = useState("");
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  // Na een geslaagde aanvraag: de gebruikersnaam die de API toekende. Die tonen we, want daarmee
  // logt de aanvrager straks in – hij kiest hem niet zelf.
  const [toegekend, setToegekend] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFout(null);
    if (password.length < 8) {
      setFout("Kies een wachtwoord van minimaal 8 tekens.");
      return;
    }
    if (password !== herhaling) {
      setFout("De wachtwoorden komen niet overeen.");
      return;
    }
    setBezig(true);
    try {
      const res = await fetch("/api/registreren", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voornaam, achternaam, email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        if (res.status === 409) {
          setFout("Er is al een account of aanvraag met dit e-mailadres.");
        } else if (res.status === 429) {
          setFout("Te veel aanvragen. Wacht even en probeer het opnieuw.");
        } else {
          setFout(`Aanvragen mislukt${body?.detail ? `: ${body.detail}` : ""}.`);
        }
        return;
      }
      const body = (await res.json()) as { userid: string };
      setToegekend(body.userid);
    } catch {
      // Zie LoginClient: een transportfout is geen antwoord en viel dus buiten alle afhandeling.
      setFout("Aanvragen lukt nu niet – de dienst is niet bereikbaar. Probeer het zo opnieuw.");
    } finally {
      setBezig(false);
    }
  }

  if (toegekend) {
    return (
      <div className="space-y-4">
        <Melding type="bevestiging" titel="Je aanvraag is ontvangen">
          Een beheerder beoordeelt je aanvraag. Zodra die is goedgekeurd, log je in met de
          gebruikersnaam <code className="font-mono font-semibold">{toegekend}</code> en het
          wachtwoord dat je zojuist koos.
        </Melding>
        <p className="text-sm text-muted">
          Noteer die gebruikersnaam – je krijgt hier geen e-mail over. Probeer later gewoon in te
          loggen; zolang je aanvraag nog openstaat, zegt het inlogscherm dat.
        </p>
        <Link href="/login" className="block">
          <Button className="w-full">Naar het inlogscherm</Button>
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {fout && <Melding type="fout">{fout}</Melding>}
      <Field label="Voornaam" required>
        <Input
          type="text"
          autoComplete="given-name"
          required
          value={voornaam}
          onChange={(e) => setVoornaam(e.target.value)}
        />
      </Field>
      <Field label="Achternaam" required>
        <Input
          type="text"
          autoComplete="family-name"
          required
          value={achternaam}
          onChange={(e) => setAchternaam(e.target.value)}
        />
      </Field>
      <Field label="E-mailadres" required>
        <Input
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </Field>
      <Field label="Wachtwoord" hint="minimaal 8 tekens" required>
        <Input
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      <Field label="Wachtwoord herhalen" required>
        <Input
          type="password"
          autoComplete="new-password"
          required
          value={herhaling}
          onChange={(e) => setHerhaling(e.target.value)}
        />
      </Field>
      <Button type="submit" disabled={bezig} className="w-full">
        {bezig ? "Bezig…" : "Toegang aanvragen"}
      </Button>
      <p className="text-center text-sm text-muted">
        Heb je al een account?{" "}
        <Link href="/login" className="text-lint underline">
          Inloggen
        </Link>
      </p>
    </form>
  );
}
