"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tabs } from "@/components/ui/Tabs";
import { BronnenTab } from "@/components/werkgebieden/BronnenTab";
import { BegrippenTab } from "@/components/werkgebieden/BegrippenTab";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { ElementenTab } from "@/components/werkgebieden/ElementenTab";
import { HistorieTab } from "@/components/werkgebieden/HistorieTab";
import { SamenhangTab } from "@/components/werkgebieden/SamenhangTab";
import { WerkgebiedSamenvatting } from "@/components/werkgebieden/WerkgebiedSamenvatting";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { archiveerWerkgebied, foutTekst, haalWerkgebied, isApiError, wijzigWerkgebied } from "@/lib/api";
import type { BegripWeergave } from "@/lib/begrippen";
import type { Werkgebied, WerkgebiedStatus } from "@/lib/types";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import {
  DOSSIER_VELDEN, STATUS_LABEL, TABS, isRevisieConflict, type DossierVeld, type WerkgebiedTab,
} from "@/lib/werkgebied";

export interface MutatieOpties {
  /** De bevestiging na afloop; een functie als die van de uitkomst afhangt. */
  gelukt?: string | (() => string);
  /** Een fout die over de invoer zelf gaat en bij het formulier hoort: geef `true` als hij daar is
   *  afgehandeld. Een revisieconflict komt hier niet langs. */
  opFout?: (e: unknown) => boolean;
}
export type Mutatie = (actie: (revisie: number) => Promise<Werkgebied>, opties?: MutatieOpties) => Promise<boolean>;

/** Eén werkgebied: de gegevens, en de tabs Bronnen · Elementen · Begrippen · Samenhang · Historie.
 *
 *  Werkgebieden zijn gedeeld, dus elke mutatie stuurt de revisie in beeld mee. Wijzigde iemand
 *  anders het werkgebied intussen (412), dan laadt de pagina de nieuwste stand en zegt dat – de
 *  handeling wordt niet stil opnieuw uitgevoerd, want die kan op de nieuwe stand iets anders
 *  betekenen. */
export function WerkgebiedClient({ id, beginTab, beginBegrip, beginWeergave = "lezen" }: {
  id: string;
  beginTab: WerkgebiedTab;
  beginBegrip?: string;
  beginWeergave?: BegripWeergave;
}) {
  const router = useRouter();
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [nietGevonden, setNietGevonden] = useState(false);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  const [tab, setTab] = useState<WerkgebiedTab>(beginTab);
  // Het gekozen begrip op de tab Begrippen; staat ook in de URL.
  const [begrip, setBegrip] = useState<string | undefined>(beginBegrip);
  // Lezen of de kaart (F3e); blijft staan bij een wissel van begrip, en staat ook in de URL.
  const [weergave, setWeergave] = useState<BegripWeergave>(beginWeergave);
  // De begripskaart draagt niet-bewaarde wijzigingen: een tabwissel zou ze stil weggooien (de tabs
  // renderen lazy), dus die wacht eerst op bevestiging.
  const [onbewaard, setOnbewaard] = useState(false);
  const [wachtendeTab, setWachtendeTab] = useState<WerkgebiedTab | null>(null);
  // Hetzelfde voor een navigatie weg van de pagina: een link (de sidebar, "Alle werkgebieden") of een
  // gesprek openen. De vraag staat bovenaan; wie onderaan de kaart klikte, moet hem ook zien.
  const bewaker = useOnbewaardBewaker(onbewaard);
  const vraagRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (bewaker.wachtend) vraagRef.current?.scrollIntoView({ block: "nearest" });
  }, [bewaker.wachtend]);
  const [bewerken, setBewerken] = useState(false);

  const laad = useCallback(async () => {
    try {
      setWg(await haalWerkgebied(id));
    } catch (e) {
      if (isApiError(e) && e.status === 404) setNietGevonden(true);
      else setFout(foutTekst(e, "Het werkgebied kon niet worden geladen."));
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  const muteer: Mutatie = useCallback(
    async (actie, { gelukt, opFout } = {}) => {
      if (!wg) return false;
      setFout(null);
      setMelding(null);
      try {
        setWg(await actie(wg.revisie));
        if (gelukt) setMelding({ type: "bevestiging", tekst: typeof gelukt === "function" ? gelukt() : gelukt });
        return true;
      } catch (e) {
        if (isRevisieConflict(e)) {
          await laad();
          setMelding({
            type: "waarschuwing",
            tekst: "Iemand anders wijzigde dit werkgebied net. De nieuwste stand staat nu in beeld; kijk of je wijziging nog nodig is.",
          });
        } else if (!opFout?.(e)) {
          setFout(foutTekst(e));
        }
        return false;
      }
    },
    [wg, laad],
  );

  function zetUrl(t: WerkgebiedTab, b: string | undefined, w: BegripWeergave = weergave) {
    // `replace`: een tab- of begripwissel is geen stap in de geschiedenis.
    const qs = new URLSearchParams();
    if (t !== "bronnen") qs.set("tab", t);
    if (t === "begrippen" && b) qs.set("begrip", b);
    if (t === "begrippen" && b && w === "kaart") qs.set("weergave", w);
    const pad = `/werkgebieden/${encodeURIComponent(id)}`;
    router.replace(qs.size ? `${pad}?${qs}` : pad, { scroll: false });
  }

  function kiesTab(nieuw: string) {
    if (onbewaard && tab === "begrippen" && nieuw !== "begrippen") {
      setWachtendeTab(nieuw as WerkgebiedTab);
      return;
    }
    setWachtendeTab(null);
    setTab(nieuw as WerkgebiedTab);
    setMelding(null);
    zetUrl(nieuw as WerkgebiedTab, begrip);
  }

  /** Naar de tab Begrippen, op dit begrip (of de lijst) – ook vanuit de tab Elementen. Met `w` ook in die
   *  weergave (herbeoordelen gebeurt op de kaart). */
  function kiesBegrip(b: string | undefined, w?: BegripWeergave) {
    setBegrip(b);
    if (w) setWeergave(w);
    setTab("begrippen");
    setMelding(null);
    zetUrl("begrippen", b, w ?? weergave);
  }

  async function archiveer() {
    if (await muteer((r) => archiveerWerkgebied(id, r))) router.push("/werkgebieden");
  }

  const terug = (
    <Link
      href="/werkgebieden"
      className="focus-ring mb-2 inline-flex items-center gap-1 rounded text-xs text-muted transition-colors hover:text-ink"
    >
      <ChevronOmlaag className="rotate-90" /> Alle werkgebieden
    </Link>
  );

  if (nietGevonden)
    return (
      <WerkgebiedSchil titel="Werkgebied" onFout={setFout}>
        {terug}
        <Melding type="uitleg">Dit werkgebied bestaat niet (meer), of het is gearchiveerd.</Melding>
      </WerkgebiedSchil>
    );

  return (
    <WerkgebiedSchil titel={wg?.naam ?? "Werkgebied"} onFout={setFout} breed={tab === "begrippen" || tab === "samenhang"}
      bewaak={bewaker.bewaak}>
      {terug}
      {wg === null ? (
        fout ? (
          <Melding type="fout">{fout}</Melding>
        ) : (
          <div className="space-y-3">
            <Skeleton className="h-6 w-64" />
            <Skeleton className="h-3 w-96 max-w-full" />
          </div>
        )
      ) : (
        <>
          {bewerken ? (
            <GegevensFormulier
              wg={wg}
              onAnnuleer={() => setBewerken(false)}
              onBewaar={async (w) => {
                if (await muteer((r) => wijzigWerkgebied(id, { ...w, verwachte_revisie: r }), { gelukt: "Opgeslagen." })) setBewerken(false);
              }}
            />
          ) : (
            <header className="mb-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h1 className="font-display text-lg font-semibold text-lint">{wg.naam}</h1>
                  <p className="mt-0.5 text-xs text-muted">
                    {STATUS_LABEL[wg.status]}
                    {wg.peildatum && ` · peildatum ${wg.peildatum}`} · aangemaakt door {wg.aangemaakt_door}
                  </p>
                </div>
                <ButtonRow>
                  <VraagLexKnop onderwerp={{ soort: "werkgebied", werkgebied_id: wg.id, id: "", label: wg.naam }}
                    className="justify-center" />
                  <Button variant="secondary" size="sm" onClick={() => setBewerken(true)}>
                    Gegevens bewerken
                  </Button>
                  <BevestigKnop
                    bevestigTekst="Archiveren?"
                    onBevestig={archiveer}
                    className="focus-ring inline-flex min-h-[32px] items-center justify-center rounded-button border border-line px-3 py-1.5 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink coarse:min-h-[44px]"
                    bevestigClassName="border-fout/40 text-fout"
                  >
                    Archiveren
                  </BevestigKnop>
                </ButtonRow>
              </div>
              <WerkgebiedSamenvatting wg={wg} vraagLex className="mt-3" />
            </header>
          )}

          {fout && (
            <Melding type="fout" className="mb-4">
              {fout}
            </Melding>
          )}
          {melding && (
            <Melding type={melding.type} compact className="mb-4">
              {melding.tekst}
            </Melding>
          )}
          {bewaker.wachtend && (
            <div ref={vraagRef}>
              <OnbewaardMelding
                className="mb-4"
                handeling="verlaten"
                onBlijf={bewaker.blijf}
                onToch={() => {
                  setOnbewaard(false);
                  bewaker.toch();
                }}
              />
            </div>
          )}
          {wachtendeTab && (
            <OnbewaardMelding
              className="mb-4"
              onBlijf={() => setWachtendeTab(null)}
              onToch={() => {
                const naar = wachtendeTab;
                setOnbewaard(false);
                setWachtendeTab(null);
                setTab(naar);
                setMelding(null);
                zetUrl(naar, begrip);
              }}
            />
          )}

          {/* `lazy`: de inventaris en de historie halen bij mount data op, en de inventaris vraagt
              per regeling de bronboom uit de graaf. Alleen de tab in beeld laadt. */}
          <Tabs
            label="Werkgebied"
            lazy
            active={tab}
            onChange={kiesTab}
            tabs={TABS.map((t) => ({
              key: t.key,
              label: t.key === "bronnen" ? `${t.label} (${wg.bronnen.length})` : t.label,
              content:
                t.key === "bronnen" ? (
                  <BronnenTab wg={wg} muteer={muteer} onHerlaad={laad} />
                ) : t.key === "elementen" ? (
                  // Opnieuw ophalen bij elke nieuwe revisie: een andere selectie is een andere inventaris.
                  <ElementenTab key={wg.revisie} id={id} onNaarBegrip={kiesBegrip} />
                ) : t.key === "begrippen" ? (
                  <BegrippenTab id={id} gekozen={begrip} onKies={kiesBegrip} onbewaard={onbewaard} onOnbewaard={setOnbewaard}
                    weergave={weergave} onWeergave={(w) => { setWeergave(w); zetUrl("begrippen", begrip, w); }} />
                ) : t.key === "samenhang" ? (
                  <SamenhangTab wg={wg} muteer={muteer} onKiesBegrip={(b) => kiesBegrip(b, "kaart")} />
                ) : (
                  <HistorieTab key={wg.revisie} id={id} bronnen={wg.bronnen} />
                ),
            }))}
          />
        </>
      )}
    </WerkgebiedSchil>
  );
}

// Startactiviteit a en activiteit 1b: wat de velden vragen, in de woorden van de vraagkaarten.
const DOSSIER_HINT: Partial<Record<DossierVeld, string>> = {
  aanleiding: "waarom we analyseren",
  context: "de situatie eromheen",
  doel: "wat de analyse moet opleveren",
  praktijkvoorbeeld: "hoe een burger of bedrijf het doorloopt",
};

function GegevensFormulier({ wg, onBewaar, onAnnuleer }: {
  wg: Werkgebied;
  onBewaar: (w: { naam: string; peildatum: string | null; status: WerkgebiedStatus } & Record<DossierVeld, string>) => Promise<void>;
  onAnnuleer: () => void;
}) {
  const [naam, setNaam] = useState(wg.naam);
  // Het dossier in één toestand: dezelfde velden en volgorde als de kop (`DOSSIER_VELDEN`).
  const [dossier, setDossier] = useState<Record<DossierVeld, string>>(
    () => Object.fromEntries(DOSSIER_VELDEN.map(({ veld }) => [veld, wg[veld] ?? ""])) as Record<DossierVeld, string>);
  const [peildatum, setPeildatum] = useState(wg.peildatum ?? "");
  const [status, setStatus] = useState<WerkgebiedStatus>(wg.status);
  const [bezig, setBezig] = useState(false);

  async function bewaar(e: React.FormEvent) {
    e.preventDefault();
    if (!naam.trim() || bezig) return;
    setBezig(true);
    await onBewaar({ naam: naam.trim(), ...dossier, peildatum: peildatum || null, status });
    setBezig(false);
  }

  return (
    <form onSubmit={bewaar} className="mb-5 space-y-4 rounded-button border border-line bg-paper p-4">
      <Field label="Naam" required>
        <Input value={naam} onChange={(e) => setNaam(e.target.value)} maxLength={200} required autoFocus />
      </Field>
      {DOSSIER_VELDEN.map(({ veld, label }) => (
        <Field key={veld} label={label} hint={DOSSIER_HINT[veld]}>
          <Textarea value={dossier[veld]} rows={2} maxLength={4000}
            onChange={(e) => setDossier((d) => ({ ...d, [veld]: e.target.value }))} />
        </Field>
      ))}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Gewenste peildatum" hint="de wettekst zelf komt uit de actuele graaf">
          <Input type="date" value={peildatum} onChange={(e) => setPeildatum(e.target.value)} />
        </Field>
        <Field label="Status">
          <Select value={status} onChange={(e) => setStatus(e.target.value as WerkgebiedStatus)}>
            {(Object.keys(STATUS_LABEL) as WerkgebiedStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <ButtonRow>
        <Button type="submit" disabled={!naam.trim() || bezig}>
          {bezig ? "Bezig…" : "Opslaan"}
        </Button>
        <Button type="button" variant="secondary" onClick={onAnnuleer}>
          Annuleren
        </Button>
      </ButtonRow>
    </form>
  );
}
