"use client";

import { useState } from "react";

import { knopKlasse } from "@/components/ui/Button";
import { Downloaden } from "@/components/ui/Icoon";
import { MenuLijst } from "@/components/ui/MeerMenu";
import { MENU_PANEEL, MENU_RIJ } from "@/components/ui/Menu";
import { Popover } from "@/components/ui/Popover";
import { downloadTekst, foutTekst, type ExportFormaat } from "@/lib/api";
import { bestandsnaam, kopVan } from "@/lib/artefactMarkdown";

interface Props {
  onFout: (melding: string) => void;
  /** De download zelf. Zonder (de rondleiding, die geen api heeft) sluit het keuzepaneel zonder
   *  bestand. */
  onDownload?: (formaat: ExportFormaat) => Promise<void>;
  /** Welke vormen er te kiezen zijn; standaard die van een annotatie. Leeg = alleen Markdown. */
  formaten?: { formaat: ExportFormaat; label: string; uitleg: string }[];
  /** Het artefact als Markdown (`lib/artefactMarkdown.ts`): bovenaan *Kopieer als Markdown* en *Download als
   *  Markdown* – één knop voor kopiëren en exporteren bij elke soort (4 nov 2026). Mag ophalen (async). */
  markdown?: () => Promise<string> | string;
  /** De titel van het artefact: de naam van het Markdown-bestand als de tekst geen eigen kop (`# …`) heeft. */
  titel?: string;
}

const FORMATEN: { formaat: ExportFormaat; label: string; uitleg: string }[] = [
  { formaat: "pdf", label: "PDF", uitleg: "wettekst, markeringen met hun herkomst, beurtmeting en dekking" },
  { formaat: "csv", label: "CSV", uitleg: "één rij per markering, met de herkomst in eigen kolommen" },
  { formaat: "json", label: "JSON", uitleg: "alles, machineleesbaar, met schema (v4)" },
  { formaat: "trig", label: "RDF (TriG)", uitleg: "de annotatielagen als named graphs, zoals in de kennisgraaf" },
];

interface RegelProps extends Props {
  /** Sluit het menu eromheen na een geslaagde keuze. */
  sluit: () => void;
  /** Na een geslaagde kopie: de knop eromheen mag "Gekopieerd" zeggen. */
  onGekopieerd?: () => void;
}

/** De regels van het exportmenu – de ene bron voor kopiëren en exporteren (4 nov 2026). Ze staan in het menu ⋯ van een
 *  paneelkop (`PaneelKop.menu`, 8 nov 2026: een smal paneel heeft geen plek voor een losse knop) en in `ExportKnop` op
 *  een pagina. Elke regel is een `menuitem` in een `MenuLijst`; na een geslaagde keuze gaat het menu dicht. */
export function ExportRegels({ onFout, onDownload, formaten = FORMATEN, markdown, titel = "artefact", sluit, onGekopieerd }: RegelProps) {
  const [bezig, setBezig] = useState<ExportFormaat | "kopie" | "md" | null>(null);

  async function alsMarkdown(hoe: "kopie" | "md") {
    if (!markdown) return;
    setBezig(hoe);
    try {
      const tekst = await markdown();
      if (hoe === "kopie") {
        await navigator.clipboard.writeText(tekst);
        onGekopieerd?.();
      } else {
        downloadTekst(tekst, bestandsnaam(kopVan(tekst) || titel), "text/markdown");
      }
      sluit();
    } catch (e) {
      onFout(hoe === "kopie" ? "Kopiëren lukte niet (het klembord is hier niet beschikbaar)." : foutTekst(e, "Exporteren is niet gelukt."));
    } finally {
      setBezig(null);
    }
  }

  async function download(formaat: ExportFormaat) {
    setBezig(formaat);
    try {
      await onDownload?.(formaat);
      sluit();
    } catch (e) {
      onFout(foutTekst(e, "Exporteren is niet gelukt."));
    } finally {
      setBezig(null);
    }
  }

  const regels: { sleutel: string; label: string; uitleg: string; doe: () => void; data?: string }[] = [
    ...(markdown ? ([["kopie", "Kopieer als Markdown", "om in een eigen document te plakken"],
      ["md", "Download als Markdown", "hetzelfde, als bestand"]] as const).map(([hoe, label, uitleg]) =>
      ({ sleutel: hoe, label, uitleg, doe: () => void alsMarkdown(hoe), data: hoe })) : []),
    ...(onDownload ? formaten.map((f) => ({ sleutel: f.formaat, label: f.label, uitleg: f.uitleg, doe: () => void download(f.formaat) })) : []),
  ];
  return (
    <>
      {regels.map((r) => (
        <li key={r.sleutel} role="none">
          <button type="button" role="menuitem" disabled={bezig !== null} onClick={r.doe} data-markdown={r.data}
            data-export={r.sleutel} className={`${MENU_RIJ} flex-col !items-start !gap-0.5`}>
            <span className="text-sm font-medium text-ink">{bezig === r.sleutel ? `${r.label} – bezig…` : r.label}</span>
            <span className="text-xs text-muted">{r.uitleg}</span>
          </button>
        </li>
      ))}
    </>
  );
}

/** Of er iets te exporteren valt: zonder Markdown en zonder download heeft het menu geen exportregels. */
export function heeftExport({ markdown, onDownload }: Pick<Props, "markdown" | "onDownload">): boolean {
  return Boolean(markdown || onDownload);
}

/** *Exporteren* als losse knop, in de kop van een pagina (`KleineActies`). Download de annotatie – ook halverwege de
 *  review. Bewust geen statusdrempel: een concept exporteren is een normale handeling, en het bestand zegt zelf hoeveel
 *  er nog te beoordelen is. In een paneel naast het gesprek staan dezelfde regels in het menu ⋯. */
export function ExportKnop(props: Props) {
  const [gekopieerd, setGekopieerd] = useState(false);
  return (
    <Popover
      ariaLabel="Exporteren"
      className={`w-64 ${MENU_PANEEL}`}
      trigger={(open, toggle) => (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className={`${knopKlasse("secondary", "xs")} gap-1`}
        >
          <Downloaden />
          {gekopieerd ? "Gekopieerd" : "Exporteren"}
        </button>
      )}
    >
      {(sluit) => (
        <MenuLijst>
          <ExportRegels {...props} sluit={sluit} onGekopieerd={() => {
            setGekopieerd(true);
            window.setTimeout(() => setGekopieerd(false), 1500);
          }} />
        </MenuLijst>
      )}
    </Popover>
  );
}
