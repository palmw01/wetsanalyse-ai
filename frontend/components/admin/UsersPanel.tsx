"use client";

import { useCallback, useEffect, useState } from "react";
import { BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Card } from "@/components/ui/Card";
import { SettingGroup } from "@/components/ui/SettingRow";
import { Field, Input, Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { MeerMenu, MenuKnop, MenuVerwijder } from "@/components/ui/MeerMenu";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { BudgetBeleidBlok } from "@/components/admin/BudgetBeleidBlok";
import { KopieerVeld } from "@/components/admin/KopieerVeld";
import { Meter } from "@/components/ui/Meter";
import {
  createUser,
  deleteUser,
  isApiError,
  listUsers,
  listVerbruik,
  patchUser,
  resetUserPassword,
} from "@/lib/api";
import { tokensKort } from "@/lib/tokenbudget";
import type { Role, UserOut, VerbruikRegel } from "@/lib/types";
import { StatusLabel } from "@/components/ui/Lijst";

export function UsersPanel() {
  const [users, setUsers] = useState<UserOut[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [toevoegen, setToevoegen] = useState(false);
  const [nieuwUserid, setNieuwUserid] = useState("");
  const [nieuwEmail, setNieuwEmail] = useState("");
  const [nieuwRol, setNieuwRol] = useState<Role>("analist");
  // Eenmalig getoond tijdelijk wachtwoord (na aanmaken of resetten).
  const [tijdelijk, setTijdelijk] = useState<{ userid: string; wachtwoord: string } | null>(null);
  // Stand per gebruiker, apart opgehaald: één query voor iedereen in plaats van één per rij.
  const [verbruik, setVerbruik] = useState<Record<string, VerbruikRegel>>({});

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setUsers(await listUsers());
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
      setUsers([]);
    }
    try {
      const regels = await listVerbruik();
      setVerbruik(Object.fromEntries(regels.map((r) => [r.userid, r])));
    } catch {
      /* Stil: de meters zijn aanvullend, de gebruikerslijst moet hoe dan ook bruikbaar blijven. */
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

  async function onAanmaken(e: React.FormEvent) {
    e.preventDefault();
    // Zonder deze guard levert een dubbelklik een tweede aanroep op die op een duplicaat stukloopt,
    // met een foutmelding náást het net getoonde tijdelijke wachtwoord – verwarrend op precies het
    // moment dat je dat wachtwoord moet overnemen.
    if (bezig) return;
    setBezig(true);
    setFout(null);
    try {
      const res = await createUser(nieuwUserid.trim(), nieuwEmail.trim(), nieuwRol);
      setTijdelijk({ userid: res.userid, wachtwoord: res.temp_password });
      setNieuwUserid("");
      setNieuwEmail("");
      setNieuwRol("analist");
      setToevoegen(false);
      await laad();
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  async function onRol(u: UserOut, role: Role) {
    try {
      await patchUser(u.userid, { role });
      await laad();
    } catch (e) {
      melden(e);
    }
  }

  async function onActief(u: UserOut) {
    try {
      await patchUser(u.userid, { active: !u.active });
      await laad();
    } catch (e) {
      melden(e);
    }
  }

  async function onBudget(u: UserOut, waarde: string) {
    const leeg = waarde.trim() === "";
    try {
      await patchUser(
        u.userid,
        leeg ? { token_budget_wissen: true } : { token_budget: Math.max(0, Number(waarde) || 0) },
      );
      await laad();
    } catch (e) {
      melden(e);
    }
  }

  async function onReset(u: UserOut) {
    try {
      const res = await resetUserPassword(u.userid);
      setTijdelijk({ userid: res.userid, wachtwoord: res.temp_password });
    } catch (e) {
      melden(e);
    }
  }

  // De bevestiging zit in de knop (twee klikken), zoals overal in deze app.
  async function onVerwijder(u: UserOut) {
    try {
      await deleteUser(u.userid);
      await laad();
    } catch (e) {
      melden(e);
    }
  }

  return (
    <SettingGroup titel="Gebruikers" count={users?.length} omschrijving="Wie toegang heeft tot de webapp."
      acties={!toevoegen && <Button size="sm" onClick={() => setToevoegen(true)}>Nieuwe gebruiker</Button>}>
      {fout && (
        <Melding type="fout" className="mb-3">
          {fout}
        </Melding>
      )}

      {tijdelijk && (
        <Melding type="waarschuwing" titel="Tijdelijk wachtwoord – noteer dit nu" className="mb-3">
          <p className="mb-2 text-sm">
            Voor <span className="font-medium">{tijdelijk.userid}</span>. Dit wachtwoord wordt niet opnieuw getoond. Deel het
            veilig; de gebruiker logt er meteen mee in.
          </p>
          <KopieerVeld waarde={tijdelijk.wachtwoord} label="Tijdelijk wachtwoord" />
          <ButtonRow align="start" className="mt-2">
            <Button size="sm" variant="ghost" onClick={() => setTijdelijk(null)}>
              Sluiten
            </Button>
          </ButtonRow>
        </Melding>
      )}

      {toevoegen && (
        <Card className="mb-4 p-3" data-gebruiker-nieuw>
          <form onSubmit={onAanmaken}>
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
              <Field label="Gebruikersnaam">
                <Input
                  type="text"
                  required
                  autoFocus
                  autoCapitalize="none"
                  placeholder="jdoe"
                  value={nieuwUserid}
                  onChange={(e) => setNieuwUserid(e.target.value)}
                />
              </Field>
              <div className="min-w-[14rem] flex-1">
                <Field label="E-mailadres">
                  <Input
                    type="email"
                    required
                    placeholder="naam@belastingdienst.nl"
                    value={nieuwEmail}
                    onChange={(e) => setNieuwEmail(e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Rol">
                <Select value={nieuwRol} onChange={(e) => setNieuwRol(e.target.value as Role)}>
                  <option value="analist">analist</option>
                  <option value="beheerder">beheerder</option>
                </Select>
              </Field>
            </div>
            <BewerkVoet submit bezig={bezig} gewijzigd opslaanTekst="Gebruiker toevoegen" onAnnuleer={() => setToevoegen(false)} />
          </form>
        </Card>
      )}

      <BudgetBeleidBlok onGewijzigd={() => void laad()} />

      {users === null ? (
        <SkeletonCard regels={2} />
      ) : users.length === 0 ? (
        <p className="text-sm text-muted">Nog geen gebruikers.</p>
      ) : (
        <div className="space-y-3">
          {users.map((u) => (
            <Card key={u.userid} className="p-3" data-gebruiker={u.userid}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="break-words font-display font-semibold text-ink">{u.userid}</span>
                  <span className="min-w-0 break-words text-sm text-muted">{u.email}</span>
                  <StatusLabel toon={u.role === "beheerder" ? "lint" : "neutraal"}>{u.role}</StatusLabel>
                  {u.totp_enabled && <StatusLabel toon="groen">2FA aan</StatusLabel>}
                  {!u.active && (
                    <StatusLabel toon="rood">gedeactiveerd</StatusLabel>
                  )}
                  {verbruik[u.userid]?.geblokkeerd && (
                    <StatusLabel toon="rood">budget op</StatusLabel>
                  )}
                </div>
                <MeerMenu label={`Acties voor ${u.userid}`}>
                  {(sluit) => (
                    <>
                      <MenuKnop onClick={() => { sluit(); void onRol(u, u.role === "beheerder" ? "analist" : "beheerder"); }}>
                        {u.role === "beheerder" ? "Maak analist" : "Maak beheerder"}
                      </MenuKnop>
                      <MenuKnop onClick={() => { sluit(); void onActief(u); }}>
                        {u.active ? "Deactiveren" : "Activeren"}
                      </MenuKnop>
                      <MenuKnop onClick={() => { sluit(); void onReset(u); }}>Wachtwoord resetten</MenuKnop>
                      <MenuVerwijder vraag={`"${u.userid}" verwijderen?`} onBevestig={() => onVerwijder(u)} />
                    </>
                  )}
                </MeerMenu>
              </div>

              {/* Verbruik + een afwijkend budget. Leeg laten = volg het systeembeleid; het veld
                  slaat op bij verlaten, zoals de andere acties hier direct doorwerken. */}
              {verbruik[u.userid] && (
                <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-3">
                  <div className="min-w-[12rem] flex-1">
                    <div className="flex items-baseline justify-between gap-2 text-xs text-muted">
                      <span>
                        {tokensKort(verbruik[u.userid].gebruikt)} van{" "}
                        {tokensKort(verbruik[u.userid].budget)} tokens
                      </span>
                      <span>{verbruik[u.userid].percentage}%</span>
                    </div>
                    <Meter
                      percentage={verbruik[u.userid].percentage}
                      label={`Tokenverbruik van ${u.userid}`}
                      toon="verbruik"
                      className="mt-1"
                    />
                  </div>
                  <label className="flex items-center gap-2 text-xs text-muted">
                    Eigen budget
                    <Input
                      type="number"
                      min={0}
                      step={1000}
                      placeholder="standaard"
                      className="w-32"
                      defaultValue={u.token_budget ?? ""}
                      onBlur={(e) => {
                        const nieuw = e.target.value.trim();
                        const huidig = u.token_budget === null ? "" : String(u.token_budget);
                        if (nieuw !== huidig) void onBudget(u, nieuw);
                      }}
                    />
                  </label>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </SettingGroup>
  );
}
