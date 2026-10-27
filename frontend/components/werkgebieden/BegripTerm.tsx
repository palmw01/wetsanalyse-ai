"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BronBoom } from "@/components/ui/BronBoom";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Kaart, PaginaKop, Stip } from "@/components/ui/Pagina";
import { useWerkgebied } from "@/components/werkgebieden/WerkgebiedProject";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import {
  akkoordGroep, beantwoordVraag, besluitGroep, foutTekst, haalGroepen, isApiError, koppelGroep,
} from "@/lib/api";
import {
  regelingVan, standaardKeuze, termAkkoord, termenVan, termOmvang, termVan, type Term,
} from "@/lib/begripTermen";
import {
  AANDACHT_LABEL, BESLUIT_LABEL, HERKOMST_LABEL, OORDEEL_LABEL, aandachtspunten, aanpassingUit, akkoordLabel, akkoordVoor,
  groepDefinitie, herkomstNaAanpassing, passageTekst, samenAkkoord,
} from "@/lib/begripVoorstellen";
import { bouwBoom } from "@/lib/bronPlaats";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Betekenisgroep, GroepenAntwoord, Passage, TwijfelVraag } from "@/lib/types";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { artefactPad, begripPad, elementPad, projectPad } from "@/lib/werkgebiedPaden";

const telling = (n: number, een: string, meer: string) => `${n} ${n === 1 ? een : meer}`;

/** De voorstellen van Lex voor één term (spoor H4). De keten maakt één groep per term per bepaling; hier
 *  staan ze weer bij elkaar, als passages per regeling › hoofdstuk › artikel › lid, met één besluit voor
 *  wat aangevinkt is: *Eén begrip maken*, koppelen aan een bestaand begrip, later, of geen begrip. De
 *  twijfelvragen binnen de term beantwoordt dat ene begrip mee; een vraag naar een andere term staat
 *  onderaan. Geen sneltoetsen. */
export function BegripTermPagina({ sleutel }: { sleutel: string }) {
  const { wg, laad: laadWg } = useWerkgebied();
  const [data, setData] = useState<GroepenAntwoord | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  const laad = useCallback(async () => {
    try {
      setData(await haalGroepen(wg.id));
      setFout(null);
    } catch (e) {
      setFout(foutTekst(e, "De voorstellen konden niet worden geladen."));
    }
  }, [wg.id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  const termen = useMemo(() => termenVan(data), [data]);
  const term = termVan(termen, sleutel);
  const kader = artefactPad(wg.id, "begrippen");

  return (
    <div data-begripterm-pagina={sleutel}>
      <PaginaKop
        kruimels={[
          { label: "Werkgebieden", href: "/werkgebieden" }, { label: wg.naam, href: projectPad(wg.id) },
          { label: "Artefacten", href: projectPad(wg.id, "artefacten") }, { label: "Begrippenkader", href: kader },
          { label: term?.naam ?? sleutel },
        ]}
        titel={term?.naam ?? sleutel}
        sub="Waar Lex deze term vond, per regeling en artikel. Vink aan wat één begrip draagt, en beslis in één keer."
        meta={term && <>
          <span>{termOmvang(term)}</span><Stip /><span>{telling(term.passages, "passage", "passages")}</span>
          {term.lijktOp.length > 0 && <><Stip /><span>lijkt op {term.lijktOp.map((b) => b.naam).join(", ")}</span></>}
        </>}
        acties={<VraagLexKnop primair onderwerp={{ soort: "werkgebied", werkgebied_id: wg.id, id: "", label: wg.naam }}
          naam={`Bespreek ${wg.naam} met Lex`} />}
      />
      {fout && <Melding type="fout">{fout}</Melding>}
      {!data && !fout && <p className="text-sm text-muted">Laden…</p>}
      {data && !term && (
        <Kaart>
          <p className="text-sm text-muted">
            Lex heeft voor “{sleutel}” geen voorstellen (meer). <Link href={kader} className="focus-ring rounded text-lint underline">Terug naar het begrippenkader</Link>
          </p>
        </Kaart>
      )}
      {data && term && (
        <TermBeoordeling key={term.open.map((g) => `${g.id}:${g.leden.length}:${g.besluit}`).join("|")}
          werkgebiedId={wg.id} term={term} data={data} onHerlaad={laad} onGewijzigd={() => void laadWg()} />
      )}
    </div>
  );
}

interface Item { p: Passage; g: Betekenisgroep }

function TermBeoordeling({ werkgebiedId, term, data, onHerlaad, onGewijzigd }: {
  werkgebiedId: string;
  term: Term;
  data: GroepenAntwoord;
  onHerlaad: () => Promise<void>;
  onGewijzigd: () => void;
}) {
  const router = useRouter();
  const [gekozen, setGekozen] = useState<ReadonlySet<string>>(() => standaardKeuze(term));
  const [naam, setNaam] = useState(term.naam);
  const [definitieVan, setDefinitieVan] = useState<string | null>(null);
  const [definitieTekst, setDefinitieTekst] = useState<string | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ tekst: string; begripId?: string } | null>(null);
  const [bezig, setBezig] = useState(false);
  const [geenBegrip, setGeenBegrip] = useState(false);

  const items: Item[] = useMemo(() => term.open.flatMap((g) => g.leden.map((p) => ({ p, g }))), [term]);
  const plaatsen = usePlaatsen(items.map((i) => i.p.bron_iri));
  const boom = useMemo(() => bouwBoom(items, {
    iri: (i) => i.p.bron_iri, sleutel: (i) => i.p.element_id, naam: (i) => i.p.vindplaats, plaatsen,
    regelingNaam: (i) => regelingVan(i.p) || undefined,
  }), [items, plaatsen]);

  const vragen = useMemo(() => [...term.vragenBinnen, ...term.vragenBuiten], [term]);
  const akkoord = termAkkoord(term, gekozen, vragen);
  const n = items.filter((i) => gekozen.has(i.p.element_id)).length;
  const geparkeerd = akkoord.groepen.filter((g) => g.besluit === "geparkeerd");

  // De definitie: uit een gekozen groep die er een heeft; bij meer dan één kies je.
  const metDefinitie = akkoord.groepen.filter((g) => groepDefinitie(g));
  const van = metDefinitie.find((g) => g.id === definitieVan)?.id
    ?? (definitieVan === null && metDefinitie.length === 1 ? metDefinitie[0].id : "");
  const defGroep = metDefinitie.find((g) => g.id === van);
  const def = defGroep ? groepDefinitie(defGroep) : null;
  const punten = aandachtspunten([...new Set(akkoord.groepen.flatMap((g) => g.kaart?.aandachtspunten ?? []))]);
  const definitie = definitieTekst ?? def?.tekst ?? "";
  const wordt = herkomstNaAanpassing({ tekst: def?.tekst ?? "", herkomst: def?.herkomst ?? null }, definitie);
  const concept = akkoord.groepen.map(akkoordLabel).filter((l) => l.concept);
  const redenen = [...new Set(concept.flatMap((l) => l.redenen))];

  /** Een besluit op de gekozen passages; daarna herladen (de pagina tekent de nieuwe stand). */
  async function voer<T>(actie: () => Promise<T>, na?: (uit: T) => void) {
    setFout(null);
    setMelding(null);
    setBezig(true);
    try {
      const uit = await actie();
      onGewijzigd();
      if (na) na(uit);
      else await onHerlaad();
    } catch (e) {
      // Een tweede akkoord (dubbelklik, ander tabblad): het begrip bestaat al.
      const begrippen = isApiError(e) ? (e.data?.begrippen as Record<string, string> | undefined) : undefined;
      const bestaand = begrippen && Object.values(begrippen).find(Boolean);
      if (bestaand) {
        setMelding({ tekst: "Dit voorstel is al een begrip geworden.", begripId: bestaand });
        await onHerlaad();
      } else setFout(foutTekst(e));
    } finally {
      setBezig(false);
    }
  }

  function maak() {
    if (!n) return setFout("Kies minstens één passage.");
    if (!naam.trim()) return setFout("Geef het begrip een naam.");
    const aanpassing = aanpassingUit(
      { definitie: def?.tekst ?? "", context: "" },
      { definitie, context: "" },
    );
    const invoer = {
      ...akkoordVoor(akkoord.groepen, gekozen, naam, { aanpassing, definitieVan: van || undefined }),
      ...(akkoord.kandidaat_ids.length ? { kandidaat_ids: akkoord.kandidaat_ids } : {}),
    };
    void voer(() => akkoordGroep(werkgebiedId, invoer), (uit) => router.push(begripPad(werkgebiedId, uit.begrip.id)));
  }

  const ledenVan = (g: Betekenisgroep) => g.leden.map((l) => l.element_id).filter((e) => gekozen.has(e));
  const koppel = (begripId: string) => voer(async () => {
    for (const g of akkoord.groepen) await koppelGroep(werkgebiedId, g.id, begripId, ledenVan(g), true);
  }, () => router.push(begripPad(werkgebiedId, begripId)));
  const besluitAlle = (soort: "afwijzen" | "parkeren" | "heropenen", groepen: Betekenisgroep[], reden?: string) =>
    voer(async () => { for (const g of groepen) await besluitGroep(werkgebiedId, g.id, soort, reden); });
  const zet = (sleutels: string[], aan: boolean) => setGekozen((s) => {
    const nieuw = new Set(s);
    for (const k of sleutels) { if (aan) nieuw.add(k); else nieuw.delete(k); }
    return nieuw;
  });
  const uitleg = [...new Set(term.open.flatMap((g) => g.uitleg))];
  const conflicten = term.open.reduce((s, g) => s + g.conflicten.length, 0);

  return (
    <div className="space-y-4">
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {melding && (
        <Melding type="uitleg" compact>
          {melding.tekst}
          {melding.begripId && <>{" "}<Link href={begripPad(werkgebiedId, melding.begripId)} className="focus-ring rounded text-lint underline">Open het begrip</Link></>}
        </Melding>
      )}

      <Kaart titel="Passages">
        <div role="group" aria-label={`Passages met “${term.naam}”`} className="space-y-3">
          <BronBoom boom={boom} label={`Passages met “${term.naam}” per regeling`}
            bladAttrs={(b) => ({ "data-passage": b.data.p.element_id })}
            vinkjes={{ gekozen, onZet: zet, naam: (b) => `Neem “${b.data.p.tekst}” mee (${b.data.p.vindplaats})` }}
            renderBlad={(b) => <PassageBlad item={b.data} label={b.label} />} />
          {(uitleg.length > 0 || conflicten > 0 || term.vragenBinnen.length > 0) && (
            <details className="text-xs text-muted">
              <summary className="focus-ring cursor-pointer rounded">Waarom stelt Lex dit voor?</summary>
              <ul className="mt-1 space-y-0.5 pl-4">
                {uitleg.map((u) => <li key={u}>{u}</li>)}
                {term.vragenBinnen.length > 0 && (
                  <li>{telling(term.vragenBinnen.length, "twijfelvraag", "twijfelvragen")} tussen deze passages; met één begrip zijn ze beantwoord.</li>
                )}
                {conflicten > 0 && <li className="text-aandacht-geel-tekst">Er is ook bewijs dat niet alles hetzelfde betekent ({conflicten}); beoordeel de passages zelf.</li>}
              </ul>
            </details>
          )}
        </div>
      </Kaart>

      <Kaart titel="Het begrip">
        <div className="space-y-3 text-sm" data-term-begrip>
          <label className="block">
            <span className="text-xs text-muted">Naam</span>
            <Input value={naam} maxLength={200} onChange={(e) => setNaam(e.target.value)} />
          </label>
          {metDefinitie.length > 1 && (
            <fieldset className="space-y-1">
              <legend className="text-xs text-muted">Definitie uit</legend>
              {metDefinitie.map((g) => {
                const d = groepDefinitie(g)!;
                return (
                  <label key={g.id} className="flex items-start gap-1.5 text-xs">
                    <input type="radio" name="definitie-van" checked={van === g.id} className="focus-ring mt-0.5 accent-lint"
                      onChange={() => { setDefinitieVan(g.id); setDefinitieTekst(null); }} />
                    <span>{d.vindplaats || g.leden[0]?.vindplaats} ({HERKOMST_LABEL[d.herkomst]}): {d.tekst}</span>
                  </label>
                );
              })}
              <label className="flex items-center gap-1.5 text-xs">
                <input type="radio" name="definitie-van" checked={!van} className="focus-ring accent-lint"
                  onChange={() => { setDefinitieVan(""); setDefinitieTekst(null); }} />
                Geen definitie overnemen
              </label>
            </fieldset>
          )}
          <label className="block">
            <span className="text-xs text-muted">
              Definitie{def ? ` – ${def.herkomst === "letterlijk" ? "brondefinitie" : HERKOMST_LABEL[def.herkomst]}${def.vindplaats ? ` (${def.vindplaats})` : ""}` : ""}
            </span>
            <textarea value={definitie} rows={3} maxLength={8000} onChange={(e) => setDefinitieTekst(e.target.value)}
              placeholder="Nog geen definitie: vul hem nu in, of later op de begripskaart"
              className="focus-ring mt-0.5 w-full rounded-button border border-line bg-paper px-2 py-1 text-sm text-ink" />
          </label>
          {wordt && definitie.trim() && (
            <p className="text-xs text-muted" data-herkomst-wordt={wordt}>Herkomst: {HERKOMST_LABEL[wordt]}</p>
          )}
          {def && def.fragmenten.length > 0 && (
            <details className="text-xs text-muted">
              <summary className="focus-ring cursor-pointer rounded">
                Rust op {telling(def.fragmenten.length, "passage", "passages")} uit de bron
              </summary>
              <ul className="mt-1 space-y-0.5 pl-4">{def.fragmenten.map((f) => <li key={f.id}>“{f.tekst}”</li>)}</ul>
            </details>
          )}
          {defGroep?.kaart?.motivatie && <p className="text-xs text-muted">Toelichting van Lex: {defGroep.kaart.motivatie}</p>}
          {punten.length > 0 && (
            <ul className="space-y-0.5 text-xs text-aandacht-geel-tekst" aria-label="Aandachtspunten van Lex">
              {punten.map((a) => <li key={a}>{a}</li>)}
            </ul>
          )}
          {redenen.length > 0 && (
            <div className="rounded-kaart border border-aandacht-geel-rand bg-aandacht-geel-bg/40 px-2 py-1.5 text-xs text-ink">
              Het begrip blijft eerst een concept:
              <ul className="mt-0.5 list-disc pl-4">{redenen.map((r) => <li key={r}>{r}</li>)}</ul>
              Op de begripskaart los je dat op en accordeer je.
            </div>
          )}
        </div>
      </Kaart>

      {term.vragenBuiten.length > 0 && (
        <Kaart titel={`Hoort het bij een andere term? (${term.vragenBuiten.length})`}>
          <ul className="divide-y divide-line" aria-label="Vragen naar andere termen">
            {term.vragenBuiten.map((v) => (
              <VraagRegel key={v.kandidaat_id} vraag={v} data={data} bezig={bezig}
                onApart={() => voer(() => beantwoordVraag(werkgebiedId, data.run!.id, v.kandidaat_id, "apart"))}
                onSamen={(naamSamen) => voer(() => akkoordGroep(werkgebiedId, samenAkkoord(v, data.groepen, data.passages, naamSamen)),
                  (uit) => router.push(begripPad(werkgebiedId, uit.begrip.id)))} />
            ))}
          </ul>
        </Kaart>
      )}

      {term.besloten.length > 0 && (
        <details className="text-sm">
          <summary className="focus-ring cursor-pointer rounded text-sm font-semibold text-lint">Al besloten ({term.besloten.length})</summary>
          <ul className="mt-2 space-y-1 text-xs text-ink">
            {term.besloten.map((g) => (
              <li key={g.id}>
                {BESLUIT_LABEL[g.besluit]} · {telling(g.leden.length + (g.afgehandeld ?? 0), "passage", "passages")}{g.reden ? ` · ${g.reden}` : ""}
                {g.begrip_id && <>{" · "}<Link href={begripPad(werkgebiedId, g.begrip_id)} className="focus-ring rounded text-lint underline">begrip openen</Link></>}
              </li>
            ))}
          </ul>
        </details>
      )}

      {items.length > 0 && (
        <ActieBalk aantal={n} bezig={bezig} lijktOp={term.lijktOp} geparkeerd={geparkeerd.length > 0}
          later={akkoord.groepen.some((g) => g.besluit === "open")} geenBegrip={geenBegrip} onGeenBegripOpen={setGeenBegrip}
          onMaak={maak} onKoppel={(b) => void koppel(b)}
          onLater={() => void besluitAlle("parkeren", akkoord.groepen.filter((g) => g.besluit === "open"))}
          onHeropenen={() => void besluitAlle("heropenen", geparkeerd)}
          onGeenBegrip={(reden) => { setGeenBegrip(false); void besluitAlle("afwijzen", akkoord.groepen, reden); }}
          onWis={() => setGekozen(new Set())} />
      )}
    </div>
  );
}

function PassageBlad({ item: { p, g }, label }: { item: Item; label: string }) {
  const onbeoordeeld = p.annotatie_beoordeeld === false || (p.annotatie_beoordeeld === undefined && p.review_status === "voorgesteld");
  return (
    <div className="text-sm">
      <span className="mr-1 text-xs text-muted">{label}</span>
      <span className={`mr-1 inline-flex rounded-full border px-1.5 text-[10px] ${jasStyle(p.jas_klasse)}`}>{klasseLabel(p.jas_klasse)}</span>
      <span className="text-ink">“{p.tekst}”</span>
      <span className="text-xs text-muted">
        {g.besluit === "geparkeerd" && " · voor later bewaard"}
        {g.aandacht === "geel" && <span className="text-aandacht-geel-tekst"> · {AANDACHT_LABEL.geel}</span>}
        {g.door === "model" && " · samengevoegd op advies van Lex"}
        {onbeoordeeld && <span className="text-aandacht-geel-tekst"> · annotatie nog niet beoordeeld</span>}
        {" · "}<Link href={elementPad(p.element_id)} aria-label={`Element: ${p.tekst}`} className="focus-ring rounded text-lint underline">element</Link>
      </span>
    </div>
  );
}

/** Een twijfelvraag met *Samen* (één begrip, met een naam) of *Apart*; ook voor de losse vragen in het kader. */
export function VraagRegel({ vraag: v, data, bezig, onApart, onSamen }: {
  vraag: TwijfelVraag;
  data: GroepenAntwoord;
  bezig: boolean;
  onApart: () => void;
  onSamen: (naam: string) => void;
}) {
  const van = passageTekst(v.van, data.passages, data.groepen);
  const naar = passageTekst(v.naar, data.passages, data.groepen);
  const zin = `Horen ${van} en ${naar} bij hetzelfde begrip?`;
  const oordeel = data.verdieping?.oordelen?.[v.kandidaat_id];
  const [naam, setNaam] = useState<string | null>(null);
  return (
    <li className="space-y-1.5 py-2.5 text-sm" data-term-vraag={v.kandidaat_id}>
      <p className="text-ink">{zin}</p>
      {oordeel && !oordeel.reden && (
        <p className="text-xs text-ink" data-advies={oordeel.oordeel}>
          <span className="font-medium">Advies van Lex: {OORDEEL_LABEL[oordeel.oordeel]}</span>{oordeel.motivatie && <> – {oordeel.motivatie}</>}
        </p>
      )}
      {v.uitleg.map((u) => <p key={u} className="text-xs text-muted">{u}</p>)}
      {naam !== null ? (
        <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={(e) => { e.preventDefault(); if (naam.trim()) onSamen(naam); }}>
          <Input autoFocus value={naam} maxLength={200} onChange={(e) => setNaam(e.target.value)}
            aria-label={`Naam van het begrip uit: ${zin}`} className="sm:w-56" />
          <Button type="submit" size="sm" disabled={bezig || !naam.trim()}>Eén begrip maken</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setNaam(null)}>Annuleren</Button>
        </form>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button size="sm" variant="secondary" disabled={bezig} aria-label={`Samen: ${zin}`}
            onClick={() => setNaam(data.groepen.find((g) => g.leden.some((l) => l.element_id === v.van))?.voorstel.naam ?? "")}>
            Samen
          </Button>
          <Button size="sm" variant="ghost" disabled={bezig} aria-label={`Apart: ${zin}`} onClick={onApart}>Apart</Button>
        </div>
      )}
    </li>
  );
}

function ActieBalk({ aantal, bezig, lijktOp, later, geparkeerd, geenBegrip, onGeenBegripOpen, onMaak, onKoppel, onLater,
  onHeropenen, onGeenBegrip, onWis }: {
  aantal: number; bezig: boolean; lijktOp: Term["lijktOp"]; later: boolean; geparkeerd: boolean; geenBegrip: boolean;
  onGeenBegripOpen: (open: boolean) => void; onMaak: () => void; onKoppel: (begripId: string) => void; onLater: () => void;
  onHeropenen: () => void; onGeenBegrip: (reden: string) => void; onWis: () => void;
}) {
  const [reden, setReden] = useState("");
  const redenRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (geenBegrip) redenRef.current?.focus();
  }, [geenBegrip]);
  const n = `(${aantal})`;
  const uit = bezig || aantal === 0;
  return (
    <div data-actiebalk className="sticky bottom-0 z-10 -mx-1 rounded-kaart border border-line bg-paper p-3 shadow-kaart">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <span className="text-sm font-medium text-ink">{bezig ? "Bezig…" : `${telling(aantal, "passage", "passages")} gekozen`}</span>
        <Button size="sm" disabled={uit} onClick={onMaak}>Eén begrip maken {n}</Button>
        {lijktOp.map((b) => (
          <Button key={b.begrip_id} size="sm" variant="secondary" disabled={uit} onClick={() => onKoppel(b.begrip_id)}>
            Koppelen aan {b.naam} {n}
          </Button>
        ))}
        {later && <Button size="sm" variant="ghost" disabled={uit} onClick={onLater}>Later</Button>}
        {geparkeerd && <Button size="sm" variant="ghost" disabled={uit} onClick={onHeropenen}>Heropenen</Button>}
        <Button size="sm" variant="ghost" disabled={uit} aria-expanded={geenBegrip} onClick={() => onGeenBegripOpen(!geenBegrip)}>
          Geen begrip…
        </Button>
        <button type="button" onClick={onWis} className="focus-ring rounded text-xs text-muted underline sm:ml-auto">Keuze wissen</button>
      </div>
      {geenBegrip && (
        <form className="mt-2 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => { e.preventDefault(); if (reden.trim()) { onGeenBegrip(reden.trim()); setReden(""); } }}>
          <label className="sr-only" htmlFor="reden-geen-begrip">Reden om geen begrip te maken</label>
          <Input id="reden-geen-begrip" ref={redenRef} value={reden} onChange={(e) => setReden(e.target.value)}
            placeholder="Waarom is dit geen begrip? (geldt voor de hele voorstellen van de gekozen passages)" maxLength={2000}
            onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onGeenBegripOpen(false); } }} />
          <Button type="submit" size="sm" disabled={bezig || !reden.trim()} className="w-full sm:w-auto">Geen begrip</Button>
        </form>
      )}
    </div>
  );
}
