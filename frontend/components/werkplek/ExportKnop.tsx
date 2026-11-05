"use client";

import { MENU_RIJ } from "@/components/ui/Menu";
import { useState } from "react";

import { Popover } from "@/components/ui/Popover";
import { downloadTekst, foutTekst, type ExportFormaat } from "@/lib/api";
import { bestandsnaam } from "@/lib/artefactMarkdown";

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
  /** De titel van het artefact: de naam van het Markdown-bestand. */
  titel?: string;
}

const FORMATEN: { formaat: ExportFormaat; label: string; uitleg: string }[] = [
  { formaat: "pdf", label: "PDF", uitleg: "wettekst, markeringen met hun herkomst, beurtmeting en dekking" },
  { formaat: "csv", label: "CSV", uitleg: "één rij per markering, met de herkomst in eigen kolommen" },
  { formaat: "json", label: "JSON", uitleg: "alles, machineleesbaar, met schema (v3)" },
  { formaat: "trig", label: "RDF (TriG)", uitleg: "de annotatielagen als named graphs, zoals in de kennisgraaf" },
];

/** Download de annotatie – ook halverwege de review. Bewust geen statusdrempel: een concept
 *  exporteren is een normale handeling, en het bestand zegt zelf hoeveel er nog te beoordelen is.
 *
 *  Het paneel sluit na een geslaagde download doordat de Popover met een nieuwe `key` remount;
 *  de Popover geeft zijn eigen sluiter niet aan zijn kinderen door. */
export function ExportKnop({ onFout, onDownload, formaten = FORMATEN, markdown, titel = "artefact" }: Props) {
  const [bezig, setBezig] = useState<ExportFormaat | "kopie" | "md" | null>(null);
  const [sleutel, setSleutel] = useState(0);
  const [gekopieerd, setGekopieerd] = useState(false);

  async function alsMarkdown(hoe: "kopie" | "md") {
    if (!markdown) return;
    setBezig(hoe);
    try {
      const tekst = await markdown();
      if (hoe === "kopie") {
        await navigator.clipboard.writeText(tekst);
        setGekopieerd(true);
        window.setTimeout(() => setGekopieerd(false), 1500);
      } else {
        downloadTekst(tekst, bestandsnaam(titel), "text/markdown");
      }
      setSleutel((k) => k + 1);
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
      setSleutel((k) => k + 1);
    } catch (e) {
      onFout(foutTekst(e, "Exporteren is niet gelukt."));
    } finally {
      setBezig(null);
    }
  }

  return (
    <Popover
      key={sleutel}
      ariaLabel="Exporteren"
      className="w-64 rounded-lg border border-line bg-paper p-1 shadow-lg"
      trigger={(open, toggle) => (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          disabled={bezig !== null}
          className="focus-ring inline-flex min-h-[24px] shrink-0 items-center gap-1 rounded-knop-xs border border-line px-2 py-0.5 text-[11px] font-medium text-muted transition-colors hover:bg-surface hover:text-ink disabled:opacity-60 coarse:min-h-[44px] coarse:px-3"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M12 3v12M7 11l5 5 5-5M4 21h16" />
          </svg>
          {gekopieerd ? "Gekopieerd" : bezig ? "Bezig…" : "Exporteren"}
        </button>
      )}
    >
      <ul className="space-y-0.5">
        {markdown && ([["kopie", "Kopieer als Markdown", "om in een eigen document te plakken"],
          ["md", "Download als Markdown", "hetzelfde, als bestand"]] as const).map(([hoe, label, uitleg]) => (
          <li key={hoe}>
            <button type="button" disabled={bezig !== null} onClick={() => void alsMarkdown(hoe)} data-markdown={hoe}
              className={`${MENU_RIJ} flex-col !items-start !gap-0.5`}>
              <span className="text-sm font-medium text-ink">{bezig === hoe ? `${label} – bezig…` : label}</span>
              <span className="text-xs text-muted">{uitleg}</span>
            </button>
          </li>
        ))}
        {onDownload && formaten.map((f) => (
          <li key={f.formaat}>
            <button
              type="button"
              disabled={bezig !== null}
              onClick={() => void download(f.formaat)}
              className={`${MENU_RIJ} flex-col !items-start !gap-0.5`}
            >
              <span className="text-sm font-medium text-ink">
                {bezig === f.formaat ? `${f.label} – bezig…` : f.label}
              </span>
              <span className="text-xs text-muted">{f.uitleg}</span>
            </button>
          </li>
        ))}
      </ul>
    </Popover>
  );
}
