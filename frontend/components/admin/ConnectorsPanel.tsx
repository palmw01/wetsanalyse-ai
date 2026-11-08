"use client";

import { useCallback, useEffect, useState } from "react";
import { Tag } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Card } from "@/components/ui/Card";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { connectorAudit, isApiError, listConnectors, zetConnector } from "@/lib/api";
import { datumTijd } from "@/lib/datum";
import type { Connector, ConnectorAuditRegel } from "@/lib/types";

/** De bronconnectors (ADR-013): welke bronnen buiten de wettekst Lex mag raadplegen.
 *
 *  Welke er bestaan, staat in de code: een bronconnector is een getypeerde tool met een eigen vindplaats, en Lex
 *  citeert eruit zoals uit de wet. Hier zet een beheerder ze alleen aan of uit; elke wijziging staat in de audit.
 *  Aan betekent: beschikbaar in het menu bij het gesprek. De straat moet hem ook aanbieden (`CONNECTOR_*`). */
export function ConnectorsPanel() {
  const [lijst, setLijst] = useState<Connector[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState<string | null>(null);
  const [audit, setAudit] = useState<Record<string, ConnectorAuditRegel[]>>({});

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setLijst(await listConnectors());
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }, []);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  async function wissel(c: Connector) {
    setBezig(c.naam);
    setFout(null);
    try {
      const nieuw = await zetConnector(c.naam, !c.aan);
      setLijst((oud) => oud?.map((x) => (x.naam === nieuw.naam ? nieuw : x)) ?? null);
      if (audit[c.naam]) setAudit({ ...audit, [c.naam]: await connectorAudit(c.naam) });
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    } finally {
      setBezig(null);
    }
  }

  async function toonAudit(naam: string) {
    if (audit[naam]) {
      const { [naam]: _weg, ...rest } = audit;
      setAudit(rest);
      return;
    }
    try {
      setAudit({ ...audit, [naam]: await connectorAudit(naam) });
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }

  return (
    <div>
      <SettingGroup titel="Connectors" count={lijst?.length}
        omschrijving="Bronnen buiten de wettekst die Lex mag raadplegen en citeren, elk met een eigen vindplaats. Een bron is geen wettekst: Lex zegt wat de wet zegt alleen op grond van de bepaling zelf.">
        {fout && <Melding type="fout" className="mb-3">{fout}</Melding>}
        {lijst === null ? (
          <SkeletonCard regels={2} />
        ) : (
          <div className="space-y-3">
            {lijst.map((c) => (
              <Card key={c.naam} className="p-3" data-connector={c.naam}>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-display font-semibold text-ink">{c.label}</span>
                  <StatusLabel toon={c.aan ? "groen" : "neutraal"}>{c.aan ? "Aan" : "Uit"}</StatusLabel>
                  <Tag>{c.brontype}</Tag>
                </div>
                <p className="mt-1 text-sm text-muted">{c.beschrijving}</p>
                {c.door && (
                  <p className="mt-1 text-xs text-muted">
                    {c.aan ? "Aangezet" : "Uitgezet"} door {c.door}{c.bijgewerkt ? `, ${datumTijd(c.bijgewerkt)}` : ""}.
                  </p>
                )}
                {audit[c.naam] && (
                  <ul className="mt-2 space-y-0.5 text-xs text-muted" aria-label={`Audit van ${c.label}`}>
                    {audit[c.naam].length === 0 ? <li>Nog geen wijzigingen.</li> : audit[c.naam].map((r, i) => (
                      <li key={i}>{datumTijd(r.tijdstip)}: {r.actie === "aan" ? "aangezet" : "uitgezet"} door {r.door}</li>
                    ))}
                  </ul>
                )}
                <ButtonRow align="start" className="mt-3">
                  <Button size="sm" variant={c.aan ? "secondary" : "primary"} disabled={bezig === c.naam}
                    onClick={() => wissel(c)}>
                    {bezig === c.naam ? "Bezig…" : c.aan ? "Uitzetten" : "Aanzetten"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => toonAudit(c.naam)} aria-expanded={Boolean(audit[c.naam])}>
                    {audit[c.naam] ? "Verberg audit" : "Audit"}
                  </Button>
                </ButtonRow>
              </Card>
            ))}
          </div>
        )}
      </SettingGroup>
    </div>
  );
}
