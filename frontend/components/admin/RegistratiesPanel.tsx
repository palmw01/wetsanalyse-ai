"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Card } from "@/components/ui/Card";
import { SettingGroup } from "@/components/ui/SettingRow";
import { Field, Input, Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Tag } from "@/components/ui/Badge";
import {
  approveRegistratie,
  approveRegistraties,
  deleteRegistratie,
  isApiError,
  listRegistraties,
  rejectRegistratie,
} from "@/lib/api";
import type { RegistratieOut, Role } from "@/lib/types";

/** Nette datumweergave; de API levert ISO-8601 met offset. */
function datum(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" });
}

export function RegistratiesPanel() {
  const [aanvragen, setAanvragen] = useState<RegistratieOut[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [toonGoedgekeurd, setToonGoedgekeurd] = useState(false);
  // Per aanvraag de (eventueel gecorrigeerde) userid en de rol die de beheerder wil toekennen.
  const [keuze, setKeuze] = useState<Record<number, { userid: string; role: Role }>>({});
  const [geselecteerd, setGeselecteerd] = useState<Set<number>>(new Set());

  const laad = useCallback(async () => {
    setFout(null);
    try {
      const rijen = await listRegistraties(toonGoedgekeurd ? undefined : "aangevraagd");
      setAanvragen(rijen);
      // De voorstellen als startwaarde in de formuliervelden; wat de beheerder al typte blijft staan.
      setKeuze((vorig) => {
        const volgend = { ...vorig };
        for (const r of rijen) {
          if (!volgend[r.id]) volgend[r.id] = { userid: r.userid_voorstel, role: "analist" };
        }
        return volgend;
      });
      setGeselecteerd((vorig) => new Set([...vorig].filter((id) => rijen.some((r) => r.id === id))));
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
      setAanvragen([]);
    }
  }, [toonGoedgekeurd]);

  useEffect(() => {
    // Data-load bij mount en bij het wisselen van filter: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  function melden(e: unknown) {
    setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
  }

  function zet(id: number, patch: Partial<{ userid: string; role: Role }>) {
    setKeuze((vorig) => ({
      ...vorig,
      [id]: { ...(vorig[id] ?? { userid: "", role: "analist" }), ...patch },
    }));
  }

  async function onGoedkeuren(r: RegistratieOut) {
    // Guard tegen dubbelklik: een tweede aanroep loopt stuk op "al afgehandeld", met een
    // foutmelding náást een geslaagde goedkeuring.
    if (bezig) return;
    setBezig(true);
    setFout(null);
    setMelding(null);
    try {
      const k = keuze[r.id] ?? { userid: r.userid_voorstel, role: "analist" as Role };
      const user = await approveRegistratie(r.id, { userid: k.userid.trim(), role: k.role });
      setMelding(`${user.userid} kan nu inloggen met het eigen wachtwoord (rol: ${user.role}).`);
      await laad();
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  async function onAfwijzen(r: RegistratieOut, reden: string) {
    try {
      await rejectRegistratie(r.id, reden);
      await laad();
    } catch (e) {
      melden(e);
    }
  }

  async function onVerwijderen(r: RegistratieOut) {
    try {
      await deleteRegistratie(r.id);
      await laad();
    } catch (e) {
      melden(e);
    }
  }

  async function onBulk() {
    if (bezig || geselecteerd.size === 0) return;
    setBezig(true);
    setFout(null);
    setMelding(null);
    try {
      // Bulk neemt bewust het vóórstel over: wie een userid wil corrigeren doet dat per aanvraag.
      const regels = await approveRegistraties([...geselecteerd], "analist");
      const gelukt = regels.filter((x) => x.ok);
      const mislukt = regels.filter((x) => !x.ok);
      setMelding(
        `${gelukt.length} van ${regels.length} goedgekeurd als analist` +
          (gelukt.length ? `: ${gelukt.map((x) => x.userid).join(", ")}` : "") +
          ".",
      );
      if (mislukt.length) setFout(mislukt.map((x) => `#${x.id}: ${x.fout}`).join(" · "));
      setGeselecteerd(new Set());
      await laad();
    } catch (e) {
      melden(e);
    } finally {
      setBezig(false);
    }
  }

  function wissel(id: number) {
    setGeselecteerd((vorig) => {
      const volgend = new Set(vorig);
      if (volgend.has(id)) volgend.delete(id);
      else volgend.add(id);
      return volgend;
    });
  }

  const open = (aanvragen ?? []).filter((r) => r.status === "aangevraagd");

  return (
    <SettingGroup
      titel="Aanvragen"
      count={open.length}
      omschrijving="Wie toegang heeft aangevraagd via het registratieformulier. Goedkeuren maakt het account aan; de aanvrager logt in met het wachtwoord dat hij zelf koos. Afwijzen verwijdert de aanvraag, zodat het e-mailadres weer vrij is."
    >
      {fout && (
        <Melding type="fout" className="mb-3">
          {fout}
        </Melding>
      )}
      {melding && (
        <Melding type="bevestiging" className="mb-3">
          {melding}
        </Melding>
      )}

      <ButtonRow align="between" className="mb-4">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            className="h-4 w-4 accent-lint"
            checked={toonGoedgekeurd}
            onChange={(e) => setToonGoedgekeurd(e.target.checked)}
          />
          Ook goedgekeurde aanvragen tonen
        </label>
        <Button
          size="sm"
          onClick={onBulk}
          disabled={bezig || geselecteerd.size === 0}
        >
          {geselecteerd.size > 0
            ? `${geselecteerd.size} goedkeuren als analist`
            : "Geselecteerde goedkeuren"}
        </Button>
      </ButtonRow>

      {aanvragen === null ? (
        <p className="text-sm text-muted">Laden…</p>
      ) : aanvragen.length === 0 ? (
        <p className="text-sm text-muted">
          {toonGoedgekeurd ? "Nog geen aanvragen." : "Geen openstaande aanvragen."}
        </p>
      ) : (
        <div className="space-y-3">
          {aanvragen.map((r) => {
            const k = keuze[r.id] ?? { userid: r.userid_voorstel, role: "analist" as Role };
            const openstaand = r.status === "aangevraagd";
            return (
              <Card key={r.id} className="p-3">
                <div className="flex flex-wrap items-center gap-3">
                  {openstaand && (
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-lint"
                      aria-label={`${r.voornaam} ${r.achternaam} selecteren`}
                      checked={geselecteerd.has(r.id)}
                      onChange={() => wissel(r.id)}
                    />
                  )}
                  <span className="break-words font-display font-semibold text-ink">
                    {r.voornaam} {r.achternaam}
                  </span>
                  <span className="min-w-0 break-words text-sm text-muted">{r.email}</span>
                  <span className="text-sm text-muted">aangevraagd op {datum(r.created)}</span>
                  {!openstaand && <Tag>{r.status}</Tag>}
                </div>

                {r.status === "goedgekeurd" && (
                  <p className="mt-2 text-sm text-muted">
                    Account <span className="font-mono">{r.userid}</span> aangemaakt.
                  </p>
                )}

                {openstaand && (
                  <>
                    <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
                      <Field label="Gebruikersnaam" hint="voorstel — aan te passen">
                        <Input
                          type="text"
                          autoCapitalize="none"
                          value={k.userid}
                          onChange={(e) => zet(r.id, { userid: e.target.value })}
                        />
                      </Field>
                      <Field label="Rol">
                        <Select
                          value={k.role}
                          onChange={(e) => zet(r.id, { role: e.target.value as Role })}
                        >
                          <option value="analist">analist</option>
                          <option value="beheerder">beheerder</option>
                        </Select>
                      </Field>
                    </div>
                    <ButtonRow align="start" className="mt-3">
                      <Button size="sm" disabled={bezig} onClick={() => onGoedkeuren(r)}>
                        Goedkeuren
                      </Button>
                      <AfwijzenKnop onAfwijzen={(reden) => onAfwijzen(r, reden)} />
                    </ButtonRow>
                  </>
                )}

                {!openstaand && (
                  <ButtonRow align="start" className="mt-3">
                    <BevestigKnop
                      onBevestig={() => onVerwijderen(r)}
                      bevestigTekst={`Uit de lijst halen? (het account blijft bestaan)`}
                      className="focus-ring inline-flex min-h-[40px] shrink-0 items-center justify-center rounded-field border border-fout px-3 text-sm font-medium text-fout transition coarse:min-h-[48px]"
                      bevestigClassName="bg-fout text-paper"
                    >
                      Uit de lijst halen
                    </BevestigKnop>
                  </ButtonRow>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </SettingGroup>
  );
}

/** Afwijzen in twee stappen: eerst een redenveld openklappen, dan bevestigen. Afwijzen VERWIJDERT
 *  de aanvraag – het e-mailadres en het volgnummer komen meteen weer vrij. De reden gaat daarom
 *  alleen naar het security-log, niet naar de aanvrager (er gaat geen e-mail uit) en ook niet naar
 *  een rij die je later nog terugziet. */
function AfwijzenKnop({ onAfwijzen }: { onAfwijzen: (reden: string) => void }) {
  const [open, setOpen] = useState(false);
  const [reden, setReden] = useState("");

  if (!open) {
    return (
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        Afwijzen
      </Button>
    );
  }
  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-end">
      <div className="min-w-[14rem] flex-1">
        <Field label="Reden" hint="komt alleen in het logboek">
          <Input
            type="text"
            autoFocus
            value={reden}
            onChange={(e) => setReden(e.target.value)}
            placeholder="bijv. onbekende aanvrager"
          />
        </Field>
      </div>
      <ButtonRow align="start">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setOpen(false);
            onAfwijzen(reden);
          }}
        >
          Afwijzen en verwijderen
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Annuleren
        </Button>
      </ButtonRow>
    </div>
  );
}
