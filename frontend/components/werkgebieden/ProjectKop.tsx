"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Button, knopKlasse } from "@/components/ui/Button";
import { BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Field, Input, Select } from "@/components/ui/Field";
import { Meer } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { MENU_PANEEL } from "@/components/ui/Menu";
import { PaginaKop, Stip, TabLinks, type Kruimel } from "@/components/ui/Pagina";
import { Popover } from "@/components/ui/Popover";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { haalThemaVoorstel } from "@/lib/api";
import { bewerkToets, isGewijzigd } from "@/lib/bewerken";
import { themaGroepen } from "@/lib/tooiThemas";
import type { ThemaVoorstel, Werkgebied, WerkgebiedStatus } from "@/lib/types";
import { DOSSIER_VELDEN, STATUS_LABEL, datumNl, type DossierVeld } from "@/lib/werkgebied";
import { ARTEFACT_SOORTEN, PROJECT_TABS, artefactPad, projectPad, type ProjectTab } from "@/lib/werkgebiedPaden";

/** De kop van een werkgebied boven de vijf tabs (mock-up v4, `projectHead` + `tabbar`): de naam, één zin,
 *  status en wanneer gewijzigd, en twee knoppen – *Gegevens bewerken* en *Nieuw gesprek*. Verwijderen staat in
 *  het menu ernaast; de historie is een eigen tab. */
export function ProjectKop({ tab }: { tab: ProjectTab }) {
  const { wg, verwijder, stand } = useWerkgebied();
  const tellers: Partial<Record<ProjectTab, number>> = {
    gesprekken: stand.gesprekken?.length, bronnen: wg.bronnen.length, artefacten: ARTEFACT_SOORTEN.length,
  };
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
            {wg.peildatum && <><Stip /><span>Peildatum {datumNl(wg.peildatum)}</span></>}
            <Stip />
            <span>Aangemaakt door {wg.aangemaakt_door}</span>
          </>
        }
        acties={
          <>
            {/* Bewerken gebeurt ter plekke op de kaart van het dossier (4 nov 2026), niet in een venster. */}
            <Link href={`${artefactPad(wg.id, "dossier")}?bewerk=1`} className={knopKlasse("secondary", "sm")}>Gegevens bewerken</Link>
            <Link href={`/workbench?werkgebied=${encodeURIComponent(wg.id)}`}
              className={knopKlasse("primary", "sm")}>
              Nieuw gesprek
            </Link>
            <Popover ariaLabel="Meer voor dit werkgebied" className={`w-56 ${MENU_PANEEL}`}
              trigger={(open, toggle) => (
                <button type="button" onClick={toggle} aria-expanded={open} aria-label="Meer voor dit werkgebied"
                  className="focus-ring inline-flex min-h-[32px] min-w-[32px] items-center justify-center self-start rounded-full border border-line text-muted hover:bg-surface hover:text-lint coarse:min-h-[44px] coarse:min-w-[44px] sm:self-auto">
                  <Meer />
                </button>
              )}>
              <div className="px-2.5 py-1.5">
                <VerwijderKnop soort="werkgebied" onBevestig={verwijder} />
              </div>
            </Popover>
          </>
        }
      />
      <TabLinks label="Werkgebied" actief={tab}
        tabs={PROJECT_TABS.map((t) => ({ key: t.key, label: t.label, href: projectPad(wg.id, t.key), telling: tellers[t.key] }))} />
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
  gebeurtenis: "de handeling in de term van de wet, zoals kwijtschelding of verrekening",
};

/** Naam, dossier, thema, peildatum en status van het werkgebied bewerken – ter plekke, op de kaart van het dossier
 *  (4 nov 2026: één manier van bewerken, geen venster; `components/ui/Bewerkbaar`). Escape annuleert, Ctrl/⌘+Enter
 *  slaat op; wat er onbewaard openstaat, meldt het formulier aan de bewaker van het werkgebied (`onOnbewaard`). */
export function GegevensFormulier({ wg, deel = "dossier", onBewaar, onSluit, onOnbewaard }: {
  wg: Werkgebied;
  /** Welk blok: `dossier` (de kaart *Analyseopdracht*: naam, dossiervelden, thema) of `versie` (de kaart *Versie*:
   *  peildatum en status). Je bewerkt een gegeven op de plek waar het staat; het formulier stuurt alleen dat blok. */
  deel?: "dossier" | "versie";
  onBewaar: (w: Partial<{ naam: string; peildatum: string | null; status: WerkgebiedStatus; thema: string } & Record<DossierVeld, string>>) => Promise<void>;
  onSluit: () => void;
  onOnbewaard?: (onbewaard: boolean) => void;
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
  const versie = deel === "versie";
  const begin = useMemo(() => versie ? { peildatum: wg.peildatum ?? "", status: wg.status }
    : { naam: wg.naam, thema: wg.thema ?? "", ...Object.fromEntries(DOSSIER_VELDEN.map(({ veld }) => [veld, wg[veld] ?? ""])) },
  [wg, versie]);
  const gewijzigd = isGewijzigd(begin, versie ? { peildatum, status } : { naam, thema, ...dossier });
  useEffect(() => { onOnbewaard?.(gewijzigd); }, [gewijzigd, onOnbewaard]);
  useEffect(() => () => onOnbewaard?.(false), [onOnbewaard]);
  const formRef = useRef<HTMLFormElement>(null);

  async function bewaar(e: React.FormEvent) {
    e.preventDefault();
    if ((!versie && !naam.trim()) || bezig) return;
    setBezig(true);
    await onBewaar(versie ? { peildatum: peildatum || null, status } : { naam: naam.trim(), ...dossier, thema });
    setBezig(false);
  }

  return (
      <form ref={formRef} onSubmit={bewaar} className="space-y-4" data-gegevens-formulier aria-label="Gegevens van het werkgebied bewerken"
        onKeyDown={(e) => {
          const wat = bewerkToets({ key: e.key, ctrlKey: e.ctrlKey, metaKey: e.metaKey, isComposing: e.nativeEvent.isComposing }, false);
          if (!wat) return;
          e.preventDefault(); e.stopPropagation();
          if (wat === "annuleren") onSluit(); else formRef.current?.requestSubmit();
        }}>
        {!versie && <>
        <Field label="Naam" required>
          <Input value={naam} onChange={(e) => setNaam(e.target.value)} maxLength={200} required autoFocus />
        </Field>
        {/* De tekstvakken groeien mee met hun inhoud: alles wat er staat is te zien, zonder te slepen. De gebeurtenis
            is één term ("kwijtschelding") en krijgt één regel. */}
        {DOSSIER_VELDEN.map(({ veld, label }) => (
          <Field key={veld} label={label} hint={DOSSIER_HINT[veld]}>
            {veld === "gebeurtenis"
              ? <Input value={dossier[veld]} maxLength={200}
                  onChange={(e) => setDossier((d) => ({ ...d, [veld]: e.target.value }))} />
              : <AutoTextarea value={dossier[veld]} rows={2} maxLength={4000}
                  onChange={(e) => setDossier((d) => ({ ...d, [veld]: e.target.value }))} />}
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
        </>}
        {versie && <>
        {/* Peildatum en status onder elkaar: ze staan op de smalle kaart *Versie*; de uitleg van de peildatum staat eronder. */}
        <div className="space-y-4" data-peildatum-status>
          <Field label="Peildatum">
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
        <p className="-mt-2 text-xs text-faint">
          De peildatum is standaard de aanmaakdatum; leeg zet hem daarop terug. De wettekst komt uit de actuele graaf:
          geldt die pas na de peildatum, dan staat dat bij de bronnen.
        </p>
        </>}
        <BewerkVoet submit onAnnuleer={onSluit} bezig={bezig} gewijzigd={gewijzigd && (versie || !!naam.trim())} />
      </form>
  );
}
