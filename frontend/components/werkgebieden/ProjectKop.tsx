"use client";

import { MENU_PANEEL, MENU_RIJ } from "@/components/ui/Menu";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Dialog } from "@/components/ui/Dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Meer } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { MENU_PANEEL, MENU_RIJ } from "@/components/ui/Menu";
import { PaginaKop, Stip, TabLinks, type Kruimel } from "@/components/ui/Pagina";
import { Popover } from "@/components/ui/Popover";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { haalThemaVoorstel, wijzigWerkgebied } from "@/lib/api";
import { themaGroepen } from "@/lib/tooiThemas";
import type { ThemaVoorstel, Werkgebied, WerkgebiedStatus } from "@/lib/types";
import { DOSSIER_VELDEN, STATUS_LABEL, type DossierVeld } from "@/lib/werkgebied";
import { ARTEFACT_SOORTEN, PROJECT_TABS, historiePad, projectPad, type ProjectTab } from "@/lib/werkgebiedPaden";

/** De kop van een werkgebied boven de vier tabs (mock-up v4, `projectHead` + `tabbar`): de naam, één zin,
 *  status en wanneer gewijzigd, en twee knoppen – *Gegevens bewerken* en *Nieuw gesprek*. Historie en
 *  verwijderen staan in het menu ernaast. */
export function ProjectKop({ tab }: { tab: ProjectTab }) {
  const { wg, muteer, verwijder, stand } = useWerkgebied();
  const tellers: Partial<Record<ProjectTab, number>> = {
    gesprekken: stand.gesprekken?.length, bronnen: wg.bronnen.length, artefacten: ARTEFACT_SOORTEN.length,
  };
  const [bewerken, setBewerken] = useState(false);
  const kruimels: Kruimel[] = [{ label: "Werkgebieden", href: "/werkgebieden" }, { label: wg.naam, href: projectPad(wg.id) }];
  if (tab !== "overzicht") kruimels.push({ label: PROJECT_TABS.find((t) => t.key === tab)!.label });

  return (
    <>
      <PaginaKop
        kruimels={kruimels}
        titel={wg.naam}
        sub="Analysewerkruimte rond één analysevraag: gesprekken, bronnen en analyseproducten bij elkaar."
        meta={
          <>
            <StatusLabel>{STATUS_LABEL[wg.status]}</StatusLabel>
            <Stip />
            <span>Gewijzigd {datum(wg.gewijzigd)}</span>
            {wg.peildatum && <><Stip /><span>Peildatum {wg.peildatum}</span></>}
            <Stip />
            <span>Aangemaakt door {wg.aangemaakt_door}</span>
          </>
        }
        acties={
          <>
            <Button variant="secondary" size="sm" onClick={() => setBewerken(true)}>Gegevens bewerken</Button>
            <Link href={`/workbench?werkgebied=${encodeURIComponent(wg.id)}`}
              className="focus-ring inline-flex min-h-[32px] items-center justify-center rounded-full bg-accent px-3 py-1.5 text-sm font-medium text-paper hover:bg-accent-soft coarse:min-h-[44px]">
              Nieuw gesprek
            </Link>
            <Popover ariaLabel="Meer voor dit werkgebied" className={`w-56 ${MENU_PANEEL}`}
              trigger={(open, toggle) => (
                <button type="button" onClick={toggle} aria-expanded={open} aria-label="Meer voor dit werkgebied"
                  className="focus-ring inline-flex min-h-[32px] min-w-[32px] items-center justify-center self-start rounded-full border border-line text-muted hover:bg-surface hover:text-lint coarse:min-h-[44px] coarse:min-w-[44px] sm:self-auto">
                  <Meer />
                </button>
              )}>
              <Link href={historiePad(wg.id)} className={MENU_RIJ}>
                Historie
              </Link>
              <div className="px-2.5 py-1.5">
                <VerwijderKnop soort="werkgebied" onBevestig={verwijder} />
              </div>
            </Popover>
          </>
        }
      />
      <TabLinks label="Werkgebied" actief={tab}
        tabs={PROJECT_TABS.map((t) => ({ key: t.key, label: t.label, href: projectPad(wg.id, t.key), telling: tellers[t.key] }))} />
      {bewerken && (
        <GegevensDialoog wg={wg} onSluit={() => setBewerken(false)}
          onBewaar={async (w) => {
            if (await muteer((r) => wijzigWerkgebied(wg.id, { ...w, verwachte_revisie: r }), { gelukt: "Opgeslagen." })) setBewerken(false);
          }} />
      )}
    </>
  );
}

export function datum(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("nl-NL", { day: "numeric", month: "short", year: "numeric" });
}

// Startactiviteit a en activiteit 1b: wat de velden vragen, in de woorden van de vraagkaarten.
const DOSSIER_HINT: Partial<Record<DossierVeld, string>> = {
  aanleiding: "waarom we analyseren",
  context: "de situatie eromheen",
  doel: "wat de analyse moet opleveren",
  praktijkvoorbeeld: "hoe een burger of bedrijf het doorloopt",
};

/** Naam, dossier, peildatum en status van het werkgebied bewerken, in een venster boven de pagina. */
export function GegevensDialoog({ wg, onBewaar, onSluit }: {
  wg: Werkgebied;
  onBewaar: (w: { naam: string; peildatum: string | null; status: WerkgebiedStatus; thema: string } & Record<DossierVeld, string>) => Promise<void>;
  onSluit: () => void;
}) {
  const [naam, setNaam] = useState(wg.naam);
  // Het dossier in één toestand: dezelfde velden en volgorde als de samenvatting (`DOSSIER_VELDEN`).
  const [dossier, setDossier] = useState<Record<DossierVeld, string>>(
    () => Object.fromEntries(DOSSIER_VELDEN.map(({ veld }) => [veld, wg[veld] ?? ""])) as Record<DossierVeld, string>);
  const [peildatum, setPeildatum] = useState(wg.peildatum ?? "");
  const [status, setStatus] = useState<WerkgebiedStatus>(wg.status);
  const [thema, setThema] = useState(wg.thema ?? "");
  const [voorstel, setVoorstel] = useState<ThemaVoorstel | null>(null);
  const [bezig, setBezig] = useState(false);
  // Spoor I6: Lex stelt een thema voor uit de rechtsgebieden van de bronnen, zonder model; faalt stil.
  useEffect(() => {
    let levend = true;
    void haalThemaVoorstel(wg.id).then((v) => levend && setVoorstel(v));
    return () => { levend = false; };
  }, [wg.id]);
  const voorgesteld = voorstel?.voorstel[0];

  async function bewaar(e: React.FormEvent) {
    e.preventDefault();
    if (!naam.trim() || bezig) return;
    setBezig(true);
    await onBewaar({ naam: naam.trim(), ...dossier, peildatum: peildatum || null, status, thema });
    setBezig(false);
  }

  return (
    <Dialog label="Gegevens van het werkgebied" variant="compact" onSluit={onSluit}>
      <form onSubmit={bewaar} className="space-y-4 overflow-y-auto p-5" data-gegevens-formulier>
        <h2 className="font-display text-base font-semibold text-lint">Gegevens bewerken</h2>
        <Field label="Naam" required>
          <Input value={naam} onChange={(e) => setNaam(e.target.value)} maxLength={200} required autoFocus />
        </Field>
        {DOSSIER_VELDEN.map(({ veld, label }) => (
          <Field key={veld} label={label} hint={DOSSIER_HINT[veld]}>
            <Textarea value={dossier[veld]} rows={2} maxLength={4000}
              onChange={(e) => setDossier((d) => ({ ...d, [veld]: e.target.value }))} />
          </Field>
        ))}
        <Field label="Thema" hint="TOOI-thema (tooitop): waar de analyse over gaat">
          <Select value={thema} onChange={(e) => setThema(e.target.value)}>
            <option value="">Nog geen thema</option>
            {themaGroepen().map(({ hoofd, subs }) => (
              <optgroup key={hoofd.uri} label={hoofd.label}>
                <option value={hoofd.uri}>{hoofd.label}</option>
                {subs.map((s) => <option key={s.uri} value={s.uri}>{s.label}</option>)}
              </optgroup>
            ))}
          </Select>
        </Field>
        {voorgesteld && voorgesteld.thema !== thema && (
          <p className="-mt-2 flex flex-wrap items-center gap-2 text-xs text-muted" data-thema-voorstel>
            <span>Voorstel van Lex: <span className="font-medium text-ink">{voorgesteld.label}</span>
              {voorstel?.rechtsgebieden.length ? ` (uit ${voorstel.rechtsgebieden.join(", ")})` : ""}</span>
            <Button type="button" size="xs" variant="secondary" onClick={() => setThema(voorgesteld.thema)}>Overnemen</Button>
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Gewenste peildatum" hint="de wettekst zelf komt uit de actuele graaf">
            <Input type="date" value={peildatum} onChange={(e) => setPeildatum(e.target.value)} />
          </Field>
          <Field label="Status">
            <Select value={status} onChange={(e) => setStatus(e.target.value as WerkgebiedStatus)}>
              {(Object.keys(STATUS_LABEL) as WerkgebiedStatus[]).map((s) => (
                <option key={s} value={s}>{STATUS_LABEL[s]}</option>
              ))}
            </Select>
          </Field>
        </div>
        <ButtonRow>
          <Button type="submit" disabled={!naam.trim() || bezig}>{bezig ? "Bezig…" : "Opslaan"}</Button>
          <Button type="button" variant="secondary" onClick={onSluit}>Annuleren</Button>
        </ButtonRow>
      </form>
    </Dialog>
  );
}
