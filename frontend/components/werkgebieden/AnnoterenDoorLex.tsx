"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { AnnoterenBevestiging } from "@/components/werkgebieden/AnnoterenBevestiging";
import { foutTekst, haalAnnotatieWerkvoorraad } from "@/lib/api";
import type { AnnotatieWerkvoorraad } from "@/lib/types";
import { PLAFOND, bepalingen, isWerkvoorraad, standRegel } from "@/lib/werkgebiedAnnoteren";

/** Bovenaan de tab Elementen: hoe ver het annoteren per analysebron is, en *Laat Lex annoteren* voor
 *  wat nog nieuw is (fase B).
 *
 *  Na de bevestiging opent de werkplek in dit werkgebied met een vers gesprek en start daar de run
 *  (`/workbench?werkgebied=<id>&annoteer=<n>`); volgen gebeurt in het gesprek, per bepaling. Lukt het
 *  laden niet, dan zegt het blok dat en blijft de inventaris eronder gewoon werken. */
export function AnnoterenDoorLex({ id }: { id: string }) {
  const router = useRouter();
  const [wv, setWv] = useState<AnnotatieWerkvoorraad | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let levend = true;
    haalAnnotatieWerkvoorraad(id)
      .then((w) => {
        if (!levend) return;
        if (isWerkvoorraad(w)) setWv(w);
        else setFout("De werkvoorraad kon niet worden gelezen.");
      })
      .catch((e) => levend && setFout(foutTekst(e, "De werkvoorraad kon niet worden opgehaald.")));
    return () => { levend = false; };
  }, [id]);

  const nieuw = wv?.te_annoteren.length ?? 0;
  return (
    <section aria-labelledby="annoteren-door-lex" className="rounded-kaart border border-line bg-surface/40 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1.5 text-sm">
          <h3 id="annoteren-door-lex" className="font-medium text-ink">Annoteren door Lex</h3>
          {fout ? (
            <p className="text-muted">{fout}</p>
          ) : !wv ? (
            <Skeleton className="h-4 w-56" />
          ) : wv.selecties.length === 0 ? (
            <p className="text-muted">Geen bronnen om te analyseren; contextbronnen annoteert Lex niet.</p>
          ) : (
            <ul className="space-y-0.5" data-werkvoorraad-nieuw={nieuw}>
              {wv.selecties.map((s) => (
                <li key={s.id} className="text-muted">
                  <span className="text-ink">{s.label || s.bron_iri}</span>
                  {" · "}
                  {s.onbereikbaar ? <span>niet bereikbaar</span> : standRegel(s.per_stand) || "geen bepalingen"}
                </li>
              ))}
            </ul>
          )}
        </div>
        {wv && (
          <Button size="sm" className="w-full shrink-0 sm:w-auto" disabled={!nieuw} onClick={() => setOpen(true)}>
            {nieuw ? `Laat Lex annoteren (${bepalingen(Math.min(nieuw, PLAFOND))})` : "Niets nieuws te annoteren"}
          </Button>
        )}
      </div>
      {open && wv && (
        <AnnoterenBevestiging werkgebiedId={id} werkvoorraad={wv} onSluit={() => setOpen(false)}
          onBevestig={(aantal) => {
            setOpen(false);
            router.push(`/workbench?werkgebied=${encodeURIComponent(id)}&annoteer=${aantal}`);
          }} />
      )}
    </section>
  );
}
