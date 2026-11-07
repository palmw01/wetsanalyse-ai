"use client";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { useCallback, useEffect, useState } from "react";
import { Button, KNOP_GEVAAR, KNOP_GEVAAR_SCHERP } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Card } from "@/components/ui/Card";
import { BerichtBadge } from "@/components/ui/BerichtBadge";
import { Tag } from "@/components/ui/Badge";
import { ChevronOmlaag } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { Pagination } from "@/components/Pagination";
import { Markdown } from "@/components/werkplek/Markdown";
import { datumTijd } from "@/lib/datum";
import { BerichtEditor } from "./BerichtEditor";
import {
  isApiError,
  listAlleBerichten,
  verwijderBericht,
  zetPublicatie,
} from "@/lib/api";
import type { AdminBerichtenPaginaOut, AdminBerichtOut, BerichtType } from "@/lib/types";

const PER_PAGINA = 20;

export function BerichtenBeheerPanel() {
  const [data, setData] = useState<AdminBerichtenPaginaOut | null>(null);
  const [pagina, setPagina] = useState(1);
  const [fout, setFout] = useState<string | null>(null);
  const [uitgeklapt, setUitgeklapt] = useState<Set<number>>(new Set());
  // false = lijstweergave; null = nieuw bericht; AdminBerichtOut = bewerken
  const [editBericht, setEditBericht] = useState<AdminBerichtOut | null | false>(false);

  function toggleUitgeklapt(id: number) {
    setUitgeklapt((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const laad = useCallback(async (p: number) => {
    setFout(null);
    try {
      setData(await listAlleBerichten(p, PER_PAGINA));
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
      setData({ items: [], totaal: 0, pagina: p, per_pagina: PER_PAGINA });
    }
  }, []);

  useEffect(() => {
    // Data-load bij mount: setState gebeurt async ná de fetch (geen synchrone render-cascade).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad(1);
  }, [laad]);

  function onPage(p: number) {
    setPagina(p);
    void laad(p);
  }

  async function onPublicatie(b: AdminBerichtOut) {
    try {
      await zetPublicatie(b.id, !b.gepubliceerd);
      await laad(pagina);
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }

  // Bevestigen doet de knop zelf (twee klikken), zoals overal in deze app.
  async function onVerwijder(b: AdminBerichtOut) {
    try {
      await verwijderBericht(b.id);
      await laad(pagina);
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
    }
  }

  if (editBericht !== false) {
    return (
      <SettingGroup titel={editBericht ? "Bericht bewerken" : "Nieuw bericht"}>
        <BerichtEditor
          bericht={editBericht}
          onCancel={() => setEditBericht(false)}
          onDone={() => { setEditBericht(false); void laad(pagina); }}
        />
      </SettingGroup>
    );
  }

  return (
    <SettingGroup titel="Berichten beheren" count={data?.totaal} omschrijving="Release notes en aankondigingen voor analisten."
      acties={<Button size="sm" onClick={() => setEditBericht(null)}>Nieuw bericht</Button>}>
      {fout && <Melding type="fout" compact className="mb-4">{fout}</Melding>}

      {data === null && <SkeletonCard regels={2} />}

      {data !== null && data.items.length === 0 && (
        <p className="text-sm text-muted">Nog geen berichten.</p>
      )}

      {data !== null && data.items.length > 0 && (
        <div className="space-y-3">
          {data.items.map((b) => {
            const open = uitgeklapt.has(b.id);
            return (
              <Card key={b.id} className="overflow-hidden p-0">
                <button
                  type="button"
                  onClick={() => toggleUitgeklapt(b.id)}
                  className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-surface transition-colors"
                  aria-expanded={open}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <BerichtBadge type={b.type as BerichtType} />
                      {b.versie && <Tag>{b.versie}</Tag>}
                      <StatusLabel toon={b.gepubliceerd ? "groen" : "neutraal"}>
                        {b.gepubliceerd ? "Gepubliceerd" : "Concept"}
                      </StatusLabel>
                      <span className="text-xs text-faint">{datumTijd(b.created)}</span>
                    </div>
                    <p className="mt-1 text-sm font-semibold text-ink">{b.titel}</p>
                  </div>
                  <ChevronOmlaag className={`mt-1 shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
                </button>
                {open && (
                  <div className="border-t border-line px-4 pb-4 pt-3">
                    <div className="text-sm">
                      <Markdown tekst={b.inhoud} links="vrij" />
                    </div>
                    <ButtonRow align="start" className="mt-3">
                      <Button size="sm" variant="secondary" onClick={() => setEditBericht(b)}>
                        Bewerken
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => void onPublicatie(b)}>
                        {b.gepubliceerd ? "Depubliceren" : "Publiceren"}
                      </Button>
                      <BevestigKnop
                        onBevestig={() => void onVerwijder(b)}
                        bevestigTekst="Definitief verwijderen?"
                        className={KNOP_GEVAAR}
                        bevestigClassName={KNOP_GEVAAR_SCHERP}
                      >
                        Verwijderen
                      </BevestigKnop>
                    </ButtonRow>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {data !== null && (
        <Pagination
          page={pagina}
          totalPages={Math.max(1, Math.ceil(data.totaal / PER_PAGINA))}
          total={data.totaal}
          pageSize={PER_PAGINA}
          onPage={onPage}
        />
      )}
    </SettingGroup>
  );
}
