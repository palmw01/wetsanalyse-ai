"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { Field, Select } from "@/components/ui/Field";
import { LaadRegel } from "@/components/ui/LaadStand";
import { Lijst, LijstRij, StatusLabel, Voorstel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart } from "@/components/ui/Pagina";
import { Uitklap } from "@/components/ui/Uitklap";
import { besluitOpenPunt, foutTekst, haalRegel, lijstOpenPunten, maakOpenPunt, omhangOpenPunt } from "@/lib/api";
import { aantal } from "@/lib/aantal";
import {
  BRONSOORT_LABEL, METHODE_LABEL, OPEN_PUNT_STATUS_LABEL, SOORT_KEUZES, aanhaking, besluitFout, blokkeert, keuzeZin,
  nieuwePuntInhoud, nieuwFout, ordenPunten, soortLabel,
  type BesluitInvoer, type Grondslag, type Methode, type OpenPunt, type OpenPuntNieuw,
} from "@/lib/openPunten";
import { gevalLabels, type Regel } from "@/lib/regels";
import { isRevisieConflict } from "@/lib/werkgebied";
import { begripPad, bronPad, elementPad } from "@/lib/werkgebiedPaden";

/** De open punten van één regel en zijn gevallen (R3, ADR-018 besluit 7.13): wat de tekst open laat, met de lezingen,
 *  hun grondslag, wat nog getoetst moet worden en de keuze. **Het besluit valt hier, op het artefact**, via de ene route
 *  van het open punt (`besluitOpenPunt`, met het userid; het agent-token mag die route niet). De keuzekaart die Lex later
 *  in het gesprek legt (R6), schrijft naar dezelfde route. Een punt dat Lex voorlegde en nog open is, staat als
 *  `Voorstel`. */
export function OpenPunten({ werkgebiedId, regelId, revisie, alleenLezen, onBesluit, gevallen = [], regels = [], opvolger }: {
  werkgebiedId: string;
  regelId: string;
  /** De revisie van de regel: verandert hij, dan laden de punten opnieuw. */
  revisie: number;
  alleenLezen: boolean;
  /** Na een besluit: de regel opnieuw laden, want de poort telt de genomen keuzes. */
  onBesluit: () => void;
  /** De labels van de gevallen van deze regel, om een nieuw punt aan een geval te hangen. */
  gevallen?: string[];
  /** De regels van het werkgebied (de keten), om een punt om te hangen. */
  regels?: { id: string; naam: string }[];
  /** De regel die deze verving: het voor de hand liggende doel van omhangen. */
  opvolger?: string | null;
}) {
  const [punten, setPunten] = useState<OpenPunt[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [lading, setLading] = useState(0);
  const laad = useCallback(() => setLading((n) => n + 1), []);

  useEffect(() => {
    let levend = true;
    lijstOpenPunten(werkgebiedId, { soort: "regel", id: regelId })
      .then((p) => { if (levend) { setPunten(p); setFout(null); } })
      .catch((e) => levend && setFout(foutTekst(e, "De open punten konden niet worden geladen.")));
    return () => { levend = false; };
  }, [werkgebiedId, regelId, revisie, lading]);

  if (fout) return <Melding type="waarschuwing">{fout}</Melding>;
  if (!punten) return <Kaart titel="Open punten"><LaadRegel klein /></Kaart>;
  if (!punten.length && alleenLezen) return null;

  const open = punten.filter(blokkeert).length;
  const gewijzigd = () => { laad(); onBesluit(); };
  return (
    <Kaart titel="Open punten" telling={punten.length} data-open-punten
      toelichting={open
        ? `${aantal(open, "keuze houdt", "keuzes houden")} het accorderen tegen tot je besluit.`
        : "Wat de tekst open laat, met de lezingen en de keuze."}>
      {punten.length > 0 && (
        <Lijst label="Open punten">
          {ordenPunten(punten).map((p) => (
            <PuntRij key={p.id} punt={p} werkgebiedId={werkgebiedId} alleenLezen={alleenLezen} onGewijzigd={gewijzigd}
              regels={regels} opvolger={opvolger} />
          ))}
        </Lijst>
      )}
      {!alleenLezen && <NieuwPunt werkgebiedId={werkgebiedId} regelId={regelId} gevallen={gevallen} onGemaakt={gewijzigd} />}
    </Kaart>
  );
}

const LEEG_NIEUW: OpenPuntNieuw = { soort: "interpretatiekeuze", vraag: "", toelichting: "", geval: "", lezingen: ["", ""] };

/** Een open punt vastleggen op de regel of een geval: de vraag, en bij een interpretatiekeuze de lezingen. De keuze zelf
 *  valt daarna, met het besluit. */
function NieuwPunt({ werkgebiedId, regelId, gevallen, onGemaakt }: {
  werkgebiedId: string; regelId: string; gevallen: string[]; onGemaakt: () => void;
}) {
  const [n, setN] = useState<OpenPuntNieuw>(LEEG_NIEUW);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const [open, setOpen] = useState(false);
  const zet = (nieuw: Partial<OpenPuntNieuw>) => { setN({ ...n, ...nieuw }); setFout(null); };
  const leg = async () => {
    const probleem = nieuwFout(n);
    if (probleem) { setFout(probleem); return; }
    setBezig(true);
    try {
      await maakOpenPunt(werkgebiedId, nieuwePuntInhoud(regelId, n));
      setN(LEEG_NIEUW);
      setOpen(false);
      onGemaakt();
    } catch (e) {
      setFout(foutTekst(e, "Het open punt is niet vastgelegd."));
    } finally {
      setBezig(false);
    }
  };
  if (!open) {
    return (
      <ButtonRow className="mt-3">
        <Button size="sm" variant="secondary" onClick={() => setOpen(true)} data-open-punt-nieuw>Open punt toevoegen</Button>
      </ButtonRow>
    );
  }
  const keuze = n.soort === "interpretatiekeuze";
  return (
    <fieldset className="mt-3 space-y-3 border-t border-line pt-3" data-open-punt-formulier>
      <legend className="text-sm font-medium text-ink">Nieuw open punt</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Soort">
          <Select value={n.soort} onChange={(e) => zet({ soort: e.target.value as OpenPuntNieuw["soort"] })}>
            {SOORT_KEUZES.map((s) => <option key={s.waarde} value={s.waarde}>{s.label}</option>)}
          </Select>
        </Field>
        <Field label="Waar het aan hangt">
          <Select value={n.geval} onChange={(e) => zet({ geval: e.target.value })}>
            <option value="">De hele regel</option>
            {gevallen.map((g) => <option key={g} value={g}>Geval {g}</option>)}
          </Select>
        </Field>
      </div>
      <Field label="Wat is er open?">
        <AutoTextarea rows={2} className="w-full" value={n.vraag} onChange={(e) => zet({ vraag: e.target.value })}
          data-open-punt-vraag />
      </Field>
      {keuze && n.lezingen.map((l, i) => (
        <Field key={i} label={`Lezing ${String.fromCharCode(65 + i)}`}>
          <AutoTextarea rows={2} className="w-full" value={l} data-open-punt-lezing={i}
            onChange={(e) => zet({ lezingen: n.lezingen.map((x, j) => (j === i ? e.target.value : x)) })} />
        </Field>
      ))}
      {keuze && n.lezingen.length < 10 && (
        <Button size="xs" variant="ghost" onClick={() => zet({ lezingen: [...n.lezingen, ""] })}>Lezing toevoegen</Button>
      )}
      <Field label="Toelichting" hint="optioneel">
        <AutoTextarea rows={2} className="w-full" value={n.toelichting} onChange={(e) => zet({ toelichting: e.target.value })} />
      </Field>
      {fout && <Melding type="waarschuwing" compact>{fout}</Melding>}
      <ButtonRow>
        <Button size="sm" disabled={bezig} onClick={() => void leg()} data-open-punt-vastleggen>Vastleggen</Button>
        <Button size="sm" variant="ghost" onClick={() => { setOpen(false); setN(LEEG_NIEUW); setFout(null); }}>Annuleren</Button>
      </ButtonRow>
    </fieldset>
  );
}

/** Een punt aan een andere regel of een ander geval hangen, en verder niets: na een vervanging naar de opvolger. */
function Omhangen({ punt: p, werkgebiedId, regels, opvolger, onGewijzigd }: {
  punt: OpenPunt; werkgebiedId: string; regels: { id: string; naam: string }[]; opvolger?: string | null;
  onGewijzigd: () => void;
}) {
  const huidig = p.inhoud.hangt_aan.find((a) => a.soort === "regel" || a.soort === "geval");
  const [doel, setDoel] = useState(opvolger || huidig?.id || "");
  const [geval, setGeval] = useState("");
  const [labels, setLabels] = useState<string[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  // De gevallen van het doel pas bij openklappen: elke rij heeft dit formulier, en dicht kost het niets.
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let levend = true;
    if (!open || !doel) return;
    haalRegel(werkgebiedId, doel).then((r: Regel) => levend && setLabels(gevalLabels(r)))
      .catch(() => levend && setLabels([]));
    return () => { levend = false; };
  }, [werkgebiedId, doel, open]);
  const hang = async () => {
    setBezig(true);
    setFout(null);
    try {
      // Alleen de aanhaking op een regel verandert; wat het punt verder aan markeringen of begrippen hangt, blijft.
      const rest = p.inhoud.hangt_aan.filter((a) => a.soort !== "regel" && a.soort !== "geval");
      await omhangOpenPunt(werkgebiedId, p.id, p.revisie, [...aanhaking(doel, geval), ...rest]);
      onGewijzigd();
    } catch (e) {
      setFout(foutTekst(e, "Omhangen is niet gelukt."));
      if (isRevisieConflict(e)) onGewijzigd();
    } finally {
      setBezig(false);
    }
  };
  return (
    <Uitklap samenvatting="Omhangen" className="mt-1" data-omhangen={p.id}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <Select aria-label="Naar regel" value={doel}
          onChange={(e) => { setDoel(e.target.value); setLabels(null); setGeval(""); }}>
          {regels.map((r) => <option key={r.id} value={r.id}>{r.naam || r.id}{r.id === opvolger ? " (opvolger)" : ""}</option>)}
        </Select>
        <Select aria-label="Naar geval" value={geval} disabled={!labels} onChange={(e) => setGeval(e.target.value)}>
          <option value="">De hele regel</option>
          {(labels ?? []).map((g) => <option key={g} value={g}>Geval {g}</option>)}
        </Select>
      </div>
      {fout && <Melding type="waarschuwing" compact className="mt-2">{fout}</Melding>}
      <ButtonRow className="mt-2">
        <Button size="xs" variant="secondary" disabled={bezig || !doel || !labels} onClick={() => void hang()}
          data-omhangen-vastleggen>Omhangen</Button>
      </ButtonRow>
    </Uitklap>
  );
}

function PuntRij({ punt: p, werkgebiedId, alleenLezen, onGewijzigd, regels, opvolger }: {
  punt: OpenPunt;
  werkgebiedId: string;
  alleenLezen: boolean;
  onGewijzigd: () => void;
  regels: { id: string; naam: string }[];
  opvolger?: string | null;
}) {
  const gevallen = p.inhoud.hangt_aan.filter((a) => a.soort === "geval").map((a) => a.geval);
  const kop = (
    <span className="flex flex-wrap items-center gap-1.5">
      <StatusLabel klein toon={blokkeert(p) ? "geel" : "neutraal"}>{soortLabel(p)}</StatusLabel>
      {gevallen.length > 0 && <span className="text-xs text-muted">geval {gevallen.join(", ")}</span>}
    </span>
  );
  const inhoud = <>
    <PuntInhoud punt={p} werkgebiedId={werkgebiedId} alleenLezen={alleenLezen} onGewijzigd={onGewijzigd} />
    {!alleenLezen && regels.length > 0 && (
      <Omhangen punt={p} werkgebiedId={werkgebiedId} regels={regels} opvolger={opvolger} onGewijzigd={onGewijzigd} />
    )}
  </>;
  // Een voorstel van Lex dat nog open is, staat geel; wat de jurist vastlegde of besloot niet.
  if (p.herkomst === "lex" && p.status === "open") {
    return <Voorstel data-open-punt={p.id} data-status={p.status} titel={<>{kop}<p className="mt-1">{p.inhoud.vraag}</p></>}>{inhoud}</Voorstel>;
  }
  return (
    <LijstRij data-open-punt={p.id} data-status={p.status} titel={<>{kop}<p className="mt-1">{p.inhoud.vraag}</p></>}
      status={<StatusLabel toon={p.status === "open" || p.status === "gesignaleerd" ? "geel" : "groen"}>{OPEN_PUNT_STATUS_LABEL[p.status]}</StatusLabel>}>
      {inhoud}
    </LijstRij>
  );
}

function grondslagLink(g: Grondslag, werkgebiedId: string): React.ReactNode {
  const href = g.soort === "markering" ? elementPad(g.id) : g.soort === "bron" ? bronPad(g.id, werkgebiedId)
    : g.soort === "begrip" ? begripPad(werkgebiedId, g.id) : "";
  const tekst = g.label || g.id;
  return href ? <Link href={href} className="focus-ring rounded text-lint hover:underline">{tekst}</Link> : tekst;
}

function PuntInhoud({ punt: p, werkgebiedId, alleenLezen, onGewijzigd }: {
  punt: OpenPunt;
  werkgebiedId: string;
  alleenLezen: boolean;
  onGewijzigd: () => void;
}) {
  const nogTeToetsen = p.inhoud.te_toetsen.filter((t) => !t.getoetst);
  return (
    <div className="mt-2 space-y-2 text-sm">
      {p.inhoud.toelichting.trim() && <p className="text-muted">{p.inhoud.toelichting}</p>}
      {p.inhoud.lezingen.length > 0 && (
        <ul className="space-y-1.5" aria-label="Lezingen">
          {p.inhoud.lezingen.map((l) => (
            <li key={l.label} data-lezing={l.label}>
              <span className="font-medium text-ink">Lezing {l.label}</span>
              {p.keuze?.gekozen === l.label && <> <StatusLabel klein toon="groen">gekozen</StatusLabel></>}
              <span className="text-ink">: {l.omschrijving}</span>
              {/* De grondslag van een lezing, opklapbaar met de vindplaatsen: de vorm van `DefinitieOnderbouwing`. */}
              {l.grondslag.length > 0 && (
                <Uitklap className="mt-0.5" samenvatting={`Waarop lezing ${l.label} rust (${l.grondslag.length})`}>
                  <ul className="mt-1 space-y-1 pl-1">
                    {l.grondslag.map((g) => <li key={`${g.soort}:${g.id}`}>{grondslagLink(g, werkgebiedId)}</li>)}
                  </ul>
                </Uitklap>
              )}
            </li>
          ))}
        </ul>
      )}
      {p.inhoud.te_toetsen.length > 0 && (
        <ul className="space-y-1" aria-label="Te toetsen">
          {p.inhoud.te_toetsen.map((t, i) => (
            <li key={i} className="text-xs text-muted">
              {t.getoetst ? "Getoetst" : "Nog te toetsen"}: {BRONSOORT_LABEL[t.bronsoort].toLowerCase()}
              {t.omschrijving && ` (${t.omschrijving})`}{t.getoetst && t.uitkomst && `: ${t.uitkomst}`}
            </li>
          ))}
        </ul>
      )}
      {p.keuze && (
        <p className="text-sm text-ink" data-keuze>
          <span className="font-medium">Besluit:</span> {keuzeZin(p)}
          {p.keuze.door && <span className="text-xs text-muted"> · {p.keuze.door}</span>}
        </p>
      )}
      {!alleenLezen && (p.status === "open"
        ? <Besluit punt={p} werkgebiedId={werkgebiedId} onGewijzigd={onGewijzigd} />
        : <Heropenen punt={p} werkgebiedId={werkgebiedId} onGewijzigd={onGewijzigd} nogTeToetsen={nogTeToetsen.length} />)}
    </div>
  );
}

/** Het besluit van de jurist: een lezing (of, zonder lezingen, hoe het verder gaat), de methode en de motivering. */
function Besluit({ punt: p, werkgebiedId, onGewijzigd }: { punt: OpenPunt; werkgebiedId: string; onGewijzigd: () => void }) {
  const [b, setB] = useState<BesluitInvoer>({ gekozen: "", motivering: "", methode: null, uitkomst: null });
  const beleid = p.soort === "ontbrekend_uitvoeringsbeleid";
  const signaleren = b.uitkomst === "gesignaleerd";
  const [fout, setFout] = useState<string | null>(null);
  const [bezig, setBezig] = useState(false);
  const probleem = besluitFout(p, b);
  // Een melding over de invoer gaat weg zodra je iets aanpast: anders blijft "Kies een lezing." staan na het kiezen.
  const zet = (nieuw: BesluitInvoer) => { setB(nieuw); setFout(null); };
  const leg = async () => {
    if (probleem) { setFout(probleem); return; }
    setBezig(true);
    setFout(null);
    try {
      await besluitOpenPunt(werkgebiedId, p.id, p.revisie, b);
      onGewijzigd();
    } catch (e) {
      if (isRevisieConflict(e)) {
        setFout("Iemand anders wijzigde dit punt net. De nieuwste stand staat nu in beeld; kijk of je besluit nog nodig is.");
        onGewijzigd();
      } else setFout(foutTekst(e, "Het besluit is niet vastgelegd."));
    } finally {
      setBezig(false);
    }
  };
  return (
    <fieldset className="space-y-2 border-t border-line pt-2" data-besluit={p.id}>
      <legend className="sr-only">Besluit over: {p.inhoud.vraag}</legend>
      {beleid && (
        <div role="radiogroup" aria-label="Is er beleid?" className="grid gap-2 sm:grid-cols-2">
          {([["gekozen", "Het beleid is er"], ["gesignaleerd", "Het beleid ontbreekt (signaleren)"]] as const).map(([w, label]) => (
            <label key={w} className={`cursor-pointer rounded-knop border p-2 text-xs ${b.uitkomst === w ? "border-lint" : "border-line"}`}>
              <input type="radio" name={`uitkomst-${p.id}`} className="focus-ring mr-1.5 accent-lint" checked={b.uitkomst === w}
                onChange={() => zet({ ...b, uitkomst: w, gekozen: w === "gesignaleerd" ? "" : b.gekozen })} data-uitkomst={w} />
              <span className="font-medium text-ink">{label}</span>
            </label>
          ))}
        </div>
      )}
      {p.inhoud.lezingen.length > 0 && !signaleren && (
        <div role="radiogroup" aria-label="Kies een lezing" className="grid gap-2 sm:grid-cols-2">
          {p.inhoud.lezingen.map((l) => (
            <label key={l.label} className={`cursor-pointer rounded-knop border p-2 text-xs ${b.gekozen === l.label ? "border-lint" : "border-line"}`}>
              <input type="radio" name={`lezing-${p.id}`} className="focus-ring mr-1.5 accent-lint" checked={b.gekozen === l.label}
                onChange={() => zet({ ...b, gekozen: l.label })} />
              <span className="font-medium text-ink">Lezing {l.label}</span>
            </label>
          ))}
        </div>
      )}
      <Select aria-label="Methode van de interpretatie" value={b.methode ?? ""} className="w-full sm:w-auto"
        onChange={(e) => zet({ ...b, methode: (e.target.value || null) as Methode | null })}>
        <option value="">{p.soort === "interpretatiekeuze" ? "Kies de methode" : "Methode (optioneel)"}</option>
        {(Object.keys(METHODE_LABEL) as Methode[]).map((m) => <option key={m} value={m}>{METHODE_LABEL[m]}</option>)}
      </Select>
      <AutoTextarea aria-label={signaleren ? "Welk beleid ontbreekt" : p.inhoud.lezingen.length ? "Waarom deze lezing" : "Hoe het verder gaat"} rows={2}
        className="w-full" value={b.motivering} onChange={(e) => zet({ ...b, motivering: e.target.value })}
        placeholder={signaleren ? "Welk beleid ontbreekt?" : p.inhoud.lezingen.length ? "Waarom deze lezing?" : "Hoe gaat het verder?"} />
      {fout && <Melding type="waarschuwing" compact>{fout}</Melding>}
      <ButtonRow>
        <Button size="sm" disabled={bezig} onClick={() => void leg()} data-besluit-vastleggen>Besluit vastleggen</Button>
      </ButtonRow>
    </fieldset>
  );
}

/** Een genomen besluit weer openzetten: de api heropent bij een leeg besluit. */
function Heropenen({ punt: p, werkgebiedId, onGewijzigd, nogTeToetsen }: {
  punt: OpenPunt; werkgebiedId: string; onGewijzigd: () => void; nogTeToetsen: number;
}) {
  const [fout, setFout] = useState<string | null>(null);
  const heropen = async () => {
    try {
      await besluitOpenPunt(werkgebiedId, p.id, p.revisie, { gekozen: "", motivering: "", methode: null });
      onGewijzigd();
    } catch (e) {
      setFout(foutTekst(e, "Heropenen is niet gelukt."));
      if (isRevisieConflict(e)) onGewijzigd();
    }
  };
  return (
    <div className="space-y-1">
      {nogTeToetsen > 0 && <p className="text-xs text-muted">{aantal(nogTeToetsen, "punt moet", "punten moeten")} nog getoetst worden.</p>}
      {fout && <Melding type="waarschuwing" compact>{fout}</Melding>}
      <Button size="xs" variant="secondary" onClick={() => void heropen()}>Besluit heropenen</Button>
    </div>
  );
}
