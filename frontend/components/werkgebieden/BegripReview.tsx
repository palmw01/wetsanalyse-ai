"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Meter } from "@/components/ui/Meter";
import { Melding } from "@/components/ui/Melding";
import { keurElementGoed } from "@/lib/annotatieNode";
import {
  accordeerBegrip, akkoordGroep, beantwoordVraag, besluitGroep, foutTekst, haalBegrip, isApiError, koppelGroep,
  wijzigBegrip,
} from "@/lib/api";
import {
  AANDACHT_LABEL, BEGRIPSTYPE_LABEL, BESLUIT_LABEL, HERKOMST_LABEL, OORDEEL_LABEL, REVIEW_FILTERS, aandachtspunten,
  aanpassingUit, akkoordLabel, akkoordVoor, groepDefinitie, herkomstNaAanpassing, naBesluit, onbeoordeeldeAnnotaties,
  passageTekst, reviewItems, reviewVoortgang, samenAkkoord, samenOvername, vergelijk, volgendeItem,
  type ReviewFilter,
} from "@/lib/begripVoorstellen";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type {
  AkkoordAntwoord, AkkoordInvoer, Begrip, Begripstype, Betekenisgroep, DefinitieHerkomst, GroepenAntwoord, Passage,
  TwijfelVraag,
} from "@/lib/types";

const KNOP =
  "focus-ring inline-flex min-h-[24px] items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50 coarse:min-h-[44px]";
const KNOP_PRIMAIR = `${KNOP} border-lint bg-lint text-paper hover:bg-accent-soft`;
const KNOP_TWEEDE = `${KNOP} border-line text-lint hover:bg-surface`;
const KNOP_STIL = `${KNOP} border-line text-muted hover:bg-surface hover:text-ink`;

type Modus = "geen" | "aanpassen" | "afwijzen" | "parkeren" | "samen";

/** Een sneltoets op de knop zelf, zoals bij annoteren: de knop en de toets doen hetzelfde. */
const Kbd = ({ t }: { t: string }) => <kbd className="ml-0.5 rounded border border-current/30 px-1 text-[10px] opacity-70">{t}</kbd>;

/** Een akkoord dat een concept bleef: wat er openstaat, en hoe je het hier oplost. */
interface Concept {
  begrip: Begrip;
  bezig?: boolean;
}

/** De begrippenreview (spoor D, fase D): de voorstellen van Lex als reviewlijst, in dezelfde vorm als
 *  de annotatiereview – groepen én twijfelvragen in één lijst, voortgang, filters en sneltoetsen.
 *
 *  **Akkoord** (`a`) maakt in één handeling een begrip met beoordeelde koppelingen, en accordeert het als
 *  de poort dat toelaat; anders blijft het een concept en staat hier wat er nog openstaat, met een
 *  oplossing ter plekke (*Annotatie akkoord* is een aparte, expliciete beslissing op de annotatie).
 *  Aanpassen (`e`), afwijzen (`x`), parkeren (`p`), markeren om te combineren (`m`, met een
 *  vergelijking vooraf), en bij een twijfelvraag samen (`s`) of apart (`n`). Geen besluit wijzigt een
 *  annotatie, behalve die ene knop. */
export function BegripReview({ id, data, onHerlaad, onBegrip, onGewijzigd }: {
  id: string;
  data: GroepenAntwoord;
  onHerlaad: () => Promise<GroepenAntwoord | null>;
  onBegrip: (begripId: string) => void;
  onGewijzigd: () => void;
}) {
  const [filter, setFilter] = useState<ReviewFilter>("te_beoordelen");
  const [actiefId, setActiefId] = useState<string | undefined>();
  const [modus, setModus] = useState<Modus>("geen");
  const [gemarkeerd, setGemarkeerd] = useState<string[]>([]);
  const [concepten, setConcepten] = useState<Concept[]>([]);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ tekst: string; begripId?: string } | null>(null);
  const [bezig, setBezig] = useState(false);
  // Per groep de gekozen passages (splitsen); standaard alle.
  const [keuze, setKeuze] = useState<Record<string, Set<string>>>({});
  const wortel = useRef<HTMLElement>(null);

  const items = reviewItems(data, filter);
  const voortgang = reviewVoortgang(data);
  const actief = items.find((i) => i.id === actiefId);
  const combi = gemarkeerd.map((g) => data.groepen.find((x) => x.id === g)).filter((g): g is Betekenisgroep => !!g);

  const gekozenVan = (g: Betekenisgroep) => keuze[g.id] ?? new Set(g.leden.map((l) => l.element_id));

  /** Een besluit uitvoeren, herladen, en door naar het volgende open item. */
  async function besluit<T>(itemId: string | null, actie: () => Promise<T>, na?: (uit: T) => void): Promise<boolean> {
    setFout(null);
    setMelding(null);
    setBezig(true);
    try {
      const uit = await actie();
      const voor = items;
      const nieuw = await onHerlaad();
      onGewijzigd();
      setModus("geen");
      // De vinkjes golden de leden van toen: na splitsen staat er alleen de rest, en een oude keuze
      // zou een akkoord zonder passages opleveren.
      setKeuze({});
      na?.(uit);
      if (itemId && nieuw) setActiefId(naBesluit(voor, itemId, reviewItems(nieuw, filter)));
      return true;
    } catch (e) {
      // Een tweede akkoord (dubbelklik, ander tabblad): het begrip bestaat al, open dat.
      const begrippen = isApiError(e) ? (e.data?.begrippen as Record<string, string> | undefined) : undefined;
      const bestaand = begrippen && Object.values(begrippen).find(Boolean);
      if (bestaand) {
        await onHerlaad();
        setMelding({ tekst: "Dit voorstel is al een begrip geworden.", begripId: bestaand });
      } else setFout(foutTekst(e));
      return false;
    } finally {
      setBezig(false);
    }
  }

  function naAkkoord(uit: AkkoordAntwoord) {
    const naam = uit.begrip.inhoud.naam;
    if (uit.geaccordeerd) setMelding({ tekst: `Begrip “${naam}” is geaccordeerd.`, begripId: uit.begrip.id });
    else setConcepten((c) => [{ begrip: uit.begrip }, ...c.filter((x) => x.begrip.id !== uit.begrip.id)]);
  }

  const akkoord = (itemId: string, invoer: AkkoordInvoer) =>
    besluit(itemId, () => akkoordGroep(id, invoer), naAkkoord);

  function akkoordOpGroep(g: Betekenisgroep) {
    const gekozen = gekozenVan(g);
    if (!gekozen.size) return setFout("Kies minstens één passage.");
    return akkoord(g.id, akkoordVoor([g], gekozen, g.voorstel.naam));
  }

  // --- het toetsenbord: alleen in de review zelf, of als de focus nergens staat ---------------------
  useEffect(() => {
    function opToets(e: KeyboardEvent) {
      const doel = e.target as HTMLElement | null;
      // Een vinkje (splitsen) of keuzerondje is geen tekstveld: daar mogen de toetsen gewoon werken.
      const keuzeVak = doel instanceof HTMLInputElement && (doel.type === "checkbox" || doel.type === "radio");
      const inVeld = !!doel && !keuzeVak && (doel.tagName === "INPUT" || doel.tagName === "TEXTAREA"
        || doel.tagName === "SELECT" || doel.isContentEditable);
      // Binnen = de strook met de voorstellen (ook de kop, waar de focus na "Stel begrippen voor" staat),
      // het artefactpaneel eromheen, of nergens. Niet vanuit de chat ernaast of een ander venster.
      const binnen = !doel || doel === document.body || !!wortel.current?.contains(doel)
        || !!doel.closest("[data-begripvoorstellen], [data-artefact]") || !!doel.querySelector("[data-begripreview]");
      if (e.key === "Escape") {
        if (!binnen) return;
        if (modus !== "geen") setModus("geen");
        else if (inVeld) (doel as HTMLElement).blur();
        else setActiefId(undefined);
        return;
      }
      if (inVeld || !binnen || e.metaKey || e.ctrlKey || e.altKey || bezig) return;
      const stap = (r: 1 | -1) => {
        const v = volgendeItem(items, actiefId, r);
        if (v) { e.preventDefault(); setModus("geen"); setActiefId(v.id); }
      };
      if (e.key === "j" || e.key === "ArrowDown") return stap(1);
      if (e.key === "k" || e.key === "ArrowUp") return stap(-1);
      if (!actief) return;
      if (actief.soort === "groep") {
        const g = actief.groep;
        if (g.besluit !== "open" && g.besluit !== "geparkeerd") return;
        const zet = (m: Modus) => { e.preventDefault(); setModus((h) => (h === m ? "geen" : m)); };
        if (e.key === "a") { e.preventDefault(); void akkoordOpGroep(g); }
        else if (e.key === "e") zet("aanpassen");
        else if (e.key === "x") zet("afwijzen");
        else if (e.key === "p" && g.besluit === "open") zet("parkeren");
        else if (e.key === "m") {
          e.preventDefault();
          setGemarkeerd((m) => (m.includes(g.id) ? m.filter((x) => x !== g.id) : [...m, g.id]));
        }
      } else if (!data.run?.vragen_besluiten?.[actief.vraag.kandidaat_id]) {
        if (e.key === "s") { e.preventDefault(); setModus("samen"); }
        else if (e.key === "n") {
          e.preventDefault();
          void besluit(actief.id, () => beantwoordVraag(id, data.run!.id, actief.vraag.kandidaat_id, "apart"));
        }
      }
    }
    window.addEventListener("keydown", opToets);
    return () => window.removeEventListener("keydown", opToets);
  });

  return (
    <section ref={wortel} data-begripreview className="space-y-2.5" aria-label="Review van de voorstellen">
      <div className="rounded-kaart border border-line bg-surface px-3 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
          <span className="text-xs font-medium text-ink">Review – {voortgang.beslist}/{voortgang.totaal} beoordeeld</span>
          {voortgang.totaal > 0 && voortgang.beslist === voortgang.totaal
            ? <span className="text-[0.65rem] font-semibold text-aandacht-groen-tekst">Review afgerond</span>
            : <span className="text-[0.65rem] text-muted">{voortgang.totaal - voortgang.beslist} te gaan</span>}
        </div>
        <Meter percentage={voortgang.totaal ? Math.round((voortgang.beslist / voortgang.totaal) * 100) : 0}
          label="Voortgang review van de voorstellen" afgerond={voortgang.totaal > 0 && voortgang.beslist === voortgang.totaal}
          className="mt-2" />
        <div className="mt-2.5 flex flex-wrap gap-1" role="group" aria-label="Filter de review">
          {REVIEW_FILTERS.map((f) => {
            const n = f.waarde === "alles" ? voortgang.totaal : f.waarde === "te_beoordelen"
              ? voortgang.totaal - voortgang.beslist : voortgang.aandacht;
            return (
              <button key={f.waarde} type="button" aria-pressed={filter === f.waarde} onClick={() => setFilter(f.waarde)}
                className={`focus-ring min-h-[24px] rounded-full border px-2.5 py-0.5 text-[0.7rem] transition coarse:min-h-[44px] ${
                  filter === f.waarde ? "border-lint bg-lint text-paper" : "border-line text-muted hover:border-lint hover:text-ink"}`}>
                {f.label} ({n})
              </button>
            );
          })}
        </div>
        <p className="mt-2 text-[0.65rem] text-faint">
          Sneltoetsen: <kbd>j</kbd>/<kbd>k</kbd> volgende · <kbd>a</kbd> akkoord · <kbd>e</kbd> aanpassen · <kbd>x</kbd> afwijzen
          · <kbd>p</kbd> parkeren · <kbd>m</kbd> combineren · bij een vraag <kbd>s</kbd> samen / <kbd>n</kbd> apart · <kbd>Esc</kbd> terug
        </p>
      </div>

      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {melding && (
        <Melding type="uitleg" compact>
          {melding.tekst}
          {melding.begripId && (
            <>{" "}<button type="button" className="focus-ring rounded text-lint underline" onClick={() => onBegrip(melding.begripId!)}>
              Open het begrip</button></>
          )}
        </Melding>
      )}

      {concepten.length > 0 && (
        <ul className="space-y-2" aria-label="Nog te accorderen">
          {concepten.map((c) => (
            <ConceptKaart key={c.begrip.id} id={id} concept={c} onBegrip={onBegrip}
              onKlaar={(b) => {
                setConcepten((l) => l.filter((x) => x.begrip.id !== b.id));
                setMelding({ tekst: `Begrip “${b.inhoud.naam}” is geaccordeerd.`, begripId: b.id });
                onGewijzigd();
              }}
              onBijgewerkt={(b) => setConcepten((l) => l.map((x) => (x.begrip.id === b.id ? { begrip: b } : x)))}
              onFout={setFout} />
          ))}
        </ul>
      )}

      {combi.length >= 2 && (
        <Vergelijk groepen={combi} bezig={bezig} onAnnuleer={() => setGemarkeerd([])}
          onAkkoord={(naam, definitieVan) => {
            const leden = new Set(combi.flatMap((g) => [...gekozenVan(g)]));
            void besluit(combi[0].id, () => akkoordGroep(id, akkoordVoor(combi, leden, naam, { definitieVan })), (uit) => {
              setGemarkeerd([]);
              naAkkoord(uit);
            });
          }} />
      )}
      {combi.length === 1 && (
        <p className="text-xs text-muted">“{combi[0].voorstel.naam}” is gemarkeerd om te combineren; markeer nog een groep (<kbd>m</kbd>).</p>
      )}

      {items.length === 0 && (
        <p className="rounded-kaart border border-dashed border-line px-3 py-4 text-center text-xs text-muted">
          {filter === "alles" ? "Er zijn geen voorstellen." : "Niets meer te beoordelen in deze selectie."}
        </p>
      )}

      <ul className="space-y-2" aria-label="Voorstellen om te beoordelen">
        {items.map((it) => it.soort === "groep" ? (
          <GroepItem key={it.id} groep={it.groep} actief={it.id === actiefId} modus={it.id === actiefId ? modus : "geen"}
            bezig={bezig} gemarkeerd={gemarkeerd.includes(it.id)} gekozen={gekozenVan(it.groep)}
            onKies={() => { if (it.id !== actiefId) { setActiefId(it.id); setModus("geen"); } }}
            onModus={(m) => { setActiefId(it.id); setModus(m); }}
            onKeuze={(s) => setKeuze((k) => ({ ...k, [it.id]: s }))}
            onMarkeer={() => setGemarkeerd((m) => (m.includes(it.id) ? m.filter((x) => x !== it.id) : [...m, it.id]))}
            onAkkoord={(naam, aanpassing) => {
              const g = it.groep;
              const gekozen = gekozenVan(g);
              if (!gekozen.size) return setFout("Kies minstens één passage.");
              void akkoord(g.id, akkoordVoor([g], gekozen, naam, { aanpassing }));
            }}
            onKoppel={(begripId) => void besluit(it.id, () => koppelGroep(id, it.id, begripId, [...gekozenVan(it.groep)], true),
              (b) => setMelding({ tekst: `Gekoppeld aan “${b.inhoud.naam}”${b.status === "geaccordeerd" ? " (geaccordeerd)" : ""}.`, begripId: b.id }))}
            onBesluit={(soort, reden) => void besluit(it.id, () => besluitGroep(id, it.id, soort, reden))}
            onBegrip={onBegrip} />
        ) : (
          <VraagItem key={it.id} vraag={it.vraag} data={data} actief={it.id === actiefId} bezig={bezig}
            samen={it.id === actiefId && modus === "samen"}
            onKies={() => { if (it.id !== actiefId) { setActiefId(it.id); setModus("geen"); } }}
            onSamen={(open) => { setActiefId(it.id); setModus(open ? "samen" : "geen"); }}
            onApart={() => void besluit(it.id, () => beantwoordVraag(id, data.run!.id, it.vraag.kandidaat_id, "apart"))}
            onAkkoord={(naam) => void akkoord(it.id, samenAkkoord(it.vraag, data.groepen, data.passages, naam))} />
        ))}
      </ul>
    </section>
  );
}

// --- één groep ---------------------------------------------------------------------------------------

function GroepItem({ groep: g, actief, modus, bezig, gemarkeerd, gekozen, onKies, onModus, onKeuze, onMarkeer, onAkkoord,
  onKoppel, onBesluit, onBegrip }: {
  groep: Betekenisgroep;
  actief: boolean;
  modus: Modus;
  bezig: boolean;
  gemarkeerd: boolean;
  gekozen: Set<string>;
  onKies: () => void;
  onModus: (m: Modus) => void;
  onKeuze: (s: Set<string>) => void;
  onMarkeer: () => void;
  onAkkoord: (naam: string, aanpassing?: ReturnType<typeof aanpassingUit>) => void;
  onKoppel: (begripId: string) => void;
  onBesluit: (soort: "afwijzen" | "parkeren" | "heropenen", reden?: string) => void;
  onBegrip: (begripId: string) => void;
}) {
  const beslisbaar = g.besluit === "open" || g.besluit === "geparkeerd";
  const definitie = groepDefinitie(g);
  const label = akkoordLabel(g);
  const deel = gekozen.size < g.leden.length ? ` (${gekozen.size} van ${g.leden.length})` : "";
  const naam = `groep “${g.voorstel.naam}”`;
  const ref = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (!actief || !ref.current) return;
    const rustig = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    ref.current.scrollIntoView({ block: "nearest", behavior: rustig ? "auto" : "smooth" });
  }, [actief]);

  return (
    <li ref={ref} data-review-item={g.id} aria-current={actief || undefined} onClick={onKies}
      className={`rounded-kaart border border-l-4 bg-paper px-3 py-2 ${actief ? "border-lint" : "border-line"} ${
        g.aandacht === "geel" ? "border-l-aandacht-geel-rand" : "border-l-aandacht-groen-rand"} ${beslisbaar ? "" : "opacity-75"}`}>
      <div className="flex items-start justify-between gap-2">
        <button type="button" className="focus-ring min-w-0 rounded text-left" aria-expanded={actief}
          onClick={(e) => { e.stopPropagation(); onKies(); }}>
          <span className="block font-display text-sm font-semibold text-lint">{g.voorstel.naam}</span>
          <span className="block text-[11px] text-muted">
            <span className={g.aandacht === "geel" ? "text-aandacht-geel-tekst" : ""}>{AANDACHT_LABEL[g.aandacht]}</span>
            {" · "}{g.leden.length} {g.leden.length === 1 ? "passage" : "passages"}
            {g.afgehandeld ? ` · ${g.afgehandeld} al een begrip` : ""}
            {g.door === "model" && " · samengevoegd op advies van Lex"}
            {g.kaart?.begripstype && ` · ${BEGRIPSTYPE_LABEL[g.kaart.begripstype]}`}
            {g.besluit !== "open" && ` · ${BESLUIT_LABEL[g.besluit]}`}
            {beslisbaar && label.concept && <span className="text-aandacht-geel-tekst"> · nog niet te accorderen</span>}
          </span>
        </button>
        {gemarkeerd && <span className="shrink-0 rounded-full border border-lint px-2 text-[10px] text-lint">combineren</span>}
      </div>

      {actief && (
        <div className="mt-2 space-y-2" onClick={(e) => e.stopPropagation()}>
          {definitie && (
            <div className="text-xs text-ink" data-herkomst={definitie.herkomst}>
              <span className={definitie.herkomst === "geformuleerd" ? "text-aandacht-geel-tekst" : "text-muted"}>
                {definitie.herkomst === "letterlijk" ? "Brondefinitie" : `Definitie, ${HERKOMST_LABEL[definitie.herkomst]}`}
                {definitie.vindplaats ? ` (${definitie.vindplaats})` : ""}:{" "}
              </span>
              {definitie.herkomst === "geformuleerd" ? definitie.tekst : `“${definitie.tekst}”`}
              {definitie.fragmenten.length > 0 && (
                <details className="mt-0.5">
                  <summary className="focus-ring cursor-pointer rounded text-muted">
                    Rust op {definitie.fragmenten.length === 1 ? "1 passage" : `${definitie.fragmenten.length} passages`} uit de bron
                  </summary>
                  <ul className="mt-1 space-y-0.5 pl-4">{definitie.fragmenten.map((f) => <li key={f.id}>“{f.tekst}”</li>)}</ul>
                </details>
              )}
              {g.kaart?.motivatie && <p className="mt-0.5 text-muted">Toelichting van Lex: {g.kaart.motivatie}</p>}
            </div>
          )}
          {g.kaart && aandachtspunten(g.kaart.aandachtspunten).length > 0 && (
            <ul className="space-y-0.5 text-xs text-aandacht-geel-tekst" aria-label={`Aandachtspunten bij ${naam}`}>
              {aandachtspunten(g.kaart.aandachtspunten).map((a) => <li key={a}>{a}</li>)}
            </ul>
          )}
          <ul className="space-y-1" aria-label={`Passages van ${naam}`}>
            {g.leden.map((l) => (
              <li key={l.element_id} className="flex items-start gap-2 text-sm">
                {beslisbaar && (
                  <input type="checkbox" checked={gekozen.has(l.element_id)} className="focus-ring mt-1 accent-lint"
                    aria-label={`Neem “${l.tekst}” mee`}
                    onChange={(e) => { const n = new Set(gekozen); if (e.target.checked) n.add(l.element_id); else n.delete(l.element_id); onKeuze(n); }} />
                )}
                <PassageRegel p={l} />
              </li>
            ))}
          </ul>
          {g.uitleg.length > 0 && <ul className="space-y-0.5 text-xs text-muted">{g.uitleg.map((u) => <li key={u}>{u}</li>)}</ul>}
          {g.conflicten.length > 0 && (
            <p className="text-xs text-aandacht-geel-tekst">
              Er is ook bewijs dat ze níét hetzelfde betekenen ({g.conflicten.length}); beoordeel de passages zelf.
            </p>
          )}
          {beslisbaar && label.concept && (
            <div className="rounded-kaart border border-aandacht-geel-rand bg-aandacht-geel-bg/40 px-2 py-1.5 text-xs text-ink">
              Na akkoord blijft dit een concept:
              <ul className="mt-0.5 list-disc pl-4">{label.redenen.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
          )}

          {beslisbaar && modus === "aanpassen" ? (
            <AanpasFormulier groep={g} bezig={bezig} onAnnuleer={() => onModus("geen")} onAkkoord={onAkkoord} />
          ) : beslisbaar && (modus === "afwijzen" || modus === "parkeren") ? (
            <RedenFormulier soort={modus} naam={naam} onAnnuleer={() => onModus("geen")} onBevestig={(r) => onBesluit(modus, r)} />
          ) : beslisbaar ? (
            <div className="flex flex-wrap gap-1.5">
              <button type="button" disabled={bezig || gekozen.size === 0} className={KNOP_PRIMAIR}
                aria-label={`${label.label}: ${naam}`} onClick={() => onAkkoord(g.voorstel.naam)}>
                {label.label}{deel}<Kbd t="a" />
              </button>
              <button type="button" disabled={bezig} className={KNOP_TWEEDE} aria-label={`Pas ${naam} aan`} onClick={() => onModus("aanpassen")}>
                Aanpassen<Kbd t="e" />
              </button>
              <button type="button" disabled={bezig} className={KNOP_STIL} aria-label={`Wijs ${naam} af`} onClick={() => onModus("afwijzen")}>
                Afwijzen<Kbd t="x" />
              </button>
              {g.besluit === "open" ? (
                <button type="button" disabled={bezig} className={KNOP_STIL} aria-label={`Parkeer ${naam}`} onClick={() => onModus("parkeren")}>
                  Parkeren<Kbd t="p" />
                </button>
              ) : (
                <button type="button" disabled={bezig} className={KNOP_STIL} aria-label={`Heropen ${naam}`} onClick={() => onBesluit("heropenen")}>
                  Heropenen
                </button>
              )}
              <button type="button" aria-pressed={gemarkeerd} className={KNOP_STIL} aria-label={`Markeer ${naam} om te combineren`}
                onClick={onMarkeer}>
                {gemarkeerd ? "Niet combineren" : "Combineren"}<Kbd t="m" />
              </button>
              {g.lijkt_op.map((b) => (
                <button key={b.begrip_id} type="button" disabled={bezig} className={KNOP_TWEEDE}
                  aria-label={`Koppel ${naam} aan het begrip ${b.naam}`} onClick={() => onKoppel(b.begrip_id)}>
                  Koppelen aan {b.naam}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted">
              {BESLUIT_LABEL[g.besluit]}{g.reden ? `: ${g.reden}` : ""}
              {g.begrip_id ? (
                <>{" · "}<button type="button" className="focus-ring rounded text-lint underline" onClick={() => onBegrip(g.begrip_id!)}>begrip openen</button></>
              ) : (
                <>{" · "}<button type="button" className="focus-ring rounded text-lint underline" aria-label={`Heropen ${naam}`}
                  onClick={() => onBesluit("heropenen")}>heropenen</button></>
              )}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function PassageRegel({ p }: { p: Passage }) {
  const onbeoordeeld = p.annotatie_beoordeeld === false || (p.annotatie_beoordeeld === undefined && p.review_status === "voorgesteld");
  return (
    <span className="min-w-0">
      <span className={`mr-1 inline-flex rounded-full border px-1.5 text-[10px] ${jasStyle(p.jas_klasse)}`}>{klasseLabel(p.jas_klasse)}</span>
      <span className="text-ink">“{p.tekst}”</span>{" "}
      <span className="text-xs text-muted">{p.vindplaats}</span>
      {onbeoordeeld && <span className="text-xs text-aandacht-geel-tekst"> · annotatie nog niet beoordeeld</span>}
    </span>
  );
}

/** Aanpassen vóór het akkoord: de velden van het voorstel, ingevuld. Wat je niet verandert, laat de api
 *  uit het voorstel komen (ook de herkomst). Enter in een veld = akkoord, Escape = terug. */
function AanpasFormulier({ groep: g, bezig, onAnnuleer, onAkkoord }: {
  groep: Betekenisgroep;
  bezig: boolean;
  onAnnuleer: () => void;
  onAkkoord: (naam: string, aanpassing: ReturnType<typeof aanpassingUit>) => void;
}) {
  const def = groepDefinitie(g);
  const voorstel = {
    definitie: def?.tekst ?? "", herkomst: def?.herkomst ?? null,
    context: g.kaart?.context ?? "", begripstype: (g.kaart?.begripstype ?? "") as Begripstype | "",
  };
  const [naam, setNaam] = useState(g.voorstel.naam);
  const [definitie, setDefinitie] = useState(voorstel.definitie);
  const [herkomst, setHerkomst] = useState<DefinitieHerkomst | null>(null);
  const [context, setContext] = useState(voorstel.context);
  const [type, setType] = useState<Begripstype | "">(voorstel.begripstype);
  const wordt = herkomstNaAanpassing({ tekst: voorstel.definitie, herkomst: voorstel.herkomst }, definitie, herkomst);
  const verstuur = () => {
    if (!naam.trim()) return;
    onAkkoord(naam, aanpassingUit(voorstel, { definitie, herkomst, context, begripstype: type }));
  };
  const opEnter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !(e.target instanceof HTMLTextAreaElement)) { e.preventDefault(); verstuur(); }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); verstuur(); }
  };
  return (
    <form className="space-y-2 text-xs" onSubmit={(e) => { e.preventDefault(); verstuur(); }} onKeyDown={opEnter}>
      <label className="block">
        <span className="text-muted">Naam</span>
        <Input autoFocus value={naam} maxLength={200} onChange={(e) => setNaam(e.target.value)} />
      </label>
      <label className="block">
        <span className="text-muted">Definitie</span>
        <textarea value={definitie} rows={3} maxLength={8000} onChange={(e) => setDefinitie(e.target.value)}
          className="focus-ring mt-0.5 w-full rounded-button border border-line bg-paper px-2 py-1 text-sm text-ink" />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1">
          <span className="text-muted">Herkomst</span>
          <select value={herkomst ?? ""} onChange={(e) => setHerkomst((e.target.value || null) as DefinitieHerkomst | null)}
            className="focus-ring rounded-button border border-line bg-paper px-1.5 py-0.5">
            <option value="">volgt uit de tekst</option>
            <option value="letterlijk">letterlijk uit de wet</option>
            <option value="geformuleerd">geformuleerd</option>
          </select>
        </label>
        {wordt && <span className="text-muted" data-herkomst-wordt={wordt}>wordt: {wordt === "geformuleerd" ? "geformuleerd" : HERKOMST_LABEL[wordt]}</span>}
        <label className="flex items-center gap-1">
          <span className="text-muted">Begripstype</span>
          <select value={type} onChange={(e) => setType(e.target.value as Begripstype | "")}
            className="focus-ring rounded-button border border-line bg-paper px-1.5 py-0.5">
            <option value="">–</option>
            {(Object.keys(BEGRIPSTYPE_LABEL) as Begripstype[]).map((t) => <option key={t} value={t}>{BEGRIPSTYPE_LABEL[t]}</option>)}
          </select>
        </label>
      </div>
      <label className="block">
        <span className="text-muted">Context</span>
        <textarea value={context} rows={2} maxLength={4000} onChange={(e) => setContext(e.target.value)}
          placeholder="Leeg: afgeleid uit de vindplaatsen"
          className="focus-ring mt-0.5 w-full rounded-button border border-line bg-paper px-2 py-1 text-sm text-ink" />
      </label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="submit" size="sm" disabled={bezig || !naam.trim()}>Akkoord met aanpassing</Button>
        <Button type="button" size="sm" variant="secondary" onClick={onAnnuleer}>Annuleren</Button>
      </div>
    </form>
  );
}

function RedenFormulier({ soort, naam, onAnnuleer, onBevestig }: {
  soort: "afwijzen" | "parkeren";
  naam: string;
  onAnnuleer: () => void;
  onBevestig: (reden: string) => void;
}) {
  const [reden, setReden] = useState("");
  return (
    <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); onBevestig(reden); }}>
      <Input autoFocus value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Reden"
        aria-label={`Reden om ${naam} ${soort === "afwijzen" ? "af te wijzen" : "te parkeren"}`} />
      <Button type="submit" size="sm" variant="secondary">{soort === "afwijzen" ? "Afwijzen" : "Parkeren"}</Button>
      <Button type="button" size="sm" variant="ghost" onClick={onAnnuleer}>Annuleren</Button>
    </form>
  );
}

// --- één twijfelvraag ------------------------------------------------------------------------------

function VraagItem({ vraag: v, data, actief, bezig, samen, onKies, onSamen, onApart, onAkkoord }: {
  vraag: TwijfelVraag;
  data: GroepenAntwoord;
  actief: boolean;
  bezig: boolean;
  samen: boolean;
  onKies: () => void;
  onSamen: (open: boolean) => void;
  onApart: () => void;
  onAkkoord: (naam: string) => void;
}) {
  const antwoord = data.run?.vragen_besluiten?.[v.kandidaat_id];
  const oordeel = data.verdieping?.oordelen?.[v.kandidaat_id];
  const zin = `Horen ${passageTekst(v.van, data.passages, data.groepen)} en ${passageTekst(v.naar, data.passages, data.groepen)} bij hetzelfde begrip?`;
  const [naam, setNaam] = useState(() => samenOvername(v, data.groepen, data.passages).naam);
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => {
    if (actief) ref.current?.scrollIntoView({ block: "nearest" });
  }, [actief]);

  return (
    <li ref={ref} data-review-item={v.kandidaat_id} aria-current={actief || undefined} onClick={onKies}
      className={`rounded-kaart border border-l-4 border-l-aandacht-geel-rand bg-paper px-3 py-2 text-sm ${actief ? "border-lint" : "border-line"}`}>
      <button type="button" className="focus-ring rounded text-left" aria-expanded={actief} onClick={(e) => { e.stopPropagation(); onKies(); }}>
        <span className="block text-[11px] text-muted">Twijfelvraag{antwoord ? ` · beantwoord: ${antwoord.antwoord}` : ""}</span>
        <span className="block text-ink">{zin}</span>
      </button>
      {actief && (
        <div className="mt-1.5 space-y-1.5" onClick={(e) => e.stopPropagation()}>
          {oordeel && !oordeel.reden && (
            <p className="text-xs text-ink" data-advies={oordeel.oordeel}>
              <span className="font-medium">Advies van Lex: {OORDEEL_LABEL[oordeel.oordeel]}</span>
              {oordeel.motivatie && <> – {oordeel.motivatie}</>}
            </p>
          )}
          {v.uitleg.map((u) => <p key={u} className="text-xs text-muted">{u}</p>)}
          {antwoord ? (
            <p className="text-xs text-muted">Beantwoord: {antwoord.antwoord} · {antwoord.door}</p>
          ) : samen ? (
            <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={(e) => { e.preventDefault(); if (naam.trim()) onAkkoord(naam); }}>
              <Input autoFocus value={naam} maxLength={200} onChange={(e) => setNaam(e.target.value)}
                aria-label={`Naam van het begrip uit: ${zin}`} className="sm:w-56" />
              <Button type="submit" size="sm" disabled={bezig || !naam.trim()}>Akkoord: één begrip</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => onSamen(false)}>Annuleren</Button>
            </form>
          ) : (
            <div className="flex gap-1.5">
              <button type="button" disabled={bezig} className={KNOP_PRIMAIR} aria-label={`Samen: ${zin}`} onClick={() => onSamen(true)}>
                Samen<Kbd t="s" />
              </button>
              <button type="button" disabled={bezig} className={KNOP_STIL} aria-label={`Apart: ${zin}`} onClick={onApart}>
                Apart<Kbd t="n" />
              </button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

// --- combineren: eerst vergelijken ------------------------------------------------------------------

function Vergelijk({ groepen, bezig, onAnnuleer, onAkkoord }: {
  groepen: Betekenisgroep[];
  bezig: boolean;
  onAnnuleer: () => void;
  onAkkoord: (naam: string, definitieVan?: string) => void;
}) {
  const v = vergelijk(groepen);
  const [naam, setNaam] = useState(groepen[0].voorstel.naam);
  const [definitieVan, setDefinitieVan] = useState<string>(v.metDefinitie.length === 1 ? v.metDefinitie[0] : "");
  return (
    <section aria-label="Vergelijking om te combineren" className="space-y-2 rounded-kaart border border-lint p-3">
      <p className="text-sm font-semibold text-lint">{groepen.length} groepen als één begrip?</p>
      {v.signalen.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-aandacht-geel-tekst" aria-label="Signalen tegen combineren">
          {v.signalen.map((s) => <li key={s}>{s}</li>)}
        </ul>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        {v.groepen.map((r) => (
          <div key={r.id} className="rounded-kaart border border-line p-2 text-xs">
            <p className="font-display text-sm font-semibold text-lint">{r.naam}</p>
            <p className="text-muted">{AANDACHT_LABEL[r.aandacht]}{r.begripstype ? ` · ${BEGRIPSTYPE_LABEL[r.begripstype]}` : ""} · {r.klassen.join(", ")}</p>
            {r.definitie ? (
              <label className="mt-1 flex items-start gap-1.5">
                <input type="radio" name="definitie-van" checked={definitieVan === r.id} onChange={() => setDefinitieVan(r.id)}
                  className="focus-ring mt-0.5 accent-lint" />
                <span><span className="text-muted">Definitie ({HERKOMST_LABEL[r.definitie.herkomst]}): </span>{r.definitie.tekst}</span>
              </label>
            ) : <p className="mt-1 text-muted">Geen definitie.</p>}
            <ul className="mt-1 space-y-0.5">{r.leden.map((l) => <li key={l.element_id}><PassageRegel p={l} /></li>)}</ul>
          </div>
        ))}
      </div>
      {v.metDefinitie.length > 0 && (
        <label className="flex items-center gap-1.5 text-xs text-ink">
          <input type="radio" name="definitie-van" checked={definitieVan === ""} onChange={() => setDefinitieVan("")} className="focus-ring accent-lint" />
          Geen definitie meenemen
        </label>
      )}
      <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={(e) => { e.preventDefault(); if (naam.trim()) onAkkoord(naam, definitieVan || undefined); }}>
        <Input value={naam} maxLength={200} onChange={(e) => setNaam(e.target.value)} aria-label="Naam van het gecombineerde begrip" className="sm:w-56" />
        <Button type="submit" size="sm" disabled={bezig || !naam.trim()}>Combineer: akkoord</Button>
        <Button type="button" size="sm" variant="secondary" onClick={onAnnuleer}>Annuleren</Button>
      </form>
    </section>
  );
}

// --- een akkoord dat een concept bleef ------------------------------------------------------------

/** Wat de poort nog tegenhoudt, met de oplossing ernaast. Na elke oplossing probeert de review opnieuw
 *  te accorderen: het akkoord van de jurist stond er al. */
function ConceptKaart({ id, concept, onBegrip, onKlaar, onBijgewerkt, onFout }: {
  id: string;
  concept: Concept;
  onBegrip: (begripId: string) => void;
  onKlaar: (b: Begrip) => void;
  onBijgewerkt: (b: Begrip) => void;
  onFout: (f: string) => void;
}) {
  const b = concept.begrip;
  const [bezig, setBezig] = useState(false);
  const [definitie, setDefinitie] = useState<string | null>(null);
  const open = onbeoordeeldeAnnotaties(b);

  async function probeer(stap: () => Promise<unknown>) {
    setBezig(true);
    try {
      await stap();
      let nu = await haalBegrip(id, b.id);
      if (nu.status !== "geaccordeerd" && nu.accorderen.mag) nu = await accordeerBegrip(id, b.id, nu.revisie);
      if (nu.status === "geaccordeerd") onKlaar(nu);
      else onBijgewerkt(nu);
    } catch (e) {
      onFout(foutTekst(e));
    } finally {
      setBezig(false);
    }
  }

  return (
    <li data-concept={b.id} className="rounded-kaart border border-aandacht-geel-rand bg-aandacht-geel-bg/40 px-3 py-2 text-sm">
      <p className="font-display text-sm font-semibold text-lint">
        {b.inhoud.naam} <span className="text-[11px] font-normal text-aandacht-geel-tekst">· concept, nog te accorderen</span>
      </p>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-ink">{b.accorderen.redenen.map((r) => <li key={r}>{r}</li>)}</ul>
      {open.length > 0 && (
        <ul className="mt-1.5 space-y-1" aria-label={`Onbeoordeelde annotaties van ${b.inhoud.naam}`}>
          {open.map((k) => (
            <li key={k.id} className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-ink">“{k.bewijs.tekst}”</span>
              <span className="text-muted">{k.bewijs.vindplaats}</span>
              <button type="button" disabled={bezig} className={KNOP_TWEEDE}
                aria-label={`Annotatie akkoord: ${k.bewijs.tekst}`}
                onClick={() => void probeer(() => keurElementGoed(k.element_id))}>
                Annotatie akkoord
              </button>
            </li>
          ))}
        </ul>
      )}
      {!b.inhoud.definitie && definitie !== null && (
        <form className="mt-1.5 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => {
          e.preventDefault();
          if (!definitie.trim()) return;
          void probeer(() => wijzigBegrip(id, b.id, b.revisie, { ...b.inhoud, definitie: definitie.trim(), definitie_herkomst: "geformuleerd" }));
        }}>
          <Input autoFocus value={definitie} onChange={(e) => setDefinitie(e.target.value)} aria-label={`Definitie van ${b.inhoud.naam}`} />
          <Button type="submit" size="sm" disabled={bezig || !definitie.trim()}>Opslaan</Button>
        </form>
      )}
      <div className="mt-1.5 flex flex-wrap items-center gap-3">
        {!b.inhoud.definitie && definitie === null && (
          <button type="button" className={KNOP_TWEEDE} onClick={() => setDefinitie("")}>Definitie toevoegen</button>
        )}
        <button type="button" className="focus-ring rounded text-xs text-lint underline" onClick={() => onBegrip(b.id)}>Open het begrip</button>
      </div>
    </li>
  );
}
