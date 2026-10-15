"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { haalWerkgebied } from "@/lib/api";

/** De balk boven de chat als de werkplek in de context van een werkgebied staat (`?werkgebied=`).
 *
 *  Hij noemt het werkgebied (PLAN §GUI: je moet zien in welke analyse je werkt), biedt *Zoek
 *  bepalingen* en *Stel begrippen voor* – gewone beurten, die graph-qa naar de bronnen- of
 *  begrippenroute stuurt – en laat je uit de context stappen. De naam laden mag mislukken: dan staat er "Werkgebied" en werkt de rest gewoon. */
export function WerkgebiedBalk({ id, uitgeschakeld, onBronnen, onBegrippen, onVerlaat }: {
  id: string;
  uitgeschakeld: boolean;
  onBronnen: () => void;
  onBegrippen: () => void;
  onVerlaat: () => void;
}) {
  const [naam, setNaam] = useState<string | null>(null);
  useEffect(() => {
    let levend = true;
    haalWerkgebied(id).then((w) => levend && setNaam(w.naam)).catch(() => levend && setNaam(""));
    return () => { levend = false; };
  }, [id]);

  return (
    <div data-werkgebied={id}
      className="flex shrink-0 flex-col gap-2 border-b border-line bg-lint/5 px-4 py-2 text-xs sm:flex-row sm:items-center">
      <p className="min-w-0 flex-1 truncate text-muted">
        Werkgebied{" "}
        <Link href={`/werkgebieden/${encodeURIComponent(id)}`} className="focus-ring font-medium text-lint underline-offset-2 hover:underline">
          {naam || (naam === null ? "…" : id)}
        </Link>
        {" "}· Lex werkt binnen deze analyse
      </p>
      <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
        <Button size="sm" variant="secondary" className="w-full sm:w-auto" disabled={uitgeschakeld} onClick={onBronnen}>
          Zoek bepalingen
        </Button>
        <Button size="sm" className="w-full sm:w-auto" disabled={uitgeschakeld} onClick={onBegrippen}>
          Stel begrippen voor
        </Button>
        <Button size="sm" variant="secondary" className="w-full sm:w-auto" onClick={onVerlaat}
          aria-label="Uit de context van dit werkgebied stappen">
          Verlaten
        </Button>
      </div>
    </div>
  );
}
