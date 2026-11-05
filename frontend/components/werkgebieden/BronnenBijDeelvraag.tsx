"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { MeerMenu, MenuKeuze, MenuVerwijder } from "@/components/ui/MeerMenu";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { KnoopTekst } from "@/components/graaf/KnoopTekst";
import { PeildatumRegel } from "@/components/werkgebieden/Peildatum";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedProject";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { besluitBronselectie, foutTekst, haalBronselectie, verwijderBron, wijzigBron, type BronselectieBesluit } from "@/lib/api";
import { haalNodeWeergave, type NodeWeergave } from "@/lib/annotatieNode";
import {
  BRONSELECTIE_GEWIJZIGD, BEWIJS_LABEL, STAND_LABEL, zoekvraagZin, meldBronselectieGewijzigd, bronnenZin, deelvraagStand, slotZin, voortgangZin, zoekBeperkingen,
  type BronselectieOverzicht, type DeelvraagSelectie, type KandidaatHier,
} from "@/lib/bronselectie";
import { bepalingEnRegeling, ookBijZin } from "@/lib/bronnenPerDeelvraag";
import type { BronRol, Bronselectie, Werkgebied } from "@/lib/types";
import { ROL_LABEL, isRevisieConflict } from "@/lib/werkgebied";
import { bronPad, deelvraagPad, historiePad, selectieStand, voorstellenPad, type Werkvoorraad } from "@/lib/werkgebiedPaden";

/** Beheer over de bronselecties, als de schil het werkgebied en `muteer` heeft (de tab Bronnen, de
 *  deelvraagpagina): rol wijzigen en verwijderen achter ⋯, de stand van de annotatie, en *Zonder deelvraag*. */
export interface BronBeheer {
  wg: Werkgebied;
  muteer: Mutatie;
  laad: () => Promise<void>;
  werkvoorraad?: Werkvoorraad | null;
}

/** De bronnen per deelvraag (spoor L): één inhoud voor de tab Bronnen, de deelvraagpagina en het paneel naast het
 *  gesprek. Per deelvraag een `Groep` met de voortgang, de bronnen (*Geselecteerd* of *Context*), de voorstellen
 *  van Lex met hun besluiten (opnemen, uitsluiten met reden, heropenen), de onderzoekspunten en wat het
 *  beoordelen nog tegenhoudt; erboven wat er over het zoeken te zeggen is, eronder de slotzin – nooit "volledig".
 *
 *  - `deelvraagId` toont één deelvraag (de deelvraagpagina);
 *  - `inGesprek` is het paneel: de deelvraag waar het gesprek staat volledig, de andere als kop met *Ga verder
 *    met deelvraag n*;
 *  - `filter` (de tab Bronnen: zoeken, rol) laat alleen de passende bronnen zien. */
export function BronnenBijDeelvraag({ werkgebiedId, revisie = 0, deelvraagId, inGesprek = false, huidig: huidigId,
  beheer, filter, versie = 0, onKlaar, klaarVoor }: {
  werkgebiedId: string;
  /** Laadt opnieuw bij een nieuwe revisie van het werkgebied. */
  revisie?: number;
  deelvraagId?: string;
  inGesprek?: boolean;
  /** De deelvraag waar het gesprek staat. */
  huidig?: string;
  beheer?: BronBeheer;
  filter?: { past: (s: Bronselectie | undefined, label: string, rol: BronRol) => boolean; actief: boolean };
  versie?: number;
  /** Naast het gesprek: *Klaar met deze deelvraag* stuurt de actie van het open kaartje (alleen bij `klaarVoor`). */
  onKlaar?: (deelvraagId: string) => void;
  klaarVoor?: string;
}) {
  const [o, setO] = useState<BronselectieOverzicht | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [poging, setPoging] = useState(0);
  // Een besluit elders (het kaartje, een bepaling die Lex in het gesprek toevoegde): opnieuw laden.
  useEffect(() => {
    const bij = (e: Event) => { if ((e as CustomEvent).detail === werkgebiedId) setPoging((p) => p + 1); };
    window.addEventListener(BRONSELECTIE_GEWIJZIGD, bij);
    return () => window.removeEventListener(BRONSELECTIE_GEWIJZIGD, bij);
  }, [werkgebiedId]);
  useEffect(() => {
    let levend = true;
    haalBronselectie(werkgebiedId).then((x) => { if (levend) { setO(x); setFout(null); } })
      .catch((e) => { if (levend) setFout(foutTekst(e)); });
    return () => { levend = false; };
  }, [werkgebiedId, revisie, poging, versie]);

  const perSelectie = useMemo(() => new Map((beheer?.werkvoorraad?.selecties ?? []).map((s) => [s.id, s])), [beheer?.werkvoorraad]);
  const selecties = useMemo(() => new Map((beheer?.wg.bronnen ?? []).map((s) => [s.id, s])), [beheer?.wg.bronnen]);

  async function beslis(d: DeelvraagSelectie, k: KandidaatHier, besluit: BronselectieBesluit) {
    setMelding(null);
    try {
      setO(await besluitBronselectie(werkgebiedId, d.id, k.id, besluit));
      meldBronselectieGewijzigd(werkgebiedId);
      // Opnemen maakt een bronselectie: het werkgebied zelf veranderde ook.
      if (besluit.besluit === "opnemen") await beheer?.laad();
    } catch (e) {
      // Een 412: iemand anders wijzigde het werkgebied. Opnieuw laden, niet stil opnieuw uitvoeren.
      if (isRevisieConflict(e)) {
        setMelding("Iemand anders wijzigde het werkgebied net; hieronder de stand van nu.");
        setPoging((p) => p + 1);
        await beheer?.laad();
      } else setMelding(foutTekst(e, "Het besluit is niet vastgelegd."));
    }
  }

  const links = !inGesprek && (
    <p className="text-xs">
      <Link href={historiePad(werkgebiedId)} className="focus-ring rounded font-medium text-lint hover:underline">Historie en besluiten</Link>
      {" · "}
      <Link href={voorstellenPad(werkgebiedId)} className="focus-ring rounded font-medium text-lint hover:underline">
        Bronverkenner – alles wat Lex vond, met bewijs
      </Link>
    </p>
  );

  // Zonder de stand per deelvraag staan op de tab en de deelvraagpagina toch de bronnen van het werkgebied: een
  // storing kost de indeling, niet de lijst.
  if (fout && beheer && !deelvraagId) {
    const bronnen = beheer.wg.bronnen.filter((s) => !filter?.actief || filter.past(s, s.label, s.rol));
    return (
      <div data-bronnen-bij-deelvraag className="space-y-4 text-sm text-ink">
        <PeildatumRegel werkgebiedId={werkgebiedId} revisie={revisie} />
        {beheer.wg.bronnen.length > 0 && (
          <Melding type="uitleg" compact>
            De indeling per deelvraag is nu niet te laden; hieronder de bronnen van het werkgebied.{" "}
            <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => setPoging((p) => p + 1)}>
              Opnieuw proberen
            </button>
          </Melding>
        )}
        <Groep kop="Bronnen" telling={bronnenZin(bronnen.length)} label="Bronnen" data-bronnen-groep="alle"
          leeg={beheer.wg.bronnen.length ? "Geen bronnen gevonden."
            : "Nog geen bronnen. Neem een bepaling op, of bepaal ze per deelvraag met Lex in het gesprek."}>
          {bronnen.map((s) => (
            <BronRij key={s.id} werkgebiedId={werkgebiedId} bronIri={s.bron_iri} label={s.label || s.bron_iri} rol={s.rol}
              selectie={s} beheer={beheer} ook={[]}
              stand={s.rol === "analyseren" ? selectieStand(perSelectie.get(s.id))?.tekst ?? "" : ""} />
          ))}
        </Groep>
        {links}
      </div>
    );
  }
  if (fout) {
    return (
      <Melding type="fout" titel="De bronnen per deelvraag konden niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => setPoging((p) => p + 1)}>
          Opnieuw proberen
        </button>
      </Melding>
    );
  }
  if (!o) return <SkeletonCard regels={4} />;

  const beperkingen = zoekBeperkingen(o.zoekdekking);
  const huidig = huidigId || o.actief || "";
  const vragen = o.deelvragen.filter((d) => !deelvraagId || d.id === deelvraagId);
  // Hoe vaak een selectie bij een andere deelvraag hoort ("ook bij deelvraag 2").
  const bij = new Map<string, number[]>();
  o.deelvragen.forEach((d) => d.bronnen.forEach((b) => bij.set(b.selectie_id, [...(bij.get(b.selectie_id) ?? []), d.nr])));
  const gekoppeld = new Set(bij.keys());
  const zonder = deelvraagId || inGesprek || o.modus === "analysevraag" ? []
    : (beheer?.wg.bronnen ?? []).filter((s) => !gekoppeld.has(s.id) && (!filter?.actief || filter.past(s, s.label, s.rol)));

  return (
    <div data-bronnen-bij-deelvraag className="space-y-6 text-sm text-ink">
      <PeildatumRegel werkgebiedId={werkgebiedId} revisie={revisie} />
      {!deelvraagId && <p className="text-xs text-muted" data-bronselectie-voortgang>{voortgangZin(o)}</p>}
      {beperkingen.length > 0 && !deelvraagId && (
        <Melding type="waarschuwing" compact titel="Over het zoeken">
          <span data-zoekbeperking>{beperkingen.join(" ")}</span>
        </Melding>
      )}
      {melding && <Melding type="waarschuwing" compact>{melding}</Melding>}

      {vragen.map((d) => {
        const kort = inGesprek && !deelvraagId && d.id !== huidig && o.modus === "deelvragen";
        const bronnen = d.bronnen.filter((b) => !filter?.actief || filter.past(selecties.get(b.selectie_id), b.label, b.rol));
        if (filter?.actief && bronnen.length === 0) return null;
        // Bij een filter (zoeken, rol) gaat het om de bronnen; de voorstellen staan er dan niet bij.
        const voorstellen = filter?.actief ? [] : d.kandidaten.filter((k) => k.stand !== "opgenomen");
        const v = deelvraagStand(d);
        const titel = o.modus === "analysevraag" ? "De analysevraag" : deelvraagId ? "Bronnen" : `${d.nr}. ${d.vraag}`;
        const telling = [bronnenZin(d.bronnen.length), d.telling.voorgesteld ? `${d.telling.voorgesteld} ter beoordeling` : ""]
          .filter(Boolean).join(" · ");
        return (
          <div key={d.id} className="space-y-2" data-bronselectie-deelvraag={d.id} data-bronnen-groep={d.id}
            data-voortgang={d.status} data-huidig={d.id === huidig || undefined}>
            <Groep
              kop={o.modus === "deelvragen" && !deelvraagId && !inGesprek
                ? <Link href={deelvraagPad(o.werkgebied_id, d.id)} className="focus-ring rounded hover:underline">{titel}</Link> : titel}
              telling={telling}
              status={v && <StatusLabel toon={v.toon}>{v.label}</StatusLabel>}
              sub={!kort && d.opnieuw_bekijken
                ? "De analysevraag, de afbakening of deze deelvraag is veranderd sinds de afronding; bekijk of de besluiten nog kloppen."
                : undefined}
              label={o.modus === "analysevraag" ? "Bronnen bij de analysevraag" : `Bronnen bij deelvraag ${d.nr}`}
              leeg={kort ? undefined : `Er hoort nog geen bron bij ${o.modus === "analysevraag" ? "de analysevraag" : "deze deelvraag"}. `
                + "Bepaal de bronnen met Lex in het gesprek, of laat Lex er een toevoegen."}>
              {!kort && bronnen.map((b) => {
                const sel = selecties.get(b.selectie_id);
                return (
                  <BronRij key={b.selectie_id} werkgebiedId={o.werkgebied_id} bronIri={b.bron_iri} label={b.label || b.bron_iri}
                    rol={b.rol} selectie={sel} beheer={beheer}
                    ook={(bij.get(b.selectie_id) ?? []).filter((n) => n !== d.nr)}
                    stand={b.rol === "analyseren" && sel ? selectieStand(perSelectie.get(sel.id))?.tekst ?? "" : ""}
                    inGesprek={inGesprek} />
                );
              })}
              {!kort && voorstellen.map((k) => <Voorstel key={k.id} o={o} d={d} k={k} beslis={beslis} inGesprek={inGesprek} />)}
            </Groep>
            {/* Zelf een bepaling toevoegen gaat via het gesprek (*Noem een bepaling* boven het invoerveld, of
                typen op het kaartje): zoeken in de graaf hoort niet bij het artefact. */}
            {inGesprek && !kort && onKlaar && klaarVoor === d.id && d.status !== "voorlopig_afgerond" && d.status !== "beoordeeld" && (
              <div className="flex sm:justify-end" data-paneel-acties={d.id}>
                <Button size="sm" onClick={() => onKlaar(d.id)} className="w-full sm:w-auto" data-paneel-klaar>
                  Klaar met deze deelvraag
                </Button>
              </div>
            )}
            {kort && (
              <VraagLexKnop alleenInGesprek naam={`Ga verder met deelvraag ${d.nr}`} tekst={`Ga verder met deelvraag ${d.nr}`}
                onderwerp={{ soort: "deelvraag", werkgebied_id: o.werkgebied_id, id: d.id, label: d.vraag }} />
            )}
            {!kort && d.open_punten.length > 0 && (
              <div className="rounded-lg border border-aandacht-geel-rand bg-aandacht-geel-bg/40 px-3.5 py-2.5">
                <p className="text-xs font-semibold text-aandacht-geel-tekst">Onderzoekspunten</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm" data-onderzoekspunten>
                  {d.open_punten.map((p) => <li key={p.tekst}>{p.tekst}</li>)}
                </ul>
              </div>
            )}
            {!kort && !d.beoordelen.mag && d.status !== "niet_gestart" && (
              <p className="text-xs text-muted">Nog niet te beoordelen: {d.beoordelen.redenen.join(" ")}</p>
            )}
          </div>
        );
      })}

      {zonder.length > 0 && (
        <Groep kop="Zonder deelvraag" data-bronnen-groep="zonder" telling={bronnenZin(zonder.length)}
          sub="Bij geen enkele deelvraag gekoppeld, bijvoorbeeld een definitie of context." label="Bronnen zonder deelvraag">
          {zonder.map((s) => (
            <BronRij key={s.id} werkgebiedId={o.werkgebied_id} bronIri={s.bron_iri} label={s.label || s.bron_iri} rol={s.rol}
              selectie={s} beheer={beheer} ook={[]}
              stand={s.rol === "analyseren" ? selectieStand(perSelectie.get(s.id))?.tekst ?? "" : ""} />
          ))}
        </Groep>
      )}

      {!deelvraagId && <p className="text-xs text-muted" data-bronselectie-slot>{slotZin(o)}</p>}
      {links}
    </div>
  );
}


/** De wettekst van een bepaling, uitgeklapt naast het gesprek: lezen zonder de werkplek te verlaten. De pagina van
 *  de bepaling blijft één klik verder. */
function Wettekst({ bronIri, werkgebiedId }: { bronIri: string; werkgebiedId: string }) {
  const [view, setView] = useState<NodeWeergave | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  useEffect(() => {
    let levend = true;
    haalNodeWeergave({ bron_iri: bronIri }).then((v) => { if (levend) setView(v); })
      .catch((e) => { if (levend) setFout(foutTekst(e, "De tekst kon niet worden geladen.")); });
    return () => { levend = false; };
  }, [bronIri]);
  const actueel = (view?.elementen ?? []).filter((e) => !e.verouderd && e.lifecycle !== "rejected");
  return (
    <div className="mx-4 mb-2 rounded-kaart border border-line bg-surface/60 px-3 py-2.5" data-wettekst={bronIri}>
      {fout ? <p className="text-sm text-muted">{fout}</p>
        : view ? <KnoopTekst segmenten={view.segmenten} elementen={actueel} kiesbaar={() => false} onKies={() => {}} />
          : <p className="text-sm text-muted">Tekst laden…</p>}
      <Link href={bronPad(bronIri, werkgebiedId)} className="focus-ring mt-2 inline-block rounded text-xs font-medium text-lint hover:underline">
        Open de bepaling
      </Link>
    </div>
  );
}

/** Eén bron als rij (de `itemrow` van de mock-up): de bepaling als titel, de regeling en wat ze hier doet eronder,
 *  de status rechts; de rij opent de pagina van de bepaling. Met beheer staan rol en verwijderen achter ⋯. */
function BronRij({ werkgebiedId, bronIri, label, rol, selectie, beheer, ook, stand, inGesprek = false }: {
  inGesprek?: boolean;
  werkgebiedId: string;
  bronIri: string;
  label: string;
  rol: BronRol;
  selectie?: Bronselectie;
  beheer?: BronBeheer;
  ook: number[];
  stand: string;
}) {
  const [tekst, setTekst] = useState(false);
  const { bepaling, regeling } = bepalingEnRegeling(label);
  const sub = [regeling, ROL_LABEL[rol].toLowerCase(), stand.toLowerCase(), ookBijZin(ook)].filter(Boolean).join(" · ");
  const s = selectie;
  return (
    <GroepRij data-bron={s?.id} data-bron-hier={bronIri} titel={bepaling} sub={sub}
      {...(inGesprek ? { uitklap: { open: tekst, onWissel: () => setTekst((t) => !t), label: `Tekst van ${label}` } }
        : { href: bronPad(bronIri, werkgebiedId) })}
      status={rol === "context" ? <StatusLabel>Context</StatusLabel> : <StatusLabel toon="groen">Geselecteerd</StatusLabel>}
      eind={beheer && s && (
        <MeerMenu label={`Rol en verwijderen: ${label}`}>
          {(sluit) => {
            const zetRol = (nieuw: BronRol) => {
              sluit();
              if (nieuw === s.rol) return;
              void beheer.muteer((r) => wijzigBron(beheer.wg.id, s.id, { verwachte_revisie: r, rol: nieuw }), {
                gelukt: `Rol gewijzigd naar ${ROL_LABEL[nieuw].toLowerCase()}.`,
              });
            };
            return (<>
              {(["analyseren", "context"] as const).map((r) => (
                <MenuKeuze key={r} gekozen={s.rol === r} onClick={() => zetRol(r)}>{ROL_LABEL[r]}</MenuKeuze>
              ))}
              <MenuVerwijder titel="Haalt de bepaling uit dit werkgebied; de bepaling en haar annotaties blijven bestaan."
                onBevestig={async () => {
                  await beheer.muteer((r) => verwijderBron(beheer.wg.id, s.id, r), {
                    gelukt: "Uit het werkgebied verwijderd. De bepaling en haar annotaties blijven bestaan.",
                  });
                }}>
                Verwijderen uit werkgebied
              </MenuVerwijder>
            </>);
          }}
        </MeerMenu>
      )}
      onder={tekst && <Wettekst bronIri={bronIri} werkgebiedId={werkgebiedId} />} />
  );
}

/** Eén voorstel van Lex bij één deelvraag: het soort bewijs in gewone woorden en de besluiten. Uitsluiten vraagt een
 *  reden en geldt voor deze deelvraag; een besluit voor het hele werkgebied (`overal`) heropen je met dezelfde
 *  reikwijdte. */
function Voorstel({ o, d, k, beslis, inGesprek = false }: {
  inGesprek?: boolean;
  o: BronselectieOverzicht;
  d: DeelvraagSelectie;
  k: KandidaatHier;
  beslis: (d: DeelvraagSelectie, k: KandidaatHier, b: BronselectieBesluit) => Promise<void>;
}) {
  const [uitsluiten, setUitsluiten] = useState(false);
  const [tekst, setTekst] = useState(false);
  const [reden, setReden] = useState("");
  const [bezig, setBezig] = useState(false);
  const doe = async (b: BronselectieBesluit) => {
    setBezig(true);
    try { await beslis(d, k, b); } finally { setBezig(false); }
  };
  const { bepaling, regeling } = bepalingEnRegeling(k.label || k.bron_iri);
  const sub = [regeling, k.rol === "kern" ? "kernbepaling" : k.rol === "afhankelijkheid" ? "afhankelijkheid" : "mogelijk relevant",
    // Bij welke zoekvraag (a–d) het hoort: waarom het er staat in de termen van de methode.
    ...k.zoekvragen.map(zoekvraagZin), ...k.bewijs_soorten.map((s) => BEWIJS_LABEL[s]), k.elders_opgenomen ? "al opgenomen bij een andere deelvraag" : "",
    k.reden ? `reden: ${k.reden}` : "", k.overal ? "geldt voor het hele werkgebied" : ""].filter(Boolean).join(" · ");
  const label = k.stand === "voorgesteld" ? "Ter beoordeling" : STAND_LABEL[k.stand].charAt(0).toUpperCase() + STAND_LABEL[k.stand].slice(1);
  return (
    <GroepRij data-kandidaat-hier={k.id} data-stand={k.stand} titel={bepaling} sub={sub}
      {...(inGesprek ? { uitklap: { open: tekst, onWissel: () => setTekst((t) => !t), label: `Tekst van ${k.label || bepaling}` } }
        : { href: bronPad(k.bron_iri, o.werkgebied_id) })}
      status={<StatusLabel toon={k.stand === "voorgesteld" ? "geel" : "neutraal"}>{label}</StatusLabel>}
      onder={(<>
        {tekst && <Wettekst bronIri={k.bron_iri} werkgebiedId={o.werkgebied_id} />}
        <div className="flex flex-col gap-2 px-4 pb-3 sm:flex-row sm:items-center">
          {uitsluiten ? (
            <form className="flex w-full flex-col gap-2 sm:flex-row" onSubmit={(e) => {
              e.preventDefault();
              if (reden.trim()) void doe({ besluit: "uitsluiten", reden: reden.trim() }).then(() => setUitsluiten(false));
            }}>
              <Input autoFocus aria-label={`Waarom sluit je ${k.label} uit bij deze deelvraag?`} value={reden}
                onChange={(e) => setReden(e.target.value)} placeholder="Waarom niet bij deze deelvraag?" />
              <Button type="submit" size="xs" variant="secondary" disabled={!reden.trim() || bezig}>Uitsluiten</Button>
              <Button type="button" size="xs" variant="ghost" onClick={() => setUitsluiten(false)}>Annuleren</Button>
            </form>
          ) : k.stand !== "uitgesloten" ? (
            <>
              <Button size="xs" variant="secondary" disabled={bezig} aria-label={`Opnemen: ${k.label}`}
                onClick={() => doe({ besluit: "opnemen", verwachte_revisie: o.revisie, rol: k.rol === "kern" ? "analyseren" : "context" })}>
                Opnemen
              </Button>
              <Button size="xs" variant="secondary" disabled={bezig} aria-label={`Uitsluiten: ${k.label}`} onClick={() => setUitsluiten(true)}>
                Uitsluiten…
              </Button>
            </>
          ) : (
            <Button size="xs" variant="secondary" disabled={bezig} onClick={() => doe({ besluit: "heropenen", overal: k.overal })}>
              Heropenen
            </Button>
          )}
        </div>
      </>)} />
  );
}
