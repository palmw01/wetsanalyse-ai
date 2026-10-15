"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Popover } from "@/components/ui/Popover";
import { foutTekst, lijstWerkgebieden, neemOpInWerkgebied } from "@/lib/api";
import type { BronRol, WerkgebiedSamenvatting } from "@/lib/types";
import { ROL_LABEL, isAlOpgenomen } from "@/lib/werkgebied";

const CHIP =
  "focus-ring inline-flex min-h-[24px] shrink-0 items-center rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-lint transition-colors hover:bg-surface coarse:min-h-[44px]";

/** *Opnemen in werkgebied* bij een annotatie: kies een werkgebied en een rol, en de bepaling staat
 *  erin. De annotatie zelf verandert niet – een werkgebied verwijst ernaar. */
export function OpnemenInWerkgebied({ bronIri }: { bronIri: string }) {
  return (
    <Popover
      ariaLabel="Opnemen in werkgebied"
      positie="right-0 top-full mt-1"
      className="w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-line bg-paper shadow-lg"
      trigger={(open, toggle) => (
        <button type="button" className={CHIP} aria-expanded={open} onClick={toggle}>
          Opnemen in werkgebied
        </button>
      )}
    >
      <Keuze bronIri={bronIri} />
    </Popover>
  );
}

function Keuze({ bronIri }: { bronIri: string }) {
  const [lijst, setLijst] = useState<WerkgebiedSamenvatting[] | null>(null);
  const [rol, setRol] = useState<BronRol>("analyseren");
  const [bezig, setBezig] = useState<string | null>(null);
  const [uitkomst, setUitkomst] = useState<{ fout: boolean; tekst: string; id?: string } | null>(null);

  useEffect(() => {
    lijstWerkgebieden()
      .then(setLijst)
      .catch((e) => {
        setLijst([]);
        setUitkomst({ fout: true, tekst: foutTekst(e, "De werkgebieden konden niet worden geladen.") });
      });
  }, []);

  async function kies(wg: WerkgebiedSamenvatting) {
    setBezig(wg.id);
    setUitkomst(null);
    try {
      const { nieuw } = await neemOpInWerkgebied(wg.id, { bron_iri: bronIri, rol });
      setUitkomst({ fout: false, id: wg.id, tekst: nieuw ? `Opgenomen in ${wg.naam}.` : `Stond al in ${wg.naam}.` });
    } catch (e) {
      setUitkomst({
        fout: true,
        tekst: isAlOpgenomen(e)
          ? `Staat al in ${wg.naam}, met een andere rol of een ander bereik. Pas dat aan in het werkgebied.`
          : foutTekst(e, "Opnemen is niet gelukt."),
        id: isAlOpgenomen(e) ? wg.id : undefined,
      });
    } finally {
      setBezig(null);
    }
  }

  return (
    <div className="space-y-3 p-3 text-sm">
      <fieldset className="flex gap-3">
        <legend className="sr-only">Rol</legend>
        {(["analyseren", "context"] as BronRol[]).map((r) => (
          <label key={r} className="inline-flex items-center gap-1.5 text-xs text-ink">
            <input type="radio" name="opnemen-rol" checked={rol === r} onChange={() => setRol(r)} className="focus-ring accent-lint" />
            {ROL_LABEL[r]}
          </label>
        ))}
      </fieldset>
      {lijst === null ? (
        <p className="text-xs text-muted">Werkgebieden laden…</p>
      ) : lijst.length === 0 ? (
        <p className="text-xs text-muted">Nog geen werkgebieden.</p>
      ) : (
        <ul className="max-h-60 space-y-1 overflow-y-auto" aria-label="Werkgebieden">
          {lijst.map((wg) => (
            <li key={wg.id}>
              <button
                type="button"
                disabled={!!bezig}
                onClick={() => void kies(wg)}
                className="focus-ring flex min-h-[32px] w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-sm text-ink hover:bg-surface disabled:opacity-50 coarse:min-h-[44px]"
              >
                <span className="truncate">{wg.naam}</span>
                {bezig === wg.id && <span className="shrink-0 text-xs text-muted">Bezig…</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {uitkomst && (
        <p role={uitkomst.fout ? "alert" : "status"} className={`text-xs ${uitkomst.fout ? "text-fout" : "text-ink"}`}>
          {uitkomst.tekst}{" "}
          {uitkomst.id && (
            <Link href={`/werkgebieden/${encodeURIComponent(uitkomst.id)}`} className="focus-ring rounded text-lint underline">
              Naar het werkgebied
            </Link>
          )}
        </p>
      )}
      <Link href="/werkgebieden" className="focus-ring inline-block rounded text-xs text-muted underline hover:text-ink">
        Nieuw werkgebied maken
      </Link>
    </div>
  );
}
