"use client";

import { useEffect, useRef, useState } from "react";

import { foutTekst, haalArtefactVersie, haalArtefactVersies } from "@/lib/api";
import { beginPlek, isNu, plekLabel, versieTijd } from "@/lib/artefactVersie";
import type { ArtefactVersie } from "@/lib/types";

/** De versiekiezer van een artefact, in het slot `onder` van `PaneelKop` (deel 2 van de artefacten, naar het voorbeeld
 *  van Claude): ‹ *Versie n van m* › en daarachter *Nu*. Een versie is de stand direct na een beurt van Lex (api
 *  `artefact_versies`); een oudere is alleen te lezen, met eronder "Je bekijkt de versie van … · *Ga naar de huidige
 *  versie*". De chip opent zijn eigen versie; de nieuwste opent als *Nu* (`beginPlek`), met erbij wanneer Lex die maakte:
 *  ‹ is de weg erheen.
 *
 *  `onKies` krijgt de versie die het paneel moet tonen, of `null` voor *Nu* (de live stand, met alle knoppen). Het
 *  paneel toont niets zolang de kiezer nog niet heeft gekozen: anders staan er even knoppen op iets wat een oude
 *  versie blijkt. Kan de versie niet worden gelezen (verwijderd, storing), dan zegt hij dat en kiest hij *Nu*. */
export function VersieKiezer({ versie, gekozen, onKies }: {
  /** De versie van de chip (`artefact.ref.versie`). */
  versie: string;
  /** Wat het paneel al koos (een id, of `null` voor *Nu*); de kiezer begint daar en meldt niets. Nodig waar hij opnieuw
   *  gemonteerd wordt binnen hetzelfde paneel (de tab Tekst en de tab Graaf hebben elk een kop); anders sprong hij
   *  terug naar de versie van de chip. */
  gekozen?: string | null;
  onKies: (v: ArtefactVersie | null) => void;
}) {
  const [ids, setIds] = useState<string[] | null>(null);
  const [plek, setPlek] = useState(0);
  const [getoond, setGetoond] = useState<ArtefactVersie | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  // Wanneer Lex de nieuwste versie maakte: bij *Nu* de wijzer naar wat de laatste beurt opleverde.
  const [laatste, setLaatste] = useState("");
  const cache = useRef(new Map<string, ArtefactVersie>());
  // De handler van de laatste render, zonder het laden opnieuw te starten als het paneel een nieuwe functie meegeeft.
  const kies = useRef(onKies);
  useEffect(() => { kies.current = onKies; }, [onKies]);
  const start = useRef(gekozen);

  useEffect(() => {
    let levend = true;
    (async () => {
      try {
        const v = await haalArtefactVersie(versie);
        cache.current.set(v.id, v);
        const versies = await haalArtefactVersies(v.sleutel);
        const lijst = versies.map((x) => x.id);
        const alle = lijst.includes(v.id) ? lijst : [...lijst, v.id];
        setLaatste(versieTijd(versies.at(-1)?.gemaakt ?? v.gemaakt));
        if (start.current !== undefined) {
          // Al gekozen: alleen de plek en de regel terugzetten.
          const i = start.current === null ? alle.length : alle.indexOf(start.current);
          const p = i === -1 ? alle.length : i;
          const nu = isNu(p, alle.length);
          const getoonde = nu ? null : await haalArtefactVersie(alle[p]);
          if (!levend) return;
          setIds(alle); setPlek(p); setGetoond(getoonde);
          return;
        }
        if (!levend) return;
        const p = beginPlek(alle, v.id);
        setIds(alle);
        setPlek(p);
        setGetoond(isNu(p, alle.length) ? null : v);
        kies.current(isNu(p, alle.length) ? null : v);
      } catch (e) {
        if (!levend) return;
        setFout(`${foutTekst(e, "Deze versie kon niet worden gelezen.")} Je ziet de huidige stand.`);
        kies.current(null);
      }
    })();
    return () => { levend = false; };
  }, [versie]);

  async function ga(naar: number) {
    if (!ids) return;
    setFout(null);
    if (isNu(naar, ids.length)) {
      setPlek(naar); setGetoond(null); kies.current(null);
      return;
    }
    const id = ids[naar];
    try {
      const v = cache.current.get(id) ?? await haalArtefactVersie(id);
      cache.current.set(id, v);
      setPlek(naar); setGetoond(v); kies.current(v);
    } catch (e) {
      setFout(foutTekst(e, "Deze versie kon niet worden gelezen."));
    }
  }

  if (!ids) return fout ? <p className="border-b border-line bg-surface/60 px-5 py-1.5 text-xs text-muted" data-versie-fout>{fout}</p> : null;
  const knop = "focus-ring rounded-knop-xs px-2 py-1 text-xs font-medium text-lint hover:bg-lint/5 disabled:cursor-default disabled:text-faint disabled:hover:bg-transparent";
  const nu = isNu(plek, ids.length);
  return (
    <div data-versiekiezer data-versie-plek={nu ? "nu" : plek + 1} className="shrink-0">
      <nav aria-label="Versies" className="flex items-center gap-2 border-b border-line bg-surface/60 px-4 py-1.5">
        <button type="button" className={knop} disabled={plek === 0} onClick={() => void ga(plek - 1)}
          aria-label="Vorige versie" title="Vorige versie">‹</button>
        <span className="min-w-0 flex-1 truncate text-center text-xs text-muted" aria-live="polite">
          <span className="text-ink">{plekLabel(plek, ids.length)}</span>
          {nu && laatste && <span data-laatste-versie> · laatste versie van Lex: {laatste}</span>}
        </span>
        <button type="button" className={knop} disabled={nu} onClick={() => void ga(plek + 1)}
          aria-label={plek === ids.length - 1 ? "Naar de huidige versie" : "Volgende versie"} title="Volgende versie">›</button>
      </nav>
      {!nu && getoond && (
        <p className="border-b border-line bg-aandacht-geel-bg/40 px-5 py-1.5 text-xs text-ink" data-oude-versie>
          Je bekijkt de versie van {versieTijd(getoond.gemaakt) || "een eerdere beurt"}; alleen lezen.{" "}
          <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => void ga(ids.length)}>
            Ga naar de huidige versie
          </button>
        </p>
      )}
      {fout && <p className="border-b border-line px-5 py-1.5 text-xs text-fout" role="alert">{fout}</p>}
    </div>
  );
}
