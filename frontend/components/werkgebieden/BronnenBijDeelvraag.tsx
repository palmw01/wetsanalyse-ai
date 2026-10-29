"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button, KNOP_XS } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Meer } from "@/components/ui/Icoon";
import { StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { SkeletonCard } from "@/components/ui/Skeleton";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedProject";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { besluitBronselectie, foutTekst, haalBronselectie, verwijderBron, wijzigBron, type BronselectieBesluit } from "@/lib/api";
import {
  BEWIJS_LABEL, STAND_LABEL, bronnenZin, deelvraagStand, slotZin, voortgangZin, zoekBeperkingen,
  type BronselectieOverzicht, type DeelvraagSelectie, type KandidaatHier,
} from "@/lib/bronselectie";
import { bepalingEnRegeling, ookBijZin } from "@/lib/bronnenPerDeelvraag";
import { labelVanPlaats } from "@/lib/bronPlaats";
import { usePlaatsen } from "@/lib/usePlaatsen";
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
  beheer, filter, versie = 0 }: {
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
}) {
  const [ruw, setO] = useState<BronselectieOverzicht | null>(null);
  const plaatsen = usePlaatsen([
    ...(beheer?.wg.bronnen ?? []).map((b) => b.bron_iri),
    ...(ruw?.deelvragen ?? []).flatMap((d) => [...d.bronnen, ...d.kandidaten].map((b) => b.bron_iri)),
    ...(ruw?.zonder_deelvraag ?? []).map((b) => b.bron_iri),
  ]);
  const bronNaam = (iri: string, label: string) => labelVanPlaats(plaatsen?.get(iri)) || label || iri;
  const o = ruw && { ...ruw, deelvragen: ruw.deelvragen.map((d) => ({ ...d,
    bronnen: d.bronnen.map((b) => ({ ...b, label: bronNaam(b.bron_iri, b.label) })),
    kandidaten: d.kandidaten.map((b) => ({ ...b, label: bronNaam(b.bron_iri, b.label) })),
  })) };
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [poging, setPoging] = useState(0);
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
    const bronnen = beheer.wg.bronnen.filter((s) => !filter?.actief || filter.past(s, bronNaam(s.bron_iri, s.label), s.rol));
    return (
      <div data-bronnen-bij-deelvraag className="space-y-4 text-sm text-ink">
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
            <BronRij key={s.id} werkgebiedId={werkgebiedId} bronIri={s.bron_iri} label={bronNaam(s.bron_iri, s.label)} rol={s.rol}
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
    : (beheer?.wg.bronnen ?? []).filter((s) => !gekoppeld.has(s.id) && (!filter?.actief || filter.past(s, bronNaam(s.bron_iri, s.label), s.rol)));

  return (
    <div data-bronnen-bij-deelvraag className="space-y-6 text-sm text-ink">
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
                + "Bepaal de bronnen met Lex in het gesprek, of neem een bepaling op."}>
              {!kort && bronnen.map((b) => {
                const sel = selecties.get(b.selectie_id);
                return (
                  <BronRij key={b.selectie_id} werkgebiedId={o.werkgebied_id} bronIri={b.bron_iri} label={b.label || b.bron_iri}
                    rol={b.rol} selectie={sel} beheer={beheer}
                    ook={(bij.get(b.selectie_id) ?? []).filter((n) => n !== d.nr)}
                    stand={b.rol === "analyseren" && sel ? selectieStand(perSelectie.get(sel.id))?.tekst ?? "" : ""} />
                );
              })}
              {!kort && voorstellen.map((k) => <Voorstel key={k.id} o={o} d={d} k={k} beslis={beslis} />)}
            </Groep>
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
            <BronRij key={s.id} werkgebiedId={o.werkgebied_id} bronIri={s.bron_iri} label={bronNaam(s.bron_iri, s.label)} rol={s.rol}
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

/** Eén bron als rij (de `itemrow` van de mock-up): de bepaling als titel, de regeling en wat ze hier doet eronder,
 *  de status rechts; de rij opent de pagina van de bepaling. Met beheer staan rol en verwijderen achter ⋯. */
function BronRij({ werkgebiedId, bronIri, label, rol, selectie, beheer, ook, stand }: {
  werkgebiedId: string;
  bronIri: string;
  label: string;
  rol: BronRol;
  selectie?: Bronselectie;
  beheer?: BronBeheer;
  ook: number[];
  stand: string;
}) {
  const [open, setOpen] = useState(false);
  const { bepaling, regeling } = bepalingEnRegeling(label);
  const sub = [regeling, ROL_LABEL[rol].toLowerCase(), stand.toLowerCase(), ookBijZin(ook)].filter(Boolean).join(" · ");
  const s = selectie;
  return (
    <GroepRij data-bron={s?.id} data-bron-hier={bronIri} href={bronPad(bronIri, werkgebiedId)} titel={bepaling} sub={sub}
      status={rol === "context" ? <StatusLabel>Context</StatusLabel> : <StatusLabel toon="groen">Geselecteerd</StatusLabel>}
      eind={beheer && s && (
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={`Rol en verwijderen: ${label}`}
          className="focus-ring shrink-0 rounded p-1.5 text-muted hover:bg-paper hover:text-lint">
          <Meer />
        </button>
      )}
      onder={open && beheer && s && (
        <div className="mx-2 mb-2 flex flex-col gap-2 rounded-md border border-line bg-surface p-3 sm:flex-row sm:items-center" data-bron-acties>
          <label className="text-xs text-muted" htmlFor={`rol-${s.id}`}>Rol</label>
          <Select id={`rol-${s.id}`} value={s.rol} className="sm:w-48"
            onChange={(e) => {
              const nieuw = e.target.value as BronRol;
              void beheer.muteer((r) => wijzigBron(beheer.wg.id, s.id, { verwachte_revisie: r, rol: nieuw }), {
                gelukt: `Rol gewijzigd naar ${ROL_LABEL[nieuw].toLowerCase()}.`,
              });
            }}>
            {(["analyseren", "context"] as const).map((r) => <option key={r} value={r}>{ROL_LABEL[r]}</option>)}
          </Select>
          <BevestigKnop
            bevestigTekst="Verwijderen?"
            titel="Haalt de bepaling uit dit werkgebied; de bepaling en haar annotaties blijven bestaan."
            onBevestig={async () => {
              await beheer.muteer((r) => verwijderBron(beheer.wg.id, s.id, r), {
                gelukt: "Uit het werkgebied verwijderd. De bepaling en haar annotaties blijven bestaan.",
              });
            }}
            className={`${KNOP_XS} border-line bg-paper text-muted hover:text-ink sm:ml-auto`}
            bevestigClassName="border-fout/40 text-fout">
            Verwijderen uit werkgebied
          </BevestigKnop>
        </div>
      )} />
  );
}

/** Eén voorstel van Lex bij één deelvraag: het soort bewijs in gewone woorden en de besluiten. Uitsluiten vraagt een
 *  reden en geldt voor deze deelvraag; een besluit voor het hele werkgebied (`overal`) heropen je met dezelfde
 *  reikwijdte. */
function Voorstel({ o, d, k, beslis }: {
  o: BronselectieOverzicht;
  d: DeelvraagSelectie;
  k: KandidaatHier;
  beslis: (d: DeelvraagSelectie, k: KandidaatHier, b: BronselectieBesluit) => Promise<void>;
}) {
  const [uitsluiten, setUitsluiten] = useState(false);
  const [reden, setReden] = useState("");
  const [bezig, setBezig] = useState(false);
  const doe = async (b: BronselectieBesluit) => {
    setBezig(true);
    try { await beslis(d, k, b); } finally { setBezig(false); }
  };
  const { bepaling, regeling } = bepalingEnRegeling(k.label || k.bron_iri);
  const sub = [regeling, k.rol === "kern" ? "kernbepaling" : k.rol === "afhankelijkheid" ? "afhankelijkheid" : "mogelijk relevant",
    ...k.bewijs_soorten.map((s) => BEWIJS_LABEL[s]), k.elders_opgenomen ? "al opgenomen bij een andere deelvraag" : "",
    k.reden ? `reden: ${k.reden}` : "", k.overal ? "geldt voor het hele werkgebied" : ""].filter(Boolean).join(" · ");
  const label = k.stand === "voorgesteld" ? "Ter beoordeling" : STAND_LABEL[k.stand].charAt(0).toUpperCase() + STAND_LABEL[k.stand].slice(1);
  return (
    <GroepRij data-kandidaat-hier={k.id} data-stand={k.stand} href={bronPad(k.bron_iri, o.werkgebied_id)} titel={bepaling} sub={sub}
      status={<StatusLabel toon={k.stand === "voorgesteld" ? "geel" : "neutraal"}>{label}</StatusLabel>}
      onder={(
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
      )} />
  );
}
