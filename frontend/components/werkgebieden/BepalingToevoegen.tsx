"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Select, Textarea, inputBase } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Dialog } from "@/components/ui/Dialog";
import { SluitKnop } from "@/components/ui/PaneelKop";
import { KnoopTekst } from "@/components/graaf/KnoopTekst";
import {
  foutTekst, haalWerkgebied, voegBepalingToeBijDeelvraag, voegBronToe, zoekBepalingen, zoekRegelingen,
} from "@/lib/api";
import { haalNodeWeergave, type NodeWeergave } from "@/lib/annotatieNode";
import {
  HEEL_WERKGEBIED, MAX_REDEN, geenTrefferZin, invoerVoor, toegevoegdZin, toevoegFout, type ToevoegFout,
} from "@/lib/bepalingToevoegen";
import type { BepalingTreffer, BepalingZoekAntwoord, BronRol, RegelingTreffer, Werkgebied } from "@/lib/types";
import { ROL_LABEL, ROL_UITLEG } from "@/lib/werkgebied";

const WACHT_MS = 250;
const ROLLEN: BronRol[] = ["analyseren", "context"];

/** *Bepaling toevoegen* (3 nov 2026): één onderdeel voor de tab Bronnen, het paneel naast het gesprek en het
 *  kaartje van de bronselectie. Eerst een regeling (die van het werkgebied vooraan), dan een vindplaats zoals de
 *  jurist hem typt – "9 lid 2", "21.1", "25.4 onderdeel b" – met live treffers uit de echte boom en de wettekst
 *  van de gekozen bepaling eronder. Dan de deelvraag (of het hele werkgebied), de rol en een optionele reden.
 *
 *  *Toevoegen* staat uit tot er een treffer gekozen is: er gaat nooit vrije tekst naar de api die hij moet
 *  raden. Elke fout staat bij het formulier (`toevoegFout`): niet gevonden met wat er gelezen is, een keuze uit de
 *  opties van de graaf, al opgenomen, uitgesloten, de graaf weg; een 412 haalt de revisie opnieuw en probeert één
 *  keer opnieuw – de bedoeling hangt niet af van de rest van het werkgebied. */
export function BepalingToevoegen({ werkgebiedId, deelvraagId, onKlaar, onSluit }: {
  werkgebiedId: string;
  /** De deelvraag waar de jurist staat; leeg = het hele werkgebied. */
  deelvraagId?: string;
  /** Na toevoegen, met de zin die zegt wat er gebeurde. */
  onKlaar: (zin: string) => void;
  onSluit: () => void;
}) {
  const [wg, setWg] = useState<Werkgebied | null>(null);
  const [regeling, setRegeling] = useState<RegelingTreffer | null>(null);
  const [keuze, setKeuze] = useState<BepalingTreffer | null>(null);
  const [deelvraag, setDeelvraag] = useState(deelvraagId ?? HEEL_WERKGEBIED);
  const [rol, setRol] = useState<BronRol>("analyseren");
  const [reden, setReden] = useState("");
  const [fout, setFout] = useState<ToevoegFout | null>(null);
  const [bezig, setBezig] = useState(false);

  useEffect(() => {
    let levend = true;
    haalWerkgebied(werkgebiedId).then((w) => { if (levend) setWg(w); }).catch(() => {});
    return () => { levend = false; };
  }, [werkgebiedId]);

  const actief = (wg?.deelvragen ?? []).filter((d) => d.status === "actief");
  const nrVan = (id: string) => (actief.findIndex((d) => d.id === id) + 1) || null;

  async function voegToe(e: React.FormEvent) {
    e.preventDefault();
    if (!keuze || bezig) return;
    setBezig(true);
    setFout(null);
    const poging = async (revisie: number) => {
      const invoer = invoerVoor(keuze, rol, reden, revisie);
      if (deelvraag) {
        await voegBepalingToeBijDeelvraag(werkgebiedId, deelvraag, invoer);
        return toegevoegdZin(keuze, nrVan(deelvraag));
      }
      const uit = await voegBronToe(werkgebiedId, invoer);
      return uit.nieuw ? toegevoegdZin(keuze, null) : `${keuze.vindplaats} stond er al in, met dezelfde rol.`;
    };
    try {
      const revisie = wg?.revisie ?? (await haalWerkgebied(werkgebiedId)).revisie;
      let zin: string;
      try {
        zin = await poging(revisie);
      } catch (err) {
        if (toevoegFout(err).soort !== "conflict") throw err;
        const vers = await haalWerkgebied(werkgebiedId);
        setWg(vers);
        zin = await poging(vers.revisie);
      }
      onKlaar(zin);
    } catch (err) {
      setFout(toevoegFout(err));
    } finally {
      setBezig(false);
    }
  }

  return (
    <Dialog label="Bepaling toevoegen" variant="compact" onSluit={onSluit}>
      <form onSubmit={voegToe} className="flex min-h-0 flex-1 flex-col" data-bepaling-toevoegen>
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <h2 className="font-display text-base font-semibold text-lint">Bepaling toevoegen</h2>
            <p className="mt-0.5 text-xs text-muted">Kies een regeling en typ de vindplaats; je kiest uit wat de kennisgraaf kent.</p>
          </div>
          <SluitKnop onSluit={onSluit} />
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <RegelingVeld werkgebiedId={werkgebiedId} gekozen={regeling}
            onKies={(r) => { setRegeling(r); setKeuze(null); setFout(null); }} />
          <VindplaatsVeld key={regeling?.bwb_id ?? ""} werkgebiedId={werkgebiedId} regeling={regeling} gekozen={keuze}
            onKies={(t) => { setKeuze(t); setFout(null); }} />
          {keuze && <Voorbeeld key={keuze.bron_iri} treffer={keuze} />}
          {actief.length > 0 && (
            <Field label="Koppel aan deelvraag">
              <Select value={deelvraag} onChange={(e) => setDeelvraag(e.target.value)} data-deelvraag-keuze>
                {actief.map((d, i) => (
                  <option key={d.id} value={d.id}>Deelvraag {i + 1} – {d.vraag}</option>
                ))}
                <option value={HEEL_WERKGEBIED}>Geen deelvraag – alleen opnemen in het werkgebied</option>
              </Select>
            </Field>
          )}
          <fieldset>
            <legend className="mb-1 text-sm font-medium text-ink">Rol</legend>
            <div className="space-y-1.5">
              {ROLLEN.map((r) => (
                <label key={r} className="flex items-start gap-2 text-sm text-ink">
                  <input type="radio" name="rol" value={r} checked={rol === r} onChange={() => setRol(r)}
                    className="focus-ring mt-1 accent-lint" />
                  <span>{ROL_LABEL[r]} <span className="text-xs text-muted">– {ROL_UITLEG[r]}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
          <Field label="Reden van opname" hint={`optioneel · ${reden.length} / ${MAX_REDEN}`}>
            <Textarea value={reden} onChange={(e) => setReden(e.target.value)} rows={2} maxLength={MAX_REDEN} />
          </Field>
          {fout && (
            <Melding type={fout.soort === "graaf" || fout.soort === "conflict" ? "waarschuwing" : "fout"} compact>
              <span data-toevoeg-fout={fout.soort}>{fout.tekst}</span>
              {fout.soort === "keuze" && fout.opties.length > 0 && (
                <span className="mt-2 flex flex-wrap gap-1.5">
                  {fout.opties.map((o) => (
                    <button key={o.bron_iri} type="button" className="focus-ring rounded-full border border-line px-2.5 py-0.5 text-xs text-lint hover:bg-surface"
                      onClick={() => { setKeuze({ bron_iri: o.bron_iri, soort: "deel", vindplaats: o.label, titel: "", fragment: o.fragment ?? "" }); setFout(null); }}>
                      {o.label}
                    </button>
                  ))}
                </span>
              )}
            </Melding>
          )}
        </div>
        <div className="flex flex-col-reverse gap-2 border-t border-line px-5 py-3 sm:flex-row sm:items-center sm:justify-end">
          <Button type="button" variant="ghost" size="sm" onClick={onSluit} className="w-full sm:w-auto">Annuleren</Button>
          <Button type="submit" size="sm" disabled={!keuze || bezig} className="w-full sm:w-auto">
            {bezig ? "Toevoegen…" : "Toevoegen"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Een combobox: een veld met een lijst eronder, met de pijltjes en Enter te bedienen (`aria-activedescendant`).
 *  Een klik of Enter kiest; Escape sluit eerst de lijst. */
function Keuzeveld<T>({ label, placeholder, waarde, onWaarde, opties, sleutel, render, onKies, uit = false, bezig = false,
  leeg, hint, data }: {
  label: string;
  placeholder: string;
  waarde: string;
  onWaarde: (v: string) => void;
  opties: T[];
  sleutel: (o: T) => string;
  render: (o: T) => React.ReactNode;
  onKies: (o: T) => void;
  uit?: boolean;
  bezig?: boolean;
  /** Wat er onder het veld staat als de lijst leeg is (en er gezocht is). */
  leeg?: React.ReactNode;
  hint?: string;
  data?: string;
}) {
  const lijstId = useId();
  const [open, setOpen] = useState(false);
  const [actief, setActief] = useState(0);
  const sluit = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toon = open && opties.length > 0;
  const kies = (o: T) => { onKies(o); setOpen(false); };
  return (
    <div className="relative" data-keuzeveld={data}>
      <Field label={label} hint={hint}>
        <input role="combobox" aria-expanded={toon} aria-controls={lijstId} aria-autocomplete="list"
          aria-activedescendant={toon && opties[actief] ? `${lijstId}-${actief}` : undefined}
          disabled={uit} placeholder={placeholder} value={waarde} className={inputBase}
          onChange={(e) => { onWaarde(e.target.value); setActief(0); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => { sluit.current = setTimeout(() => setOpen(false), 120); }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActief((i) => Math.min(i + 1, opties.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setActief((i) => Math.max(i - 1, 0)); }
            else if (e.key === "Enter" && toon && opties[actief]) { e.preventDefault(); kies(opties[actief]); }
            else if (e.key === "Escape" && toon) { e.stopPropagation(); setOpen(false); }
          }} />
      </Field>
      {bezig && <span className="pointer-events-none absolute right-3 top-9 text-xs text-faint" aria-live="polite">Zoekt in de kennisgraaf…</span>}
      {toon && (
        <ul id={lijstId} role="listbox" aria-label={label}
          className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-kaart border border-line bg-paper p-1 shadow-kaart">
          {opties.map((o, i) => (
            <li key={sleutel(o)} id={`${lijstId}-${i}`} role="option" aria-selected={i === actief}
              onMouseDown={(e) => e.preventDefault()} onClick={() => kies(o)} onMouseEnter={() => setActief(i)}
              className={`cursor-pointer rounded-lg px-2.5 py-2 text-sm coarse:min-h-11 ${i === actief ? "bg-lint/10" : ""}`}>
              {render(o)}
            </li>
          ))}
        </ul>
      )}
      {!toon && leeg}
    </div>
  );
}

/** Een effect dat pas na `WACHT_MS` stilte zoekt, en een oude zoekvraag afbreekt. */
function useZoek<T>(zoek: ((signal: AbortSignal) => Promise<T>) | null, sleutel: string) {
  const [uitkomst, setUitkomst] = useState<{ sleutel: string; waarde: T } | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const ref = useRef(zoek);
  useEffect(() => { ref.current = zoek; });
  useEffect(() => {
    if (!ref.current) return;
    const ctl = new AbortController();
    setBezig(true);
    const t = setTimeout(() => {
      ref.current?.(ctl.signal)
        .then((w) => { setUitkomst({ sleutel, waarde: w }); setFout(null); })
        .catch((e) => { if (!ctl.signal.aborted) setFout(foutTekst(e, "Zoeken lukte niet.")); })
        .finally(() => { if (!ctl.signal.aborted) setBezig(false); });
    }, WACHT_MS);
    return () => { ctl.abort(); clearTimeout(t); };
  }, [sleutel]);
  return { uitkomst, fout, bezig };
}

function RegelingVeld({ werkgebiedId, gekozen, onKies }: {
  werkgebiedId: string;
  gekozen: RegelingTreffer | null;
  onKies: (r: RegelingTreffer) => void;
}) {
  const [q, setQ] = useState("");
  const { uitkomst, fout, bezig } = useZoek((signal) => zoekRegelingen(werkgebiedId, q, signal), `${werkgebiedId}|${q}`);
  const opties = useMemo(() => uitkomst?.waarde ?? [], [uitkomst]);
  // Eén regeling in het werkgebied: die staat vast klaar.
  const eerste = useRef(false);
  useEffect(() => {
    if (!eerste.current && !gekozen && !q && opties.length === 1) {
      eerste.current = true;
      onKies(opties[0]);
      setQ(opties[0].citeertitel);
    }
  }, [opties, gekozen, q, onKies]);
  return (
    <Keuzeveld label="Regeling" placeholder="Zoek op naam, afkorting of BWB-id" data="regeling"
      waarde={q} onWaarde={setQ} opties={opties} sleutel={(r) => r.bwb_id} bezig={bezig && !uitkomst}
      onKies={(r) => { onKies(r); setQ(r.citeertitel); }}
      hint={gekozen ? gekozen.bwb_id : undefined}
      render={(r) => <><span className="font-medium text-ink">{r.citeertitel || r.bwb_id}</span>
        <span className="ml-2 text-xs text-muted">{[r.soort, r.bwb_id].filter(Boolean).join(" · ")}</span></>}
      leeg={fout ? <p className="mt-1 text-xs text-fout">{fout}</p>
        : q && uitkomst && !opties.length ? <p className="mt-1 text-xs text-muted">Geen regeling met “{q}” in de kennisgraaf.</p> : null} />
  );
}

function VindplaatsVeld({ werkgebiedId, regeling, gekozen, onKies }: {
  werkgebiedId: string;
  regeling: RegelingTreffer | null;
  gekozen: BepalingTreffer | null;
  onKies: (t: BepalingTreffer) => void;
}) {
  const [q, setQ] = useState("");
  const zoek = regeling && q.trim() && q !== gekozen?.vindplaats
    ? (signal: AbortSignal) => zoekBepalingen(werkgebiedId, regeling.bwb_id, q, signal) : null;
  const { uitkomst, fout, bezig } = useZoek<BepalingZoekAntwoord>(zoek, zoek ? `${regeling?.bwb_id}|${q}` : "");
  const actueel = uitkomst && uitkomst.sleutel === `${regeling?.bwb_id}|${q}` ? uitkomst.waarde : null;
  const opties = actueel?.treffers ?? [];
  return (
    <Keuzeveld label="Vindplaats" placeholder={regeling ? "Bijvoorbeeld 9 lid 2, 21.1 of 25.4 onderdeel b" : "Kies eerst een regeling"}
      data="vindplaats" uit={!regeling} waarde={q} onWaarde={setQ} opties={opties} sleutel={(t) => t.bron_iri}
      bezig={!!zoek && bezig} onKies={(t) => { onKies(t); setQ(t.vindplaats); }}
      hint="artikel, lid, onderdeel of divisie"
      render={(t) => <>
        <span className="block font-medium text-ink">{t.vindplaats}{t.titel && <span className="font-normal text-muted"> – {t.titel}</span>}</span>
        {t.fragment && <span className="block truncate text-xs text-muted">{t.fragment}</span>}
      </>}
      leeg={fout ? <p className="mt-1 text-xs text-fout" data-vindplaats-fout>{fout}</p>
        : zoek && actueel && !opties.length && regeling
          ? <p className="mt-1 text-xs text-fout" data-vindplaats-leeg>{geenTrefferZin(regeling.citeertitel || regeling.bwb_id, actueel.gelezen)}</p>
          : null} />
  );
}

/** De wettekst van de gekozen bepaling, zodat de jurist ziet wat hij toevoegt. */
function Voorbeeld({ treffer }: { treffer: BepalingTreffer }) {
  const [view, setView] = useState<NodeWeergave | null>(null);
  const [mis, setMis] = useState(false);
  useEffect(() => {
    let levend = true;
    haalNodeWeergave({ bron_iri: treffer.bron_iri }).then((v) => { if (levend) setView(v); })
      .catch(() => { if (levend) setMis(true); });
    return () => { levend = false; };
  }, [treffer.bron_iri]);
  return (
    <section className="rounded-kaart border border-line bg-surface/60 px-3 py-2.5" data-bepaling-voorbeeld={treffer.bron_iri}>
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-faint">{treffer.vindplaats}</h3>
      {view ? <KnoopTekst segmenten={view.segmenten} elementen={[]} kiesbaar={() => false} onKies={() => {}} />
        : <p className="text-sm text-muted">{mis ? treffer.fragment || "De tekst is nu niet te laden." : "Tekst laden…"}</p>}
    </section>
  );
}
