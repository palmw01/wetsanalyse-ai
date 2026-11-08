"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { BewerkKnop, BewerkVoet, useBewerken } from "@/components/ui/Bewerkbaar";
import { Button, knopKlasse } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { IcoonBevestig } from "@/components/ui/IcoonBevestig";
import { Lijst, LijstRij, Regel, Regels, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { MeerMenu, MenuKnop, MenuVerwijder } from "@/components/ui/MeerMenu";
import { usePaneelKopVulling } from "@/components/ui/PaneelKop";
import { Melding } from "@/components/ui/Melding";
import { ObjectRij, ObjectRijen, SplitDetail } from "@/components/ui/Pagina";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { BegripBlok, type BegripWeergaveVorm } from "@/components/werkgebieden/BegripBlok";
import { BegripOpvolging } from "@/components/werkgebieden/BegripOpvolging";
import { BegripPassages } from "@/components/werkgebieden/BegripPassages";
import { BegripRelaties } from "@/components/werkgebieden/BegripRelaties";
import { DefinitieOnderbouwing } from "@/components/werkgebieden/DefinitieOnderbouwing";
import { KaartVoorstelKaart } from "@/components/werkgebieden/KaartVoorstel";
import { OordeelKeuze, VoorbeeldRijen } from "@/components/werkgebieden/Voorbeelden";
import { bevestigGebruik, foutTekst, maakGeneriek, neemOpvolgerOver, stopGebruik } from "@/lib/api";
import { conformZin, veldVanPad, type Conformiteit } from "@/lib/begripGraaf";
import { relatieZin } from "@/lib/begripRelaties";
import { definitieAard, regels, revisieZin, sorteerKoppelingen, uitRegels, volledigeInhoud } from "@/lib/begrippen";
import { BEGRIP_STATUS_LABEL } from "@/lib/begrippenOverzicht";
import { herkomstNaAanpassing } from "@/lib/begripVoorstellen";
import { geraaktPerKoppeling } from "@/lib/herbeoordeling";
import { definitieDoor, openPerVeld } from "@/lib/kaartVoorstel";
import type { Begrip, BegripInhoud as Inhoud, BegripRevisie, KaartVeld, Voorbeeld } from "@/lib/types";
import { useBegrip, type BegripContext, type BegripOpname, type BegripStand } from "@/lib/useBegrip";
import { VERWIJDER_UITLEG, verwijderLabel, verwijderdZin } from "@/lib/verwijderen";
import { generiekPad, projectPad } from "@/lib/werkgebiedPaden";

export const BEGRIP_STATUS_TOON = { geaccordeerd: "groen", concept: "neutraal", vervangen: "neutraal" } as const;

const tijd = (iso: string) =>
  new Date(iso).toLocaleString("nl-NL", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Eén begrip, overal dezelfde inhoud (spoor N, naar `BronnenBijDeelvraag`): op de pagina naast elkaar (`SplitDetail`),
 *  naast het gesprek onder elkaar. Links wat het begrip betekent en waarop het rust, rechts het oordeel en de samenhang.
 *  Je leest, en *Bewerken* bij een blok maakt van dat blok ter plekke een formulier; elke bewaring is een revisie. Een
 *  begrip is een analyse-uitkomst, geen wettelijke definitie: de betekenis zegt waar de definitie vandaan komt.
 *
 *  `stand` komt van `useBegrip`, zodat de kop eromheen dezelfde gegevens leest. Met een `opname` is alles alleen te
 *  lezen: geen knoppen, en geen oordeel of historie, want die horen bij de stand van nu. */
export function BegripInhoud({ stand, weergave, onOnbewaard, onNaarBegrip, onGewijzigd }: {
  stand: BegripStand;
  weergave: BegripWeergaveVorm;
  onOnbewaard: (onbewaard: boolean) => void;
  /** Naar een ander begrip: de opvolger van een vervangen begrip, of het begrip dat na combineren overblijft. */
  onNaarBegrip?: (begripId: string) => void;
  onGewijzigd?: () => void;
}) {
  const [open, setOpen] = useState({ betekenis: false, voorbeelden: false });
  const meldBetekenis = useCallback((o: boolean) => setOpen((s) => ({ ...s, betekenis: o })), []);
  const meldVoorbeelden = useCallback((o: boolean) => setOpen((s) => ({ ...s, voorbeelden: o })), []);
  const onbewaard = open.betekenis || open.voorbeelden;

  useEffect(() => { onOnbewaard(onbewaard); }, [onbewaard, onOnbewaard]);
  useEffect(() => () => onOnbewaard(false), [onOnbewaard]);
  // Herladen of het venster sluiten: dat kan de pagina niet zelf tegenhouden, de browser wel.
  useEffect(() => {
    if (!onbewaard) return;
    const waarschuw = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", waarschuw);
    return () => window.removeEventListener("beforeunload", waarschuw);
  }, [onbewaard]);

  const { begrip, alleenLezen } = stand;
  if (!begrip) return <BegripLaadStand stand={stand} />;

  const betekenis = <BetekenisBlok stand={stand} begrip={begrip} weergave={weergave} onbewaard={onbewaard} onOnbewaard={meldBetekenis} />;
  const voorbeelden = <VoorbeeldenBlok stand={stand} begrip={begrip} weergave={weergave} onbewaard={onbewaard} onOnbewaard={meldVoorbeelden} />;
  const melding = stand.melding && <Melding type={stand.melding.type} compact>{stand.melding.tekst}</Melding>;

  // De eigen pagina van een generiek begrip: de passages per werkgebied, en waar het gebruikt wordt.
  if (stand.generiek && !alleenLezen) {
    return (
      <div data-begrip-paneel={begrip.id} data-status={begrip.status} data-weergave="generiek" className="space-y-4">
        {melding}
        <SplitDetail hoofd={<>{betekenis}{voorbeelden}<PassagesPerWerkgebied begrip={begrip} /></>}
          zij={<>
            <BeoordelingBlok stand={stand} begrip={begrip} weergave={weergave} onbewaard={onbewaard} onNaarBegrip={onNaarBegrip} />
            <GebruiktIn begrip={begrip} />
            <RelatiesGeneriek stand={stand} />
            <Historie stand={stand} begrip={begrip} />
          </>} />
      </div>
    );
  }

  if (alleenLezen) {
    return (
      <div data-begrip-paneel={begrip.id} data-status={begrip.status} data-alleen-lezen className="space-y-5 text-sm text-ink">
        {betekenis}
        {voorbeelden}
        <PassagesLezen begrip={begrip} />
        <RelatiesLezen stand={stand} />
      </div>
    );
  }

  const passages = (
    <BegripPassages id={stand.id} begrip={begrip} primair={stand.lijst?.primair ?? {}} muteer={stand.muteer} weergave={weergave}
      geraakt={geraaktPerKoppeling(stand.herbeoordeling, stand.begripId)} />
  );
  const beoordeling = <BeoordelingBlok stand={stand} begrip={begrip} weergave={weergave} onbewaard={onbewaard} onNaarBegrip={onNaarBegrip} />;
  const relaties = (
    <BegripRelaties id={stand.id} begrip={begrip} andere={stand.lijst?.begrippen ?? []}
      onGewijzigd={() => { void stand.laad(); onGewijzigd?.(); }} onNaarBegrip={onNaarBegrip} weergave={weergave} />
  );
  const historie = <Historie stand={stand} begrip={begrip} />;
  const veranderd = <GeneriekVeranderdBlok stand={stand} begrip={begrip} onNaarBegrip={onNaarBegrip} />;

  if (weergave === "pagina") {
    return (
      <div data-begrip-paneel={begrip.id} data-status={begrip.status} data-weergave="pagina" className="space-y-4">
        {melding}
        <SplitDetail hoofd={<>{veranderd}{betekenis}{voorbeelden}{passages}</>} zij={<>{beoordeling}{relaties}{historie}</>} />
      </div>
    );
  }
  return (
    <div data-begrip-paneel={begrip.id} data-status={begrip.status} data-weergave="paneel" className="space-y-5 text-sm text-ink">
      {melding}
      {veranderd}
      {betekenis}
      {voorbeelden}
      {beoordeling}
      {passages}
      {relaties}
      {historie}
    </div>
  );
}

/** Laden, een fout met *Opnieuw proberen*, of de stand van een verwijderd begrip. */
function BegripLaadStand({ stand }: { stand: BegripStand }) {
  if (stand.verwijderd) return <Melding type="uitleg"><span data-verwijderd>{verwijderdZin(stand.verwijderd)}</span></Melding>;
  if (!stand.fout) return <SkeletonCard regels={4} />;
  return (
    <Melding type="fout" titel="Het begrip kon niet worden geladen.">
      {stand.fout}{" "}
      <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => void stand.laad()}>
        Opnieuw proberen
      </button>
    </Melding>
  );
}

/** De regels van het menu ⋯ van een begrip: de zware, zeldzame handelingen, met het venster dat ze openen. Een vervangen
 *  begrip heeft ze niet: verwijder dan de opvolger. Nieuwe betekenis en combineren openen een venster, want ze vragen een
 *  reden. Op de pagina staan ze in `BegripMenu`, naast het gesprek in het menu ⋯ van de paneelkop (`BegripCompact`). */
export function useBegripMenu({ stand, onNaarBegrip, onGestopt }: {
  stand: BegripStand;
  onNaarBegrip?: (begripId: string) => void;
  /** Dit werkgebied gebruikt het generieke begrip niet meer. */
  onGestopt?: () => void | Promise<void>;
}): { regels: ((sluit: () => void) => React.ReactNode) | null; venster: React.ReactNode } {
  const [opvolging, setOpvolging] = useState<"nieuw" | "combineren" | "generiek" | null>(null);
  const b = stand.begrip;
  if (!b || b.status === "vervangen" || stand.alleenLezen) return { regels: null, venster: null };
  const kandidaten = (stand.lijst?.begrippen ?? []).filter((x) => x.id !== b.id && x.status !== "vervangen" && x.kader !== "generiek");
  // Een generiek begrip in een werkgebied: dit werkgebied beslist alleen of het het gebruikt.
  if (b.kader === "generiek" && !stand.generiek) {
    return {
      regels: () => (
        <MenuVerwijder vraag="Stoppen?" ariaLabel="Dit begrip niet meer gebruiken"
          titel="Dit werkgebied gebruikt het begrip niet meer. Zijn passages hier gaan los; het begrip en de annotaties blijven."
          onBevestig={async () => { await stopGebruik(stand.id, b.id); await onGestopt?.(); }}>
          Niet meer gebruiken
        </MenuVerwijder>
      ),
      venster: null,
    };
  }
  return {
    regels: (sluit) => <>
      {!stand.generiek && b.status === "geaccordeerd" && (
        <MenuKnop onClick={() => { sluit(); void stand.muteer((r) => maakGeneriek(stand.id, b.id, r),
          { gelukt: "Dit begrip is nu generiek." }); }}>Generiek maken</MenuKnop>
      )}
      <MenuKnop onClick={() => { sluit(); setOpvolging("nieuw"); }}>Nieuwe betekenis</MenuKnop>
      {!stand.generiek && kandidaten.length > 0 && <MenuKnop onClick={() => { sluit(); setOpvolging("combineren"); }}>Combineren met…</MenuKnop>}
      {!stand.generiek && <MenuKnop onClick={() => { sluit(); setOpvolging("generiek"); }}>Combineren met generiek begrip…</MenuKnop>}
      <MenuVerwijder ariaLabel={verwijderLabel("begrip")} titel={VERWIJDER_UITLEG.begrip} onBevestig={async () => { await stand.verwijder(); sluit(); }} />
    </>,
    venster: opvolging && (
      <BegripOpvolging soort={opvolging} id={stand.id} begrip={b} kandidaten={kandidaten} onSluit={() => setOpvolging(null)}
        onKlaar={(naar) => { setOpvolging(null); void stand.laad(); onNaarBegrip?.(naar); }} />
    ),
  };
}

/** Het menu ⋯ van een begrip in de kop van zijn pagina (`KleineActies`). */
export function BegripMenu({ stand, maat = "sm", onNaarBegrip, onGestopt }: {
  stand: BegripStand;
  maat?: "xs" | "sm";
  onNaarBegrip?: (begripId: string) => void;
  onGestopt?: () => void | Promise<void>;
}) {
  const { regels, venster } = useBegripMenu({ stand, onNaarBegrip, onGestopt });
  if (!regels) return null;
  return (
    <>
      <MeerMenu label="Meer voor dit begrip" maat={maat}>{regels}</MeerMenu>
      {venster}
    </>
  );
}

/** Een begrip naast het gesprek: daar staat geen pagina omheen, dus de stand en de kop horen erbij. */
export function BegripCompact({ context, begripId, opname, onOnbewaard, onNaarBegrip }: {
  context: BegripContext;
  begripId: string;
  opname?: BegripOpname;
  onOnbewaard: (onbewaard: boolean) => void;
  onNaarBegrip?: (begripId: string) => void;
}) {
  const stand = useBegrip({ context, begripId, opname });
  const b = stand.begrip;
  const { regels, venster } = useBegripMenu({ stand, onNaarBegrip });
  // De stand en het menu ⋯ staan in de kop van het paneel (`PaneelKop`, 8 nov 2026), niet in een eigen rij.
  usePaneelKopVulling(b ? {
    status: <><StatusLabel toon={BEGRIP_STATUS_TOON[b.status]}>{BEGRIP_STATUS_LABEL[b.status]}</StatusLabel>
      <span className="text-xs text-muted">revisie {b.revisie}</span></>,
    menu: regels ?? undefined,
  } : null, b ? `${b.status}|${b.revisie}|${b.kader}|${stand.alleenLezen}|${regels ? 1 : 0}` : "");
  return (
    <div className="space-y-3">
      {venster}
      <BegripInhoud stand={stand} weergave="paneel" onOnbewaard={onOnbewaard} onNaarBegrip={onNaarBegrip} />
    </div>
  );
}

/** Een groep velden in de bewerkstand, met de NL-SBB-eigenschappen waar ze in de export op landen. */
function Groep({ titel, nlsbb, children }: { titel: string; nlsbb: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4" data-kaart-groep={titel}>
      <p className="flex flex-wrap items-baseline gap-x-2 text-xs font-medium text-muted">
        {titel}<span className="font-mono text-[0.65rem] font-normal text-faint">{nlsbb}</span>
      </p>
      {children}
    </div>
  );
}

/** De voorstellen van Lex bij één veld, met *Overnemen · Aanpassen · Afwijzen*. Overnemen staat uit zolang er iets
 *  onbewaard openstaat: er wordt niets stil overschreven. */
function VanLex({ stand, begrip, veld, onbewaard }: { stand: BegripStand; begrip: Begrip; veld: KaartVeld; onbewaard: boolean }) {
  if (stand.alleenLezen || begrip.status === "vervangen" || begrip.kader === "generiek") return null;
  const open = openPerVeld(stand.voorstellen)[veld];
  if (!open.length) return null;
  return (
    <div className="mt-2 space-y-2" aria-label={`Voorstellen van Lex bij ${veld}`}>
      {open.map((v) => (
        <KaartVoorstelKaart key={v.id} v={v} onbewaard={onbewaard} geaccordeerd={begrip.status === "geaccordeerd"}
          verouderd={stand.verouderd?.voorstelId === v.id ? stand.verouderd : null}
          onOvernemen={(extra) => stand.overnemen(v, extra)} onAfwijzen={(reden) => stand.afwijzen(v, reden)} />
      ))}
    </div>
  );
}

interface BlokProps {
  stand: BegripStand;
  begrip: Begrip;
  weergave: BegripWeergaveVorm;
  onbewaard: boolean;
  onOnbewaard: (onbewaard: boolean) => void;
}

/** Een generiek begrip bewerk je op zijn eigen pagina: vanuit een werkgebied zou je ongemerkt andere analyses wijzigen. */
const generiekHier = (stand: BegripStand, begrip: Begrip) => begrip.kader === "generiek" && !stand.generiek;

const magBewerken = (stand: BegripStand, begrip: Begrip) =>
  !stand.alleenLezen && begrip.status !== "vervangen" && !generiekHier(stand, begrip);

/** De weg naar de pagina van een generiek begrip. */
function NaarGeneriek({ begrip }: { begrip: Begrip }) {
  return <Link href={generiekPad(begrip.id)} className={`focus-ring ${knopKlasse("secondary", "xs")}`}>Bewerk generiek begrip</Link>;
}

/** Term en betekenis. De herkomst van de definitie kiest niemand: de api leidt haar af, en het label volgt wat er staat. */
function BetekenisBlok({ stand, begrip, weergave, onbewaard, onOnbewaard }: BlokProps) {
  const i = volledigeInhoud(begrip.inhoud);
  const begin = { naam: i.naam, termen: regels(i.alternatieve_termen), definitie: i.definitie, uitleg: i.uitleg, context: i.context };
  const b = useBewerken({
    begin, onOnbewaard,
    opslaan: ({ termen, ...rest }) => stand.muteer((r) =>
      stand.api.wijzig(r, { ...begrip.inhoud, ...rest, alternatieve_termen: uitRegels(termen).map((t) => t.trim()).filter(Boolean) } as Inhoud), { gelukt: "Opgeslagen." }),
  });
  const c = b.concept;
  const zet = (v: Partial<typeof begin>) => b.zet({ ...c, ...v });
  const vanLex = (veld: KaartVeld) => <VanLex stand={stand} begrip={begrip} veld={veld} onbewaard={onbewaard} />;
  const door = definitieDoor(begrip.inhoud);
  const termen = i.alternatieve_termen.filter((t) => t.trim());

  return (
    <BegripBlok weergave={weergave} titel="Betekenis" data-blok="betekenis"
      acties={generiekHier(stand, begrip) ? <NaarGeneriek begrip={begrip} />
        : magBewerken(stand, begrip) && !b.open && <BewerkKnop wat="Betekenis" onClick={b.start} />}>
      {b.open ? (
        <div className="space-y-5" role="group" aria-label="Betekenis bewerken" onKeyDown={b.toetsen(false)}>
          <Groep titel="Term" nlsbb="skos:prefLabel · skos:altLabel">
            <Field label="Voorkeursterm" hint="de naam van het begrip" required>
              <Input value={c.naam} onChange={(e) => zet({ naam: e.target.value })} maxLength={200} required autoFocus onKeyDown={b.toetsen(true)} />
            </Field>
            <Field label="Alternatieve termen" hint="één per regel">
              <AutoTextarea value={c.termen} onChange={(e) => zet({ termen: e.target.value })} rows={2} />
            </Field>
          </Groep>
          <Groep titel="Definitie, uitleg en toelichting" nlsbb="skos:definition · rdfs:comment · skos:scopeNote">
            <DefinitieAard inhoud={{
              definitie: c.definitie,
              definitie_herkomst: herkomstNaAanpassing(
                { tekst: i.definitie, herkomst: i.definitie_herkomst ?? null }, c.definitie),
            }} />
            <Field label="Definitie" hint="een gewijzigde definitie heet geformuleerd">
              <AutoTextarea value={c.definitie} onChange={(e) => zet({ definitie: e.target.value })} rows={3} maxLength={8000} />
            </Field>
            {/* Alleen bij de bewaarde tekst: een andere definitie rust niet meer op deze fragmenten (spoor M). */}
            {begrip.definitie_onderbouwing && c.definitie === i.definitie && (
              <DefinitieOnderbouwing onderbouwing={begrip.definitie_onderbouwing} werkgebiedId={stand.id} />
            )}
            {vanLex("definitie")}
            <Field label="Uitleg" hint="in eenvoudige taal: wat betekent het begrip">
              <AutoTextarea value={c.uitleg} onChange={(e) => zet({ uitleg: e.target.value })} rows={2} maxLength={8000} />
            </Field>
            {vanLex("uitleg")}
            <Field label="Toelichting" hint="de grenzen of het gebruik van het begrip">
              <AutoTextarea value={c.context} onChange={(e) => zet({ context: e.target.value })} rows={2} maxLength={4000} />
            </Field>
            {vanLex("context")}
          </Groep>
          <BewerkVoet onAnnuleer={b.annuleer} onOpslaan={() => void b.slaOp()} bezig={b.bezig} gewijzigd={b.gewijzigd && !!c.naam.trim()} fout={b.fout} />
        </div>
      ) : (
        <Regels data-begrip-lees>
          {termen.length > 0 && <Regel naam="Ook">{termen.join(", ")}</Regel>}
          <Regel naam="Definitie">
            {i.definitie ? (
              <div className="space-y-2">
                <p className="whitespace-pre-line">{i.definitie}</p>
                <DefinitieAard inhoud={i} />
                {door && <p className="text-xs text-muted">{door}</p>}
                {begrip.definitie_onderbouwing && (
                  <DefinitieOnderbouwing onderbouwing={begrip.definitie_onderbouwing} werkgebiedId={stand.id} />
                )}
              </div>
            ) : <span className="text-muted">Nog geen definitie.</span>}
            {vanLex("definitie")}
          </Regel>
          <Regel naam="Uitleg">
            {i.uitleg ? <span className="whitespace-pre-line">{i.uitleg}</span> : <span className="text-muted">Nog geen uitleg.</span>}
            {vanLex("uitleg")}
          </Regel>
          <Regel naam="Toelichting">
            {i.context ? <span className="whitespace-pre-line">{i.context}</span> : <span className="text-muted">Nog geen toelichting.</span>}
            {vanLex("context")}
          </Regel>
        </Regels>
      )}
    </BegripBlok>
  );
}

/** Brondefinitie of analysebegrip, zichtbaar bij de definitie: een geformuleerd analysebegrip is niet automatisch een
 *  wettelijke definitie (`definitieAard`). In de bewerkstand volgt hij wat er in het veld staat. */
export function DefinitieAard({ inhoud }: { inhoud: Parameters<typeof definitieAard>[0] }) {
  const aard = definitieAard(inhoud);
  const stijl = aard.soort === "brondefinitie" ? "border-aandacht-groen-rand bg-aandacht-groen-bg/50"
    : aard.soort === "analysebegrip" ? "border-lint/40 bg-lint/5" : "border-line bg-surface";
  return (
    <p data-definitie-aard={aard.soort} className={`rounded-md border-l-4 px-3 py-2 text-sm ${stijl}`}>
      <span className="font-medium text-ink">{aard.titel}.</span> <span className="text-muted">{aard.uitleg}</span>
    </p>
  );
}

/** De voorbeelden, met hun oordeel. Ook grensgevallen en tegenvoorbeelden: ze toetsen de afbakening. */
function VoorbeeldenBlok({ stand, begrip, weergave, onbewaard, onOnbewaard }: BlokProps) {
  const lijst = volledigeInhoud(begrip.inhoud).voorbeelden;
  const b = useBewerken<Voorbeeld[]>({
    begin: lijst, onOnbewaard,
    opslaan: (voorbeelden) => stand.muteer((r) => stand.api.wijzig(r, { ...begrip.inhoud, voorbeelden: voorbeelden.filter((v) => v.tekst.trim()) }), { gelukt: "Opgeslagen." }),
  });
  const zet = (i: number, v: Partial<Voorbeeld>) => b.zet(b.concept.map((x, j) => (j === i ? { ...x, ...v } : x)));

  return (
    <BegripBlok weergave={weergave} titel="Voorbeelden" telling={lijst.length} data-blok="voorbeelden"
      toelichting="Ook grensgevallen en tegenvoorbeelden: ze toetsen de afbakening."
      acties={magBewerken(stand, begrip) && !b.open && <BewerkKnop wat="Voorbeelden" onClick={b.start} />}>
      {b.open ? (
        <div className="space-y-3" role="group" aria-label="Voorbeelden bewerken" onKeyDown={b.toetsen(false)}>
          <Groep titel="Voorbeelden" nlsbb="skos:example">
            <fieldset className="space-y-3">
              <legend className="sr-only">Voorbeelden</legend>
              {b.concept.map((v, i) => (
                <div key={i} className="space-y-2 border-b border-line pb-3 last:border-b-0">
                  <AutoTextarea value={v.tekst} onChange={(e) => zet(i, { tekst: e.target.value })} rows={2} aria-label={`Voorbeeld ${i + 1}`} />
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <OordeelKeuze waarde={v.oordeel} onKies={(o) => zet(i, { oordeel: o })}
                      label={`Oordeel bij voorbeeld ${i + 1}`} naam={`oordeel-${begrip.id}-${i}`} />
                    <IcoonBevestig soort="verwijderen" label={`Verwijder voorbeeld ${i + 1}`}
                      onBevestig={() => b.zet(b.concept.filter((_, j) => j !== i))} />
                  </div>
                </div>
              ))}
              <Button type="button" size="xs" variant="secondary" onClick={() => b.zet([...b.concept, { tekst: "", oordeel: "wel" }])}>
                Voorbeeld toevoegen
              </Button>
            </fieldset>
          </Groep>
          <VanLex stand={stand} begrip={begrip} veld="voorbeelden" onbewaard={onbewaard} />
          <BewerkVoet onAnnuleer={b.annuleer} onOpslaan={() => void b.slaOp()} bezig={b.bezig} gewijzigd={b.gewijzigd} fout={b.fout} />
        </div>
      ) : (
        <>
          {lijst.length ? <VoorbeeldRijen voorbeelden={lijst} /> : <p className="text-sm text-muted">Nog geen voorbeelden.</p>}
          <VanLex stand={stand} begrip={begrip} veld="voorbeelden" onbewaard={onbewaard} />
        </>
      )}
    </BegripBlok>
  );
}

/** Accorderen en heropenen. De poort rekent de server; hier staan zijn redenen letterlijk. */
function BeoordelingBlok({ stand, begrip, weergave, onbewaard, onNaarBegrip }: Omit<BlokProps, "onOnbewaard"> & {
  onNaarBegrip?: (begripId: string) => void;
}) {
  const [bezig, setBezig] = useState(false);
  const [reden, setReden] = useState("");
  async function doe(actie: (r: number) => Promise<Begrip>, gelukt: string) {
    setBezig(true);
    await stand.muteer(actie, { gelukt });
    setBezig(false);
    setReden("");
  }
  const { mag, redenen } = begrip.accorderen;
  return (
    <BegripBlok weergave={weergave} titel="Beoordeling" data-blok="beoordeling"
      acties={<StatusLabel toon={BEGRIP_STATUS_TOON[begrip.status]}>{BEGRIP_STATUS_LABEL[begrip.status]}</StatusLabel>}>
      <div className="space-y-2 text-sm">
        {generiekHier(stand, begrip) && begrip.status !== "vervangen" ? (
          <p className="text-xs text-muted">Een generiek begrip beoordeel je op zijn eigen pagina; de passages hier beoordeel je in dit werkgebied.</p>
        ) : begrip.status === "vervangen" ? (
          <p className="text-xs text-muted">
            {begrip.vervangen_door && <>
              Vervangen door{" "}
              <button type="button" className="focus-ring rounded font-medium text-lint underline"
                onClick={() => onNaarBegrip?.(begrip.vervangen_door!.begrip_id)}>{begrip.vervangen_door.naam}</button>
              {begrip.vervangen_door.reden && <> – {begrip.vervangen_door.reden}</>}.{" "}
            </>}
            Dit begrip is alleen nog te lezen.
          </p>
        ) : begrip.status === "geaccordeerd" ? (
          <>
            <p className="text-ink">
              Geaccordeerd door {begrip.geaccordeerd_door}
              {begrip.geaccordeerd_op && ` op ${tijd(begrip.geaccordeerd_op)}`}.
            </p>
            {begrip.aandachtspunten.map((a) => <p key={a} className="text-xs text-aandacht-geel-tekst">{a}</p>)}
            <NlSbbStand stand={stand} begrip={begrip} />
            <Button size="sm" variant="secondary" className="w-full sm:w-auto" disabled={bezig}
              onClick={() => void doe((r) => stand.api.heropen(r), "Heropend.")}>
              Heropenen
            </Button>
          </>
        ) : (
          <>
            {onbewaard ? (
              <p className="text-xs text-muted">Sla eerst je wijzigingen op; de poort kijkt naar wat bewaard is.</p>
            ) : !mag ? (
              <div>
                <p className="text-xs font-medium text-ink">Nog nodig om te accorderen:</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-ink" aria-label="Nog nodig om te accorderen">
                  {redenen.map((r) => <li key={r}>{r}</li>)}
                </ul>
              </div>
            ) : (
              <p className="text-xs text-ink">Alles is er: naam, definitie, toelichting en beoordeelde, actuele passages.</p>
            )}
            <NlSbbStand stand={stand} begrip={begrip} />
            {mag && !onbewaard && (
              <Field label="Reden van accorderen" hint="waarom dit begrip klopt; het komt in de historie" required>
                <AutoTextarea value={reden} onChange={(e) => setReden(e.target.value)} rows={2} maxLength={2000} />
              </Field>
            )}
            <Button size="sm" className="w-full sm:w-auto" disabled={!mag || onbewaard || bezig || !reden.trim()}
              onClick={() => void doe((r) => stand.api.accordeer(r, reden.trim()), "Geaccordeerd.")}>
              Accorderen
            </Button>
          </>
        )}
      </div>
    </BegripBlok>
  );
}

/** Is het begrip NL-SBB-conform (fase F3)? Diagnostisch: het houdt accorderen niet tegen, en een conforme kaart is
 *  daarmee nog niet juridisch juist. Opnieuw gevraagd bij elke revisie; faalt stil. */
function NlSbbStand({ stand: { api }, begrip }: { stand: BegripStand; begrip: Begrip }) {
  const [c, setC] = useState<Conformiteit | null>(null);
  useEffect(() => {
    let levend = true;
    api.conformiteit().then((x) => levend && setC(x)).catch(() => levend && setC(null));
    return () => { levend = false; };
  }, [api, begrip.id, begrip.revisie]);
  const stand = c?.begrippen[begrip.id];
  const zin = c ? conformZin(stand, c.nl_sbb_versie) : null;
  if (!zin || !stand) return null;
  const meldingen = stand.meldingen;
  return (
    <div className="text-xs" data-testid="nl-sbb-stand">
      <p className={stand.conform ? "text-muted" : "text-aandacht-geel-tekst"}>{zin}</p>
      {meldingen.length > 0 && (
        <details className="mt-1">
          <summary className="focus-ring cursor-pointer text-[11px] text-muted">Meldingen ({meldingen.length})</summary>
          <ul className="mt-1 space-y-0.5 pl-4 text-[11px] text-muted">
            {meldingen.map((m, i) => (
              <li key={i}>
                {m.laag === "nl_sbb" ? "NL-SBB" : "Platform"} · {m.ernst} · {veldVanPad(m.pad) || "begrip"}{m.melding ? `: ${m.melding}` : ""}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-[10px] text-faint">Een diagnose, geen blokkade: conform zegt iets over de vorm, niet over de juridische juistheid.</p>
        </details>
      )}
    </div>
  );
}

/** Per revisie wie wat deed, met de oude inhoud bewaard in de api. Pas geladen bij openklappen, en opnieuw bij een
 *  nieuwe revisie. Zelfde vorm als de historie van een annotatie (`RevisieHistorie`). */
function Historie({ stand: { api }, begrip }: { stand: BegripStand; begrip: Begrip }) {
  const [open, setOpen] = useState(false);
  const [revisies, setRevisies] = useState<BegripRevisie[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let levend = true;
    api.revisies()
      .then((r) => levend && setRevisies(r))
      .catch((e) => levend && setFout(foutTekst(e, "De historie kon niet worden geladen.")));
    return () => { levend = false; };
  }, [open, api, begrip.id, begrip.revisie]);

  return (
    <details className="group rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary className="focus-ring flex cursor-pointer list-none items-center gap-1.5 rounded text-xs font-medium text-muted">
        <ChevronOmlaag className="-rotate-90 transition-transform group-open:rotate-0" />
        Historie <span className="font-normal text-faint">({begrip.revisie} {begrip.revisie === 1 ? "revisie" : "revisies"})</span>
      </summary>
      {fout ? (
        <p className="mt-2 text-xs text-aandacht-rood-tekst">{fout}</p>
      ) : !revisies ? (
        <p className="mt-2 text-xs text-muted">Laden…</p>
      ) : (
        <ol className="mt-2 space-y-1.5" aria-label="Historie van het begrip">
          {revisies.map((r) => (
            <li key={r.revisie} className="flex flex-col gap-0.5 border-b border-line pb-1.5 last:border-b-0">
              <span className="text-xs text-muted">{tijd(r.tijdstip)}</span>
              <span className="text-ink">
                {revisieZin(r)} <span className="text-xs text-muted">· {r.actor} · revisie {r.revisie}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

/** Een generiek begrip veranderde sinds dit werkgebied het zag: toen naast nu, en wat je ermee doet. De oude stand blijft
 *  gelden tot je hem bevestigt of de opvolger overneemt. */
function GeneriekVeranderdBlok({ stand, begrip, onNaarBegrip }: {
  stand: BegripStand;
  begrip: Begrip;
  onNaarBegrip?: (begripId: string) => void;
}) {
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const v = stand.herbeoordeling?.generiek?.find((x) => x.begrip_id === begrip.id);
  if (!v) return null;
  async function doe(actie: () => Promise<Begrip>, na: (b: Begrip) => void) {
    setBezig(true);
    setFout(null);
    try { na(await actie()); } catch (e) { setFout(foutTekst(e)); } finally { setBezig(false); }
  }
  return (
    <section aria-label="Generiek begrip veranderd" data-generiek-veranderd className="space-y-2 rounded-kaart border border-aandacht-geel-rand bg-aandacht-geel-bg/40 p-4 text-sm">
      <p className="font-medium text-aandacht-geel-tekst">
        {v.opvolger ? `Dit generieke begrip is vervangen door ${v.opvolger.naam}` : "Dit generieke begrip veranderde sinds dit werkgebied het zag"}
      </p>
      {v.opvolger?.reden && <p className="text-xs text-ink">{v.opvolger.reden}</p>}
      {v.velden.length > 0 && (
        <Regels>
          {v.velden.map((veld) => (
            <Regel key={veld} naam={`${veld[0].toUpperCase()}${veld.slice(1).replaceAll("_", " ")}`}>
              <span className="block text-xs text-muted">Toen: {tekstVan(v.toen[veld])}</span>
              <span className="block text-xs">Nu: {tekstVan(v.nu[veld])}</span>
            </Regel>
          ))}
        </Regels>
      )}
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {v.opvolger ? (
        <Button size="sm" disabled={bezig} className="w-full sm:w-auto"
          onClick={() => void doe(() => neemOpvolgerOver(stand.id, begrip.id), (b) => onNaarBegrip?.(b.id))}>Opvolger overnemen</Button>
      ) : (
        <Button size="sm" variant="secondary" disabled={bezig} className="w-full sm:w-auto"
          onClick={() => void doe(() => bevestigGebruik(stand.id, begrip.id), () => stand.herbeoordeel())}>Klopt nog voor dit werkgebied</Button>
      )}
    </section>
  );
}

const tekstVan = (x: unknown) => (typeof x === "string" ? x : Array.isArray(x) ? `${x.length} regels` : "") || "(leeg)";

/** De passages van een generiek begrip, per werkgebied. Alleen te lezen: passages beheert elk werkgebied zelf. */
function PassagesPerWerkgebied({ begrip }: { begrip: Begrip }) {
  const passages = sorteerKoppelingen(begrip.koppelingen);
  const namen = new Map((begrip.gebruik ?? []).map((g) => [g.werkgebied_id, g.naam]));
  const per = [...new Set(passages.map((k) => k.werkgebied_id ?? ""))];
  return (
    <BegripBlok weergave="pagina" titel="Passages" telling={passages.length} data-blok="passages"
      toelichting="Per werkgebied; elk werkgebied beheert zijn eigen passages.">
      {passages.length === 0 ? <p className="text-sm text-muted">Nog geen passages.</p> : per.map((wid) => (
        <div key={wid} data-passages-werkgebied={wid}>
          <h3 className="text-xs font-medium text-muted">{namen.get(wid) ?? "Werkgebied"}</h3>
          <Lijst label={`Passages in ${namen.get(wid) ?? "dit werkgebied"}`}>
            {passages.filter((k) => (k.werkgebied_id ?? "") === wid).map((k) => (
              <LijstRij key={k.id} titel={`“${k.bewijs.tekst}”`} meta={k.bewijs.vindplaats} />
            ))}
          </Lijst>
        </div>
      ))}
    </BegripBlok>
  );
}

function GebruiktIn({ begrip }: { begrip: Begrip }) {
  const gebruik = begrip.gebruik ?? [];
  return (
    <BegripBlok weergave="pagina" titel="Gebruikt in" telling={gebruik.length} data-blok="gebruik">
      <ObjectRijen label="Werkgebieden die dit begrip gebruiken" leeg="Nog in geen enkel werkgebied.">
        {gebruik.map((g) => <ObjectRij key={g.werkgebied_id} href={projectPad(g.werkgebied_id)} titel={g.naam}
          sub={g.passages === 1 ? "1 passage" : `${g.passages} passages`} />)}
      </ObjectRijen>
    </BegripBlok>
  );
}

function RelatiesGeneriek({ stand }: { stand: BegripStand }) {
  const r = stand.relatiesGeneriek;
  return (
    <BegripBlok weergave="pagina" titel="Relaties" telling={r.length} data-blok="relaties">
      {r.length ? (
        <Lijst label="Relaties">
          {r.map((x) => <LijstRij key={x.id} titel={relatieZin(x.type, x.van_naam, x.naar_naam).join(" ")} />)}
        </Lijst>
      ) : <p className="text-sm text-muted">Nog geen relaties met andere begrippen.</p>}
    </BegripBlok>
  );
}

/** De passages van een oude versie: alleen te lezen. */
function PassagesLezen({ begrip }: { begrip: Begrip }) {
  const passages = sorteerKoppelingen(begrip.koppelingen ?? []);
  if (!passages.length) return null;
  return (
    <Sectie titel="Passages" telling={passages.length} niveau={3}>
      <Lijst label="Passages">
        {passages.map((k) => <LijstRij key={k.id} titel={`“${k.bewijs.tekst}”`} meta={k.bewijs.vindplaats} />)}
      </Lijst>
    </Sectie>
  );
}

/** De relaties van een oude versie: alleen te lezen. */
function RelatiesLezen({ stand }: { stand: BegripStand }) {
  const r = stand.relatiesOpname;
  const vast = (r?.relaties ?? []).filter((x) => x.beoordeling === "akkoord");
  if (!vast.length) return null;
  return (
    <Sectie titel="Relaties" telling={vast.length} niveau={3}>
      <Lijst label="Relaties">
        {vast.map((x) => <LijstRij key={x.id} titel={relatieZin(x.type, x.van_naam, x.naar_naam).join(" ")} />)}
      </Lijst>
    </Sectie>
  );
}
