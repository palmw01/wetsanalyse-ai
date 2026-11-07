"use client";

import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { EXPORT_FORMATEN } from "@/lib/begrippen";
import { exporteerBegrippen, exporteerWerkgebied, haalBegrip, haalBronselectie, haalWerkgebied, lijstBegrippen } from "@/lib/api";
import { begripAlsMarkdown, begrippenAlsMarkdown, bronselectieAlsMarkdown, deelvraagAlsMarkdown, dossierAlsMarkdown, voorstellenAlsMarkdown } from "@/lib/artefactMarkdown";
import { termenVan } from "@/lib/begripTermen";
import { PaneelKop } from "@/components/ui/PaneelKop";
import { VersieKiezer } from "@/components/ui/VersieKiezer";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { BegripCompact } from "@/components/werkgebieden/BegripInhoud";
import { BegripVoorstellen } from "@/components/werkgebieden/BegripVoorstellen";
import { BronnenBijDeelvraag } from "@/components/werkgebieden/BronnenBijDeelvraag";
import { DeelvraagPaneel } from "@/components/werkgebieden/DeelvraagPaneel";
import { OnbewaardMelding } from "@/components/werkgebieden/OnbewaardMelding";
import { WerkgebiedSamenvatting } from "@/components/werkgebieden/WerkgebiedSamenvatting";
import { Melding } from "@/components/ui/Melding";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { knopKlasse } from "@/components/ui/Button";
import { foutTekst, verwijderWerkgebied } from "@/lib/api";
import { metSpoor } from "@/lib/uiSpoor";
import { verwijderdUit, verwijderdZin, type Verwijderd } from "@/lib/verwijderen";
import { isRevisieConflict } from "@/lib/werkgebied";
import { artefactKop, type WerkgebiedArtefact } from "@/lib/artefact";
import type { ArtefactVersie, Begrip, Deelvraag, GroepenAntwoord, RelatiesAntwoord, Werkgebied } from "@/lib/types";
import type { BronselectieOverzicht } from "@/lib/bronselectie";
import { STATUS_LABEL, WERKGEBIED_EXPORT_FORMATEN } from "@/lib/werkgebied";
import { useOnbewaardBewaker } from "@/lib/useOnbewaardBewaker";
import { artefactPad, begripPad, deelvraagPad, projectPad } from "@/lib/werkgebiedPaden";

/** Kopiëren en exporteren per soort (4 nov 2026): altijd Markdown, bij het werkgebied de PDF en bij de begrippen de
 *  bestaande exports van het begrippenkader. De inhoud wordt bij de klik opgehaald – de kop kent de gegevens van de
 *  inhoud niet. */
function exportVan(doel: WerkgebiedArtefact, opname?: Opname | null): Pick<React.ComponentProps<typeof ExportKnop>, "markdown" | "formaten" | "onDownload"> {
  const id = doel.werkgebied_id;
  // Een oude versie: kopiëren en exporteren gaan over wat je ziet (besluit gebruiker), dus uit de opname.
  if (opname) {
    const o = opname.inhoud;
    switch (doel.soort) {
      case "werkgebied": return { formaten: [], markdown: () => dossierAlsMarkdown(o.werkgebied!, o.bronselectie ?? undefined) };
      case "bronselectie": return { formaten: [], markdown: () => bronselectieAlsMarkdown(o.bronselectie!) };
      case "deelvraag": return { formaten: [], markdown: () => {
        const d = o.bronselectie?.deelvragen.find((x) => x.id === doel.deelvraag_id);
        return d ? deelvraagAlsMarkdown(d) : `# ${o.deelvraag?.vraag ?? doel.titel}\n`;
      } };
      case "begrip": return { formaten: [], markdown: () => begripAlsMarkdown(o.begrip!) };
      // De PDF en de exports van het begrippenkader gaan over de stand van nu: niet bij een oude versie.
      default: return { formaten: [], markdown: () => voorstellenAlsMarkdown(
        o.werkgebied?.naam ? `Begripsvoorstellen – ${o.werkgebied.naam}` : "Begripsvoorstellen", termenVan(o.groepen ?? null)) };
    }
  }
  switch (doel.soort) {
    case "werkgebied":
      return { formaten: WERKGEBIED_EXPORT_FORMATEN, onDownload: (f) => exporteerWerkgebied(id, f),
        markdown: async () => dossierAlsMarkdown(await haalWerkgebied(id), await haalBronselectie(id).catch(() => undefined)) };
    case "bronselectie":
      return { formaten: [], markdown: async () => bronselectieAlsMarkdown(await haalBronselectie(id)) };
    case "deelvraag":
      return { formaten: [], markdown: async () => {
        const d = (await haalBronselectie(id)).deelvragen.find((x) => x.id === doel.deelvraag_id);
        return d ? deelvraagAlsMarkdown(d) : `# ${doel.titel}\n`;
      } };
    case "begrip":
      return { formaten: [], markdown: async () => begripAlsMarkdown(await haalBegrip(id, doel.begrip_id ?? "")) };
    default:
      return { formaten: EXPORT_FORMATEN, onDownload: (f) => exporteerBegrippen(id, f as "json" | "csv" | "ttl" | "ttl-alle"),
        markdown: async () => {
          const [wg, lijst] = await Promise.all([haalWerkgebied(id), lijstBegrippen(id)]);
          return begrippenAlsMarkdown(wg.naam, lijst.begrippen);
        } };
  }
}

/** Een versie van het artefact (api `artefact_versies`), met de inhoud die de panelen van deze soort kennen. */
type Opname = Omit<ArtefactVersie, "inhoud"> & {
  inhoud: { werkgebied?: Werkgebied; deelvraag?: Deelvraag | null; bronselectie?: BronselectieOverzicht;
    begrip?: Begrip; relaties?: RelatiesAntwoord | null; groepen?: GroepenAntwoord };
};

/** Waar *Open volledige pagina* heen gaat: de pagina van wat het paneel toont (spoor G2). */
function paginaVan(doel: WerkgebiedArtefact): string {
  const id = doel.werkgebied_id;
  switch (doel.soort) {
    case "begrippen": return artefactPad(id, "begrippen");
    case "begrip": return doel.begrip_id ? begripPad(id, doel.begrip_id) : artefactPad(id, "begrippen");
    case "deelvraag": return doel.deelvraag_id ? deelvraagPad(id, doel.deelvraag_id) : projectPad(id);
    case "bronselectie": return artefactPad(id, "bronselectie");
    default: return projectPad(id);
  }
}
/** Een artefact van een werkgebied in de werkplek, in dezelfde schil als een annotatie (een kolom naast
 *  de chat vanaf 1280px, anders een sheet):
 *
 *  - **begrippen** – de voorstellen van Lex (`BegripVoorstellen`), dezelfde inhoud als op de tab
 *    Begrippen. Een overgenomen begrip opent in het werkgebied: daar staan de kaart en de passages.
 *  - **begrip** (F3d, spoor N) – één begrip (`BegripCompact`): dezelfde inhoud als zijn pagina, onder elkaar. Je leest,
 *    bewerkt, beoordeelt en accordeert hier.
 *  - **deelvraag** (F3d) – één deelvraag (`DeelvraagPaneel`): stand, de voorstellen die haar vervangen,
 *    bronnen en de kandidaten die Lex erbij vond.
 *  - **bronselectie** (spoor J) – de bronselectie per deelvraag (`BronnenBijDeelvraag`, dezelfde als de tab Bronnen): de voortgang, de
 *    bronnen met hun rol per deelvraag, de voorstellen en de onderzoekspunten; de deelvraag waar het gesprek
 *    staat is open, en *Ga verder met deelvraag n* zet een andere klaar in hetzelfde gesprek.
 *  - **werkgebied** – het werkgebied dat Lex met de analist samenstelde (activiteit 1): de
 *    `WerkgebiedSamenvatting` (dezelfde als bovenaan de pagina) en de weg naar die pagina.
 *
 *  Eén schakelaar op de soort; geen Lex-knoppen, ook niet in de kop (spoor K): je zit al in het gesprek, en de
 *  suggesties boven het invoerveld doen het werk. Een deelvraag in de samenvatting is wel aan te klikken.
 *
 *  Eén inhoud, twee schillen. Net als op de tab vraagt het paneel eerst bevestiging als de kaart
 *  niet-bewaarde wijzigingen draagt: bij sluiten (kruisje, Escape, achtergrond), bij een link weg en bij elke
 *  wissel vanuit de werkplek (FB-05). De bewaker hoort daarom bij de werkplek (`WerkplekClient`,
 *  `wisselPaneel`): die wisselt het paneel, dit paneel toont alleen zijn vraag. */
export function WerkgebiedArtefactPaneel({ doel, variant = "side", bewaker, onOnbewaard, onSluit, onWissel, onVerwijderd, onKlaar, klaarVoor }: {
  doel: WerkgebiedArtefact;
  /** De bewaker van de werkplek; `onOnbewaard` meldt hem wat er onbewaard openstaat. */
  bewaker: ReturnType<typeof useOnbewaardBewaker>;
  onOnbewaard: (onbewaard: boolean) => void;
  /** De bronselectie: *Klaar met deze deelvraag* stuurt de actie van het open kaartje in het gesprek. */
  onKlaar?: (deelvraagId: string) => void;
  klaarVoor?: string;
  variant?: DialogVariant;
  onSluit: () => void;
  /** Het werkgebied is vanuit dit paneel verwijderd: de werkplek verlaat het dan, als ze erin stond. */
  onVerwijderd?: (werkgebiedId: string) => void;
  /** Een ander artefact in hetzelfde paneel (de opvolger van een vervangen deelvraag of begrip). */
  onWissel?: (doel: WerkgebiedArtefact) => void;
}) {
  const router = useRouter();
  const [exportFout, setExportFout] = useState<string | null>(null);
  // De vraag staat bovenaan de inhoud: wie ver naar beneden gescrold zat, moet hem toch zien.
  const vraagRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (bewaker.wachtend) vraagRef.current?.scrollIntoView({ block: "nearest" });
  }, [bewaker.wachtend]);
  // `onSluit` loopt zelf door de bewaker (`wisselPaneel` met *sluiten*).
  const sluit = onSluit;
  const naarWerkgebied = paginaVan(doel);
  const { soort, titel } = artefactKop(doel);
  // De versiekiezer (deel 2 van de artefacten): `undefined` zolang hij nog kiest, `null` voor *Nu*, anders de versie die
  // het paneel alleen-lezend toont. Zonder versie op de chip is het gewoon *Nu*.
  const metVersie = doel.versie;
  const [opname, setOpname] = useState<Opname | null | undefined>(metVersie ? undefined : null);
  return (
    <Dialog label={soort ? `${soort}: ${titel}` : titel} variant={variant} onSluit={sluit}>
      <div data-artefact data-artefact-soort={doel.soort} className="flex min-h-0 flex-1 flex-col">
        <PaneelKop soort={soort} titel={titel} pagina={naarWerkgebied} onSluit={sluit}
          // Pas als de versie vaststaat: anders gaat de export over de stand van nu in plaats van over wat je zo ziet.
          acties={opname !== undefined && <ExportKnop onFout={setExportFout} titel={titel} {...exportVan(doel, opname)} />}
          onder={metVersie && <VersieKiezer versie={metVersie} onKies={(v) => setOpname(v as Opname | null)} />} />
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {exportFout && <Melding type="waarschuwing" className="mb-4">{exportFout}</Melding>}
          {bewaker.wachtend && (
            <div ref={vraagRef} data-onbewaard-vraag className="mb-4">
              <OnbewaardMelding
                handeling={bewaker.wachtend.handeling}
                onBlijf={bewaker.blijf}
                onToch={() => {
                  onOnbewaard(false);
                  bewaker.toch();
                }}
              />
            </div>
          )}
          {opname === undefined ? (
            <SkeletonCard regels={4} />
          ) : doel.soort === "werkgebied" ? (
            <WerkgebiedInhoud id={doel.werkgebied_id} naarWerkgebied={naarWerkgebied} opname={opname?.inhoud}
              onVerwijderd={() => onVerwijderd?.(doel.werkgebied_id)} />
          ) : doel.soort === "begrip" && doel.begrip_id ? (
            <BegripCompact key={opname?.id ?? "nu"} context={{ soort: "werkgebied", werkgebiedId: doel.werkgebied_id }}
              begripId={doel.begrip_id} onOnbewaard={onOnbewaard}
              opname={opname?.inhoud.begrip ? { begrip: opname.inhoud.begrip, relaties: opname.inhoud.relaties } : undefined}
              onNaarBegrip={(b) => onWissel
                ? onWissel({ soort: "begrip", werkgebied_id: doel.werkgebied_id, run_id: "", begrip_id: b, titel: "" })
                : router.push(begripPad(doel.werkgebied_id, b))} />
          ) : doel.soort === "deelvraag" && doel.deelvraag_id ? (
            <DeelvraagPaneel werkgebiedId={doel.werkgebied_id} deelvraagId={doel.deelvraag_id} opname={opname?.inhoud}
              onKies={onWissel ? (d) => onWissel({ soort: "deelvraag", werkgebied_id: doel.werkgebied_id, run_id: "",
                deelvraag_id: d.id, titel: d.vraag }) : undefined} />
          ) : doel.soort === "bronselectie" ? (
            <BronnenBijDeelvraag werkgebiedId={doel.werkgebied_id} huidig={doel.deelvraag_id} inGesprek
              opname={opname?.inhoud.bronselectie} onKlaar={onKlaar} klaarVoor={klaarVoor} />
          ) : (
            <BegripVoorstellen key={opname?.id ?? "nu"} id={doel.werkgebied_id} runId={doel.run_id}
              opname={opname?.inhoud.groepen} />
          )}
        </div>
      </div>
    </Dialog>
  );
}

/** Het werkgebied zelf: wat er met Lex is samengesteld, zoals het nu bij de api staat – dezelfde
 *  samenvatting als bovenaan de werkgebiedpagina. */
function WerkgebiedInhoud({ id, naarWerkgebied, onVerwijderd, opname }: {
  id: string;
  naarWerkgebied: string;
  onVerwijderd: () => void;
  /** Een oude versie: alleen lezen, uit de opname, zonder verwijderen. */
  opname?: Opname["inhoud"];
}) {
  if (opname?.werkgebied) {
    const w = opname.werkgebied;
    return (
      <div data-werkgebied-inhoud data-alleen-lezen className="space-y-4 text-sm text-ink">
        <p className="text-xs text-muted">{STATUS_LABEL[w.status]} · revisie {w.revisie}</p>
        <WerkgebiedSamenvatting wg={w} bronselectie={opname.bronselectie ?? null} />
        <Link href={naarWerkgebied} className={`${knopKlasse("secondary", "md")} w-full sm:w-auto`}>Open het werkgebied</Link>
      </div>
    );
  }
  return <WerkgebiedLive id={id} naarWerkgebied={naarWerkgebied} onVerwijderd={onVerwijderd} />;
}

function WerkgebiedLive({ id, naarWerkgebied, onVerwijderd }: {
  id: string;
  naarWerkgebied: string;
  onVerwijderd: () => void;
}) {
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [verwijderd, setVerwijderd] = useState<Verwijderd | null>(null);
  const [poging, setPoging] = useState(0);
  useEffect(() => {
    let levend = true;
    haalWerkgebied(id).then((w) => { if (levend) setWg(w); }).catch((e) => {
      if (!levend) return;
      // Een verwijderd werkgebied is een toestand, geen fout – zoals een verwijderde annotatie.
      const v = verwijderdUit(e);
      if (v) setVerwijderd(v);
      else setFout(foutTekst(e));
    });
    return () => { levend = false; };
  }, [id, poging]);

  async function verwijder() {
    if (!wg) return;
    setMelding(null);
    try {
      await metSpoor("werkgebied_verwijderen", () => verwijderWerkgebied(id, wg.revisie));
      setWg(null);
      setPoging((p) => p + 1);              // de api zegt nu wanneer en door wie
      onVerwijderd();
    } catch (e) {
      if (isRevisieConflict(e)) {
        setPoging((p) => p + 1);
        setMelding("Iemand anders wijzigde dit werkgebied net. Bekijk de nieuwe stand voordat je het verwijdert.");
      } else setMelding(foutTekst(e, "Het werkgebied is niet verwijderd."));
    }
  }

  if (verwijderd) {
    return <Melding type="uitleg"><span data-verwijderd>{verwijderdZin(verwijderd)}</span></Melding>;
  }
  if (fout) {
    return (
      <Melding type="fout" titel="Het werkgebied kon niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => { setFout(null); setPoging((p) => p + 1); }}>
          Opnieuw proberen
        </button>
      </Melding>
    );
  }
  if (!wg) return <SkeletonCard regels={4} />;
  return (
    <div data-werkgebied-inhoud className="space-y-4 text-sm text-ink">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted">{STATUS_LABEL[wg.status]} · revisie {wg.revisie}</p>
        <VerwijderKnop soort="werkgebied" onBevestig={verwijder} />
      </div>
      {melding && <Melding type="waarschuwing" compact>{melding}</Melding>}
      <WerkgebiedSamenvatting wg={wg} />
      <Link href={naarWerkgebied}
        className={`${knopKlasse("primary", "md")} w-full sm:w-auto`}>
        Open het werkgebied
      </Link>
    </div>
  );
}
