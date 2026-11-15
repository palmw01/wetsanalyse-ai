"use client";

import { KleurStrip } from "@/components/annotaties/KleurStrip";
import { OverzichtKaart } from "@/components/ui/Pagina";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { documentStand } from "@/lib/annotatie";
import { naamVan } from "@/lib/annotatieOverzicht";
import { bepalingKort } from "@/lib/herkomst";
import type { DocumentSamenvatting } from "@/lib/types";
import { nodeLink } from "@/lib/annotatieNode";
import { StatusLabel } from "@/components/ui/Lijst";

/** "3 dagen geleden" – genoeg om te zien wat blijft liggen, zonder valse precisie. */
function geleden(iso?: string | null): string {
  if (!iso) return "onbekend";
  const ms = Date.now() - Date.parse(iso);
  if (Number.isNaN(ms)) return "onbekend";
  const dagen = Math.floor(ms / 86_400_000);
  if (dagen >= 1) return dagen === 1 ? "gisteren" : `${dagen} dagen geleden`;
  const uren = Math.floor(ms / 3_600_000);
  if (uren >= 1) return `${uren} uur geleden`;
  return "zojuist";
}


export function AnnotatieKaart({ doc, onVerwijder }: {
  doc: DocumentSamenvatting;
  /** Verwijderen vanuit de lijst, zoals in het paneel (`lib/verwijderen.ts`). */
  onVerwijder?: () => Promise<void>;
}) {
  const href = nodeLink({ bron_iri: doc.bron_iri ?? "", snapshot_id: doc.snapshot_id });
  const beoordeeld = doc.aantal_elementen - doc.te_beoordelen;
  const stand = documentStand(doc);
  return (
    <OverzichtKaart titel={naamVan(doc)} href={href} sub={`${bepalingKort(doc)} · ${doc.bwbId}`}
      status={<StatusLabel toon={stand.toon} uitleg={stand.uitleg}>{stand.label}</StatusLabel>}
      verwijder={onVerwijder && doc.bron_iri && <VerwijderKnop soort="annotatie" maat="sm" onBevestig={onVerwijder} />}>
      <KleurStrip perKlasse={doc.per_klasse} />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span>
          {doc.aantal_elementen === 0
            ? "nog geen markeringen"
            : `${beoordeeld} van ${doc.aantal_elementen} beoordeeld`}
        </span>
        {(["rood", "geel"] as const).map((niveau) =>
          (doc.per_aandacht?.[niveau] ?? 0) > 0 ? (
            <StatusLabel key={niveau} toon={niveau}>{doc.per_aandacht[niveau]} {niveau}</StatusLabel>
          ) : null,
        )}
        {(doc.verouderd ?? 0) > 0 && (
          <span title="Markeringen bij een oudere versie van de wettekst; ze staan als historie in de annotatie.">
            {doc.verouderd} verouderd
          </span>
        )}
        <span>bijgewerkt {geleden(doc.updated)}</span>
        {doc.laatste_model && <span className="font-mono text-[0.65rem]">{doc.laatste_model}</span>}
      </div>
    </OverzichtKaart>
  );
}
