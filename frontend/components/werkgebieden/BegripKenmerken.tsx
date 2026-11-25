"use client";

// De kenmerken van een begrip (plan lessen Termijnen-bibliotheek, V2 en V4): de klasse, het waardebereik en de eigenaar.
// De klasse rekent de api uit de dragende passages; de analist kan afwijken, altijd met een reden. Het waardebereik is
// optioneel: zonder is een voorbeeld niet te toetsen en een regel niet te bouwen.

import { BewerkKnop, BewerkVoet, useBewerken } from "@/components/ui/Bewerkbaar";
import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Field, Input, Select } from "@/components/ui/Field";
import { LeegWaarde } from "@/components/ui/Leeg";
import { Regel, Regels } from "@/components/ui/Lijst";
import { BegripBlok, type BegripWeergaveVorm } from "@/components/werkgebieden/BegripBlok";
import { geldigheidZin, klasseZin, regels, waardebereikUit, waardebereikZin, WAARDE_SOORT_LABEL } from "@/lib/begrippen";
import { JAS_KLASSEN } from "@/lib/jas";
import type { BegripStand } from "@/lib/useBegrip";
import { WAARDE_SOORTEN, type Begrip, type BegripInhoud } from "@/lib/types";

export function KenmerkenBlok({ stand, begrip, weergave, bewerkbaar, onOnbewaard }: {
  stand: BegripStand;
  begrip: Begrip;
  weergave: BegripWeergaveVorm;
  bewerkbaar: boolean;
  onOnbewaard: (onbewaard: boolean) => void;
}) {
  const i = begrip.inhoud;
  const w = i.waardebereik ?? null;
  const begin = {
    klasse: i.klasse_keuze?.klasse ?? "", reden: i.klasse_keuze?.reden ?? "", eigenaar: i.eigenaar ?? "",
    geldig_vanaf: i.geldig_vanaf ?? "", geldig_tot: i.geldig_tot ?? "",
    soort: w?.soort ?? "", eenheid: w?.eenheid ?? "", decimalen: w?.decimalen != null ? String(w.decimalen) : "",
    minimum: w?.minimum ?? "", maximum: w?.maximum ?? "", waarden: regels(w?.waarden ?? []), toelichting: w?.toelichting ?? "",
  };
  const b = useBewerken({
    begin, onOnbewaard,
    opslaan: (c) => stand.muteer((r) => stand.api.wijzig(r, {
      ...i, eigenaar: c.eigenaar.trim(), waardebereik: waardebereikUit(c), geldig_vanaf: c.geldig_vanaf, geldig_tot: c.geldig_tot,
      klasse_keuze: c.klasse ? { klasse: c.klasse, reden: c.reden.trim() } : null,
    } as BegripInhoud), { gelukt: "Opgeslagen." }),
  });
  const c = b.concept;
  const zet = (v: Partial<typeof begin>) => b.zet({ ...c, ...v });
  const k = klasseZin(begrip.klasse);
  const zonderReden = !!c.klasse && c.klasse !== begrip.klasse?.afgeleid && !c.reden.trim();
  const zonderWaarden = c.soort === "opsomming" && !c.waarden.trim();
  const omgekeerd = !!c.geldig_vanaf && !!c.geldig_tot && c.geldig_tot < c.geldig_vanaf;
  const geldig = geldigheidZin(i);

  return (
    <BegripBlok weergave={weergave} titel="Kenmerken" data-blok="kenmerken"
      toelichting="Wat voor begrip het is en welke waarde het heeft."
      acties={bewerkbaar && !b.open && <BewerkKnop wat="Kenmerken" onClick={b.start} />}>
      {b.open ? (
        <div className="space-y-4" role="group" aria-label="Kenmerken bewerken" onKeyDown={b.toetsen(false)}>
          <Field label="Klasse" hint={begrip.klasse?.afgeleid ? `uit de passages: ${begrip.klasse.afgeleid}` : "nog geen passage"}>
            <Select value={c.klasse} onChange={(e) => zet({ klasse: e.target.value })}>
              <option value="">Zoals de passages zeggen</option>
              {JAS_KLASSEN.map((kl) => <option key={kl} value={kl}>{kl}</option>)}
            </Select>
          </Field>
          {c.klasse && c.klasse !== begrip.klasse?.afgeleid && (
            <Field label="Reden" hint="waarom het begrip een andere klasse heeft dan de passages" required>
              <AutoTextarea value={c.reden} onChange={(e) => zet({ reden: e.target.value })} rows={2} maxLength={2000} />
            </Field>
          )}
          <Field label="Soort waarde" hint="leeg als het begrip geen waarde heeft (een partij, een object)">
            <Select value={c.soort} onChange={(e) => zet({ soort: e.target.value })}>
              <option value="">Geen</option>
              {WAARDE_SOORTEN.map((s) => <option key={s} value={s}>{WAARDE_SOORT_LABEL[s]}</option>)}
            </Select>
          </Field>
          {c.soort && c.soort !== "opsomming" && c.soort !== "ja_nee" && (
            <div className="space-y-4">
              <Field label="Eenheid" hint="euro, dagen, maanden"><Input value={c.eenheid} onChange={(e) => zet({ eenheid: e.target.value })} maxLength={80} /></Field>
              {(c.soort === "bedrag" || c.soort === "aantal") && (
                <Field label="Decimalen"><Input inputMode="numeric" value={c.decimalen} onChange={(e) => zet({ decimalen: e.target.value.replace(/\D/g, "") })} maxLength={2} /></Field>
              )}
              <Field label="Vanaf"><Input value={c.minimum} onChange={(e) => zet({ minimum: e.target.value })} maxLength={40} /></Field>
              <Field label="Tot en met"><Input value={c.maximum} onChange={(e) => zet({ maximum: e.target.value })} maxLength={40} /></Field>
            </div>
          )}
          {c.soort === "opsomming" && (
            <Field label="Toegestane waarden" hint="één per regel" required>
              <AutoTextarea value={c.waarden} onChange={(e) => zet({ waarden: e.target.value })} rows={3} />
            </Field>
          )}
          {c.soort && (
            <Field label="Toelichting bij de waarde" hint="bijvoorbeeld hoe er wordt afgerond">
              <Input value={c.toelichting} onChange={(e) => zet({ toelichting: e.target.value })} maxLength={1000} />
            </Field>
          )}
          <Field label="Geldig vanaf" hint="per wanneer deze betekenis geldt; leeg als dat niet vastligt">
            <Input type="date" value={c.geldig_vanaf} onChange={(e) => zet({ geldig_vanaf: e.target.value })} />
          </Field>
          <Field label="Geldig tot en met" hint="leeg zolang er geen einddatum is">
            <Input type="date" value={c.geldig_tot} onChange={(e) => zet({ geldig_tot: e.target.value })} />
          </Field>
          <Field label="Eigenaar" hint="wie het begrip beheert">
            <Input value={c.eigenaar} onChange={(e) => zet({ eigenaar: e.target.value })} maxLength={200} />
          </Field>
          <BewerkVoet onAnnuleer={b.annuleer} onOpslaan={() => void b.slaOp()} bezig={b.bezig}
            gewijzigd={b.gewijzigd && !zonderReden && !zonderWaarden && !omgekeerd}
            fout={b.fout ?? (omgekeerd ? "Geldig tot ligt vóór geldig vanaf." : undefined)} />
        </div>
      ) : (
        <Regels data-begrip-kenmerken>
          <Regel naam="Klasse">
            {k.klasse ? <>{k.klasse}{k.herkomst && <span className="text-muted"> · {k.herkomst}</span>}
              {i.klasse_keuze?.reden && <span className="block text-xs text-muted">{i.klasse_keuze.reden}</span>}</>
              : <LeegWaarde>Nog geen passage.</LeegWaarde>}
          </Regel>
          <Regel naam="Waarde">
            {w ? waardebereikZin(w) : <LeegWaarde>Nog geen waardebereik.</LeegWaarde>}
          </Regel>
          {geldig && <Regel naam="Geldig">{geldig}</Regel>}
          {i.eigenaar && <Regel naam="Eigenaar">{i.eigenaar}</Regel>}
        </Regels>
      )}
    </BegripBlok>
  );
}
