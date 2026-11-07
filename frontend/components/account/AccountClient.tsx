"use client";

import { useCallback, useEffect, useState } from "react";
import { KopieerVeld } from "@/components/admin/KopieerVeld";
import { Button } from "@/components/ui/Button";
import { FormKnoppen, FormRij, SettingGroup, SettingList, SettingRow } from "@/components/ui/SettingRow";
import { Field, Input } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { StatusLabel } from "@/components/ui/Lijst";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { activate2fa, begin2fa, disable2fa, getAccount, isApiError, vervangHerstelcodes } from "@/lib/api";
import type { MeAccount } from "@/lib/types";

/** Haal het base32-secret uit de otpauth://-URI voor handmatige invoer in de authenticator-app. */
function secretUit(uri: string): string {
  try {
    return new URL(uri).searchParams.get("secret") ?? "";
  } catch {
    return "";
  }
}

/** Vraagt één code (uit de app of een herstelcode) om iets aan actieve 2FA te doen. */
function CodeFormulier({ uitleg, knop, gevaar = false, bezig, onBevestig, onAnnuleer }: {
  uitleg: React.ReactNode;
  knop: string;
  gevaar?: boolean;
  bezig: boolean;
  onBevestig: (code: string) => Promise<void>;
  onAnnuleer: () => void;
}) {
  const [code, setCode] = useState("");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void onBevestig(code.trim());
      }}
      className="mt-4 space-y-3"
    >
      <p className="text-sm text-muted">{uitleg}</p>
      <FormRij>
        <Field label="Code" hint="6 cijfers uit de app, of een herstelcode">
          <Input autoComplete="one-time-code" required value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <FormKnoppen>
          <Button type="submit" size="sm" variant={gevaar ? "danger" : undefined} disabled={bezig}>
            {knop}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={onAnnuleer} disabled={bezig}>
            Annuleren
          </Button>
        </FormKnoppen>
      </FormRij>
    </form>
  );
}

export function AccountClient() {
  const [account, setAccount] = useState<MeAccount | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  // Bevestigingsformulier bij het inschakelen: koppelen vraagt het huidige wachtwoord.
  const [inschakelen, setInschakelen] = useState(false);
  const [wachtwoord, setWachtwoord] = useState("");
  // Lopende 2FA-koppeling: de QR/secret + het in te voeren code-veld.
  const [koppeling, setKoppeling] = useState<{ uri: string; qr: string } | null>(null);
  const [code, setCode] = useState("");
  // Welke actie op actieve 2FA om een code vraagt.
  const [codeVoor, setCodeVoor] = useState<"uitschakelen" | "herstelcodes" | null>(null);
  // Net gemaakte herstelcodes: dit is de enige keer dat ze te zien zijn.
  const [herstelcodes, setHerstelcodes] = useState<string[] | null>(null);
  const [bezig, setBezig] = useState(false);

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setAccount(await getAccount());
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch (geen synchrone render-cascade).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  function melden(e: unknown) {
    setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
  }

  async function onStart(e: React.FormEvent) {
    e.preventDefault();
    setFout(null);
    setBezig(true);
    try {
      const { otpauth_uri } = await begin2fa(wachtwoord);
      // qrcode wordt alleen hier gebruikt, bij het activeren van 2FA. Statisch importeren zette
      // de hele encoder in de bundel van iedereen die zijn account opent.
      const { default: QRCode } = await import("qrcode");
      const qr = await QRCode.toDataURL(otpauth_uri, { margin: 1, width: 200 });
      setKoppeling({ uri: otpauth_uri, qr });
      setCode("");
      setWachtwoord("");
      setInschakelen(false);
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  async function onBevestig(e: React.FormEvent) {
    e.preventDefault();
    setFout(null);
    setBezig(true);
    try {
      setHerstelcodes(await activate2fa(code.trim()));
      setKoppeling(null);
      setCode("");
      await laad();
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  async function onUitschakelen(code: string) {
    setFout(null);
    setBezig(true);
    try {
      await disable2fa(code);
      setCodeVoor(null);
      setHerstelcodes(null);
      await laad();
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  async function onNieuweCodes(code: string) {
    setFout(null);
    setBezig(true);
    try {
      setHerstelcodes(await vervangHerstelcodes(code));
      setCodeVoor(null);
      await laad();
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  return (
    <SettingGroup
      titel="Beveiliging"
      omschrijving={
        account?.role === "beheerder"
          ? "Tweestapsverificatie is voor beheerders verplicht: het inloggen vraagt dan om een code uit je authenticator-app."
          : "Tweestapsverificatie is optioneel. Staat die aan, dan vraagt het inloggen om een code uit je authenticator-app."
      }
    >
      {fout && (
        <Melding type="fout" className="mb-3">
          {fout}
        </Melding>
      )}

      {account?.tfa_nodig && (
        <Melding type="waarschuwing" titel="Het beheer is dicht tot je koppelt" className="mb-3">
          <p className="text-sm">Koppel hieronder een authenticator-app. De rest van de app werkt gewoon.</p>
        </Melding>
      )}

      {herstelcodes && (
        <Melding type="waarschuwing" titel="Herstelcodes – bewaar ze nu" className="mb-3">
          <p className="mb-2 text-sm">
            Ben je je authenticator-app kwijt, dan log je met een van deze codes in. Elke code werkt één keer. Je
            ziet ze hierna niet meer terug; bewaar ze buiten je telefoon.
          </p>
          <KopieerVeld waarde={herstelcodes.join("\n")} label="Herstelcodes" />
          <Button size="sm" variant="ghost" className="mt-2" onClick={() => setHerstelcodes(null)}>
            Ik heb ze bewaard
          </Button>
        </Melding>
      )}

      {!account && !fout && <SkeletonCard regels={2} />}
      {account && (
        <div>
          <SettingList>
            <SettingRow label="Tweestapsverificatie">
              <StatusLabel toon={account.totp_enabled ? "groen" : "neutraal"}>{account.totp_enabled ? "Aan" : "Uit"}</StatusLabel>
              {account.totp_enabled && codeVoor !== "uitschakelen" && (
                <Button size="sm" variant="secondary" onClick={() => setCodeVoor("uitschakelen")}>Uitschakelen</Button>
              )}
              {!account.totp_enabled && !koppeling && !inschakelen && (
                <Button size="sm" onClick={() => setInschakelen(true)}>2FA inschakelen</Button>
              )}
            </SettingRow>
            {account.totp_enabled && (
              <SettingRow label="Herstelcodes">
                <StatusLabel toon={account.herstelcodes_over > 0 ? "neutraal" : "rood"}>
                  {account.herstelcodes_over} over
                </StatusLabel>
                {codeVoor !== "herstelcodes" && (
                  <Button size="sm" variant="secondary" onClick={() => setCodeVoor("herstelcodes")}>
                    {account.herstelcodes_over > 0 ? "Nieuwe codes" : "Codes aanmaken"}
                  </Button>
                )}
              </SettingRow>
            )}
          </SettingList>

          {account.totp_enabled ? (
            <>
              {codeVoor === "uitschakelen" && (
                <CodeFormulier
                  uitleg={
                    account.role === "beheerder"
                      ? "Voer een code in om tweestapsverificatie uit te schakelen. Daarna is het beheer dicht tot je opnieuw koppelt."
                      : "Voer een code in om tweestapsverificatie uit te schakelen."
                  }
                  knop="2FA uitschakelen"
                  gevaar
                  bezig={bezig}
                  onBevestig={onUitschakelen}
                  onAnnuleer={() => setCodeVoor(null)}
                />
              )}
              {codeVoor === "herstelcodes" && (
                <CodeFormulier
                  uitleg="Voer een code in voor een nieuwe set herstelcodes. De oude codes vervallen."
                  knop="Codes aanmaken"
                  bezig={bezig}
                  onBevestig={onNieuweCodes}
                  onAnnuleer={() => setCodeVoor(null)}
                />
              )}
            </>
          ) : inschakelen ? (
            <form onSubmit={onStart} className="mt-4 space-y-3">
              <p className="text-sm text-muted">
                Voer je huidige wachtwoord in om een authenticator-app aan dit account te koppelen.
              </p>
              <FormRij>
                <Field label="Huidig wachtwoord">
                  <Input
                    type="password"
                    autoComplete="current-password"
                    required
                    value={wachtwoord}
                    onChange={(e) => setWachtwoord(e.target.value)}
                  />
                </Field>
                <FormKnoppen>
                  <Button type="submit" size="sm" disabled={bezig}>
                    Doorgaan
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => { setWachtwoord(""); setInschakelen(false); }}
                    disabled={bezig}
                  >
                    Annuleren
                  </Button>
                </FormKnoppen>
              </FormRij>
            </form>
          ) : koppeling ? (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-muted">
                Scan de QR-code met je authenticator-app (of voer de sleutel handmatig in) en
                bevestig met de getoonde 6-cijferige code.
              </p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={koppeling.qr} alt="QR-code voor 2FA" width={200} height={200} className="rounded-field border border-line" />
              <p className="text-xs text-muted">
                Handmatige sleutel:{" "}
                <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-xs">{secretUit(koppeling.uri)}</code>
              </p>
              <form onSubmit={onBevestig}>
                <FormRij>
                  <Field label="Code uit de app" hint="6 cijfers">
                    <Input
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      required
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                    />
                  </Field>
                  <FormKnoppen>
                    <Button type="submit" size="sm" disabled={bezig}>
                      Bevestigen
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setKoppeling(null)}
                      disabled={bezig}
                    >
                      Annuleren
                    </Button>
                  </FormKnoppen>
                </FormRij>
              </form>
            </div>
          ) : null}
        </div>
      )}
    </SettingGroup>
  );
}
