"use client";

import { Leeg } from "@/components/ui/Leeg";
import { LaadStand } from "@/components/ui/LaadStand";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart, ObjectRij, ObjectRijen } from "@/components/ui/Pagina";
import { ExportKnop } from "@/components/werkplek/ExportKnop";
import { downloadTekst } from "@/lib/api";
import { aantal } from "@/lib/aantal";
import { bestandsnaam } from "@/lib/artefactMarkdown";
import {
  REGEL_SOORT_LABEL, REGEL_STATUS_LABEL, REGEL_STATUS_TOON, buren, inKetenVolgorde, regelsAlsMarkdown,
  type Regel, type RegelKeten as Keten,
} from "@/lib/regels";
import { useRegelKeten } from "@/lib/useRegel";
import { regelPad } from "@/lib/werkgebiedPaden";

/** De afleidingsregels van een werkgebied als keten (ADR-018 §6): de regels van onder naar boven, zodat elke regel staat
 *  na de regels waarvan hij een uitkomst gebruikt; de basisgegevens (invoer die geen regel afleidt) en de signalen
 *  (dezelfde uitvoer, een kring). Een rij opent de regel. Eén inhoud voor de pagina en het paneel naast het gesprek. */
export function RegelKeten({ werkgebiedId, naam, onOpen, opname, zonderExport = false }: {
  werkgebiedId: string;
  /** De naam van het werkgebied, voor de kop van de export. */
  naam: string;
  /** Naast het gesprek: een regel opent in hetzelfde paneel in plaats van op zijn pagina. */
  onOpen?: (r: Regel) => void;
  opname?: { regels: Regel[]; keten: Keten | null };
  /** Naast het gesprek staat de export in het menu ⋯ van de paneelkop. */
  zonderExport?: boolean;
}) {
  const { regels, keten, fout, laad } = useRegelKeten(werkgebiedId, opname);
  if (!regels) return <LaadStand wat="De afleidingsregels" fout={fout} onOpnieuw={laad} skelet="rijen" />;

  const actief = regels.filter((r) => r.status !== "afgewezen" && r.status !== "vervangen");
  const weg = regels.filter((r) => !actief.includes(r));
  const json = async () => downloadTekst(JSON.stringify({ regels, keten }, null, 2),
    bestandsnaam(`Afleidingsregels ${naam}`, "json"), "application/json");

  const rij = (r: Regel, i?: number) => {
    const b = keten ? buren(keten, r.id) : null;
    const sub = [REGEL_SOORT_LABEL[r.inhoud.soort], aantal(r.inhoud.gevallen.length, "geval", "gevallen"),
      b?.volgtOp.length ? `volgt op ${aantal(b.volgtOp.length, "regel", "regels")}` : "",
      r.inhoud.brontype === "beleid" ? "beleidsregel" : "",
      r.vervangen_door ? `vervangen door ${regels.find((x) => x.id === r.vervangen_door)?.naam || r.vervangen_door}` : "",
    ].filter(Boolean).join(" · ");
    const status = <StatusLabel toon={REGEL_STATUS_TOON[r.status]}>{REGEL_STATUS_LABEL[r.status]}</StatusLabel>;
    return (
      <ObjectRij key={r.id} data-regel-rij={r.id} href={regelPad(werkgebiedId, r.id)} onKies={onOpen && (() => onOpen(r))}
        voor={i !== undefined ? i + 1 : undefined} titel={r.naam || r.uitvoer} sub={sub} status={status} />
    );
  };

  return (
    <div className="space-y-4" data-regel-keten-lijst>
      {keten?.signalen.map((s, i) => <Melding key={i} type="waarschuwing" data-keten-signaal={s.soort}>{s.melding}</Melding>)}
      <Kaart titel="Regels in de volgorde van de keten" telling={actief.length}
        toelichting="Van onder naar boven: een regel staat na de regels waarvan hij een uitkomst gebruikt."
        acties={regels.length > 0 && !zonderExport && <ExportKnop titel="Afleidingsregels" formaten={[{ formaat: "json", label: "JSON", uitleg: "de regels en de keten, machineleesbaar" }]}
          markdown={() => regelsAlsMarkdown(regels, keten, naam)} onDownload={json} onFout={() => undefined} />}>
        {actief.length
          ? <ObjectRijen label="Afleidingsregels">{inKetenVolgorde(actief, keten).map((r, i) => rij(r, i))}</ObjectRijen>
          : <Leeg kader>Nog geen afleidingsregels. Vraag Lex in het gesprek om ze op te stellen.</Leeg>}
      </Kaart>
      {keten && keten.basisgegevens.length > 0 && (
        <Kaart titel="Basisgegevens" telling={keten.basisgegevens.length}
          toelichting="Invoer die geen regel afleidt: die komt uit de aanvraag, een registratie of de beschikking.">
          <ul className="flex flex-wrap gap-2" data-basisgegevens>
            {keten.basisgegevens.map((b) => <li key={b.begrip_id}><StatusLabel>{b.naam || b.begrip_id}</StatusLabel></li>)}
          </ul>
        </Kaart>
      )}
      {weg.length > 0 && (
        <Kaart titel="Afgewezen en vervangen" telling={weg.length}>
          <ObjectRijen label="Afgewezen en vervangen regels">{weg.map((r) => rij(r))}</ObjectRijen>
        </Kaart>
      )}
    </div>
  );
}
