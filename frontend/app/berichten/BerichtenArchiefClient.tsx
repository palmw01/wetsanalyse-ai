"use client";

import { useEffect, useState } from "react";
import { listBerichten, markeerAllesGelezen } from "@/lib/api";
import type { BerichtOut, BerichtType } from "@/lib/types";
import { BerichtBadge } from "@/components/ui/BerichtBadge";
import { Tag } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { Markdown } from "@/components/werkplek/Markdown";

function BerichtArchiefItem({ bericht }: { bericht: BerichtOut }) {
  const datum = new Date(bericht.gepubliceerd_op ?? bericht.created).toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <article className="rounded-button border border-line bg-paper p-5">
      <div className="flex flex-wrap items-center gap-1.5">
        <BerichtBadge type={bericht.type as BerichtType} />
        {bericht.versie && <Tag>{bericht.versie}</Tag>}
        <span className="text-xs text-faint">{datum}</span>
      </div>
      <h2 className="mt-2 text-base font-semibold text-ink">{bericht.titel}</h2>
      <div className="mt-2 text-sm">
        <Markdown tekst={bericht.inhoud} />
      </div>
    </article>
  );
}

export function BerichtenArchiefClient() {
  const [berichten, setBerichten] = useState<BerichtOut[] | null>(null);

  useEffect(() => {
    listBerichten()
      .then((items) => {
        setBerichten(items);
        if (items.some((b) => !b.gelezen)) {
          void markeerAllesGelezen().catch(() => {});
        }
      })
      .catch(() => setBerichten([]));
  }, []);

  if (berichten === null) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-button border border-line bg-paper p-5 space-y-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-3 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (berichten.length === 0) {
    return <p className="text-sm text-muted">Nog geen berichten.</p>;
  }

  return (
    <div className="space-y-4">
      {berichten.map((b) => (
        <BerichtArchiefItem key={b.id} bericht={b} />
      ))}
    </div>
  );
}
