"use client";

import { useEffect, useState } from "react";
import { isApiError, listBerichtenPagina, markeerAllesGelezen } from "@/lib/api";
import type { BerichtenPaginaOut, BerichtType } from "@/lib/types";
import { BerichtBadge } from "@/components/ui/BerichtBadge";
import { Tag } from "@/components/ui/Badge";
import { Melding } from "@/components/ui/Melding";
import { SettingGroup } from "@/components/ui/SettingRow";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { Markdown } from "@/components/werkplek/Markdown";
import { Pagination } from "@/components/Pagination";

function BerichtArchiefItem({ bericht }: { bericht: BerichtenPaginaOut["items"][number] }) {
  const datum = new Date(bericht.gepubliceerd_op ?? bericht.created).toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <article className="rounded-kaart border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <BerichtBadge type={bericht.type as BerichtType} />
        {bericht.versie && <Tag>{bericht.versie}</Tag>}
        <span className="text-xs text-faint">{datum}</span>
      </div>
      <h4 className="mt-2 text-sm font-semibold text-ink">{bericht.titel}</h4>
      <div className="mt-2 text-sm">
        <Markdown tekst={bericht.inhoud} links="vrij" />
      </div>
    </article>
  );
}

export function BerichtenArchiefClient() {
  const [pagina, setPagina] = useState(1);
  const [data, setData] = useState<BerichtenPaginaOut | null>(null);
  const [laden, setLaden] = useState(true);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    // Bewust synchroon: bij een paginawissel moet de laadindicator meteen aan, vóór de fetch.
    // Dat kost één extra render – de regel waarschuwt daarvoor, hier is het de bedoeling.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLaden(true);
    setFout(null);
    listBerichtenPagina(pagina)
      .then((result) => {
        if (stale) return;
        setData(result);
        if (pagina === 1 && result.items.some((b) => !b.gelezen)) {
          markeerAllesGelezen().catch(() => {});
        }
      })
      .catch((err) => {
        if (!stale) setFout(isApiError(err) ? err.detail : "Kan berichten niet laden.");
      })
      .finally(() => { if (!stale) setLaden(false); });
    return () => { stale = true; };
  }, [pagina]);

  const inhoud = laden ? (
    <div className="space-y-3"><SkeletonCard regels={2} /><SkeletonCard regels={2} /></div>
  ) : fout ? (
    <Melding type="fout">{fout}</Melding>
  ) : !data || data.items.length === 0 ? (
    <p className="text-sm text-muted">Nog geen berichten.</p>
  ) : null;

  return (
    <SettingGroup titel="Berichten" count={data?.totaal} omschrijving="Wat er nieuw is in Lex.">
      {inhoud ?? (
        <div className="space-y-3">
          {data?.items.map((b) => (
            <BerichtArchiefItem key={b.id} bericht={b} />
          ))}
          {data && (
            <Pagination
              page={pagina}
              totalPages={Math.ceil(data.totaal / data.per_pagina)}
              total={data.totaal}
              pageSize={data.per_pagina}
              onPage={(p) => {
                setPagina(p);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            />
          )}
        </div>
      )}
    </SettingGroup>
  );
}
