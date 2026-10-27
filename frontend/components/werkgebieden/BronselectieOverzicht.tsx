"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Lijst, LijstRij, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { besluitBronselectie, foutTekst, haalBronselectie, type BronselectieBesluit } from "@/lib/api";
import {
  BEWIJS_LABEL, STAND_LABEL, VOORTGANG_LABEL, slotZin, voortgangToon, voortgangZin, zoekBeperkingen,
  type BronselectieOverzicht as Overzicht, type DeelvraagSelectie, type KandidaatHier,
} from "@/lib/bronselectie";
import { isRevisieConflict } from "@/lib/werkgebied";
import { bronPad, deelvraagPad, historiePad, voorstellenPad } from "@/lib/werkgebiedPaden";

/** De bronselectie per deelvraag (spoor J): per deelvraag de voortgang, de bronnen met hun rol bij díé
 *  deelvraag, de voorstellen van Lex met hun stand en het soort bewijs, en de onderzoekspunten; erboven wat er
 *  over het zoeken te zeggen is, eronder de slotzin – nooit "volledig".
 *
 *  Eén inhoud, twee schillen: het paneel naast het gesprek (`inGesprek`: de deelvraag waar het gesprek staat
 *  open, en per deelvraag *Ga hiermee verder*, dat haar als onderwerp klaarzet) en de pagina Bronselectie. De
 *  stappen – openen, afronden, beoordelen – zet Lex in het gesprek; hier staan alleen de besluiten over één
 *  voorstel bij één deelvraag. `versie` laadt opnieuw (een nieuwe beurt van Lex). */
export function BronselectieOverzicht({ werkgebiedId, deelvraagId, inGesprek = false, versie = 0 }: {
  werkgebiedId: string;
  /** De deelvraag waar het gesprek nu staat. */
  deelvraagId?: string;
  inGesprek?: boolean;
  versie?: number;
}) {
  const [o, setO] = useState<Overzicht | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [poging, setPoging] = useState(0);
  useEffect(() => {
    let levend = true;
    haalBronselectie(werkgebiedId).then((x) => { if (levend) { setO(x); setFout(null); } })
      .catch((e) => { if (levend) setFout(foutTekst(e)); });
    return () => { levend = false; };
  }, [werkgebiedId, poging, versie]);

  async function beslis(d: DeelvraagSelectie, k: KandidaatHier, besluit: BronselectieBesluit) {
    setMelding(null);
    try {
      setO(await besluitBronselectie(werkgebiedId, d.id, k.id, besluit));
    } catch (e) {
      // Een 412: iemand anders wijzigde het werkgebied. Opnieuw laden, niet stil opnieuw uitvoeren.
      if (isRevisieConflict(e)) {
        setMelding("Iemand anders wijzigde het werkgebied net; hieronder de stand van nu.");
        setPoging((p) => p + 1);
      } else setMelding(foutTekst(e, "Het besluit is niet vastgelegd."));
    }
  }

  if (fout) {
    return (
      <Melding type="fout" titel="De bronselectie kon niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => setPoging((p) => p + 1)}>
          Opnieuw proberen
        </button>
      </Melding>
    );
  }
  if (!o) return <SkeletonCard regels={4} />;
  const beperkingen = zoekBeperkingen(o.zoekdekking);
  const huidig = deelvraagId || o.actief || "";
  return (
    <div data-bronselectie className="space-y-5 text-sm text-ink">
      <p className="text-xs text-muted" data-bronselectie-voortgang>{voortgangZin(o)}</p>
      {beperkingen.length > 0 && (
        <Melding type="waarschuwing" compact titel="Over het zoeken">
          <span data-zoekbeperking>{beperkingen.join(" ")}</span>
        </Melding>
      )}
      {melding && <Melding type="waarschuwing" compact>{melding}</Melding>}
      {o.deelvragen.map((d) => (
        <Deelvraag key={d.id} o={o} d={d} open={!inGesprek || d.id === huidig || o.deelvragen.length === 1}
          huidig={d.id === huidig} inGesprek={inGesprek} beslis={beslis} />
      ))}
      {o.zonder_deelvraag.length > 0 && (
        <Sectie niveau={3} titel="Bij geen enkele deelvraag" telling={o.zonder_deelvraag.length}
          toelichting="Voorstellen die Lex vond bij de analysevraag of de opgenomen bronnen, maar bij geen deelvraag.">
          <Link href={voorstellenPad(werkgebiedId)} className="focus-ring rounded text-xs font-medium text-lint hover:underline">
            Bekijk ze in de bronverkenner
          </Link>
        </Sectie>
      )}
      <p className="text-xs text-muted" data-bronselectie-slot>{slotZin(o)}</p>
      {!inGesprek && (
        <p className="text-xs">
          <Link href={historiePad(werkgebiedId)} className="focus-ring rounded font-medium text-lint hover:underline">Historie en besluiten</Link>
          {" · "}
          <Link href={voorstellenPad(werkgebiedId)} className="focus-ring rounded font-medium text-lint hover:underline">Bronverkenner</Link>
        </p>
      )}
    </div>
  );
}

function Deelvraag({ o, d, open, huidig, inGesprek, beslis }: {
  o: Overzicht;
  d: DeelvraagSelectie;
  open: boolean;
  huidig: boolean;
  inGesprek: boolean;
  beslis: (d: DeelvraagSelectie, k: KandidaatHier, b: BronselectieBesluit) => Promise<void>;
}) {
  const titel = o.modus === "analysevraag" ? "De analysevraag" : `${d.nr}. ${d.vraag}`;
  const open_ = d.kandidaten.filter((k) => k.stand !== "opgenomen");
  return (
    <details open={open} data-bronselectie-deelvraag={d.id} data-voortgang={d.status} data-huidig={huidig || undefined}
      className={`rounded-lg border ${huidig ? "border-lint" : "border-line"} bg-paper`}>
      <summary className="focus-ring flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-2.5">
        <span className="min-w-0 flex-1 font-medium">{titel}</span>
        <StatusLabel toon={voortgangToon(d)}>
          {VOORTGANG_LABEL[d.status]}{d.opnieuw_bekijken ? " – opnieuw bekijken" : ""}
        </StatusLabel>
        <span className="w-full text-xs text-muted">
          {d.telling.opgenomen} opgenomen · {d.telling.voorgesteld} open
          {d.telling.niet_gekozen ? ` · ${d.telling.niet_gekozen} niet gekozen` : ""}{d.telling.uitgesloten ? ` · ${d.telling.uitgesloten} uitgesloten` : ""}
          {huidig && inGesprek ? " · hier staat het gesprek" : ""}
        </span>
      </summary>
      <div className="space-y-3 border-t border-line px-3 py-3">
        {inGesprek && !huidig && o.modus === "deelvragen" && (
          <VraagLexKnop alleenInGesprek naam={`Ga verder met deelvraag ${d.nr}`} tekst={`Ga verder met deelvraag ${d.nr}`}
            onderwerp={{ soort: "deelvraag", werkgebied_id: o.werkgebied_id, id: d.id, label: d.vraag }} />
        )}
        {d.opnieuw_bekijken && (
          <Melding type="waarschuwing" compact>
            De analysevraag, de afbakening of deze deelvraag is veranderd sinds de afronding. De besluiten staan er nog;
            bekijk of ze nog kloppen.
          </Melding>
        )}
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Bronnen bij deze deelvraag</h4>
          {d.bronnen.length === 0 ? <p className="mt-1 text-muted">Nog geen.</p> : (
            <Lijst label={`Bronnen bij ${titel}`}>
              {d.bronnen.map((b) => (
                <LijstRij key={b.selectie_id} data-bron-hier={b.bron_iri}
                  titel={<Link href={bronPad(b.bron_iri, o.werkgebied_id)} className="focus-ring rounded text-lint hover:underline">{b.label || b.bron_iri}</Link>}
                  status={<StatusLabel>{b.rol === "analyseren" ? "analyseren" : "context"}</StatusLabel>} />
              ))}
            </Lijst>
          )}
        </div>
        {open_.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Voorstellen van Lex</h4>
            <p className="mt-0.5 text-xs text-muted">Wat je op het kaartje niet aanvinkte, is niet gekozen. Iets toevoegen:
              doorloop de vragen van deze deelvraag opnieuw in het gesprek.</p>
            <Lijst label={`Voorstellen bij ${titel}`}>
              {open_.map((k) => <Kandidaat key={k.id} o={o} d={d} k={k} beslis={beslis} />)}
            </Lijst>
          </div>
        )}
        {d.open_punten.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Onderzoekspunten</h4>
            <ul className="mt-1 list-disc space-y-0.5 pl-5" data-onderzoekspunten>
              {d.open_punten.map((p) => <li key={p.tekst}>{p.tekst}</li>)}
            </ul>
          </div>
        )}
        {!d.beoordelen.mag && d.status !== "niet_gestart" && (
          <p className="text-xs text-muted">Nog niet te beoordelen: {d.beoordelen.redenen.join(" ")}</p>
        )}
        {!inGesprek && o.modus === "deelvragen" && (
          <Link href={deelvraagPad(o.werkgebied_id, d.id)} className="focus-ring inline-block rounded text-xs font-medium text-lint hover:underline">
            Open de deelvraag
          </Link>
        )}
      </div>
    </details>
  );
}

/** Eén voorstel bij één deelvraag: het soort bewijs in gewone woorden en de besluiten. Uitsluiten vraagt een
 *  reden en geldt voor deze deelvraag; een besluit voor het hele werkgebied (`overal`) heropen je hier met
 *  dezelfde reikwijdte. */
function Kandidaat({ o, d, k, beslis }: {
  o: Overzicht;
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
  const meta = [k.rol === "kern" ? "kernbepaling" : k.rol === "afhankelijkheid" ? "afhankelijkheid" : "mogelijk relevant",
    ...k.bewijs_soorten.map((s) => BEWIJS_LABEL[s]), k.elders_opgenomen ? "al opgenomen bij een andere deelvraag" : "",
    k.reden ? `reden: ${k.reden}` : "", k.overal ? "geldt voor het hele werkgebied" : ""].filter(Boolean).join(" · ");
  return (
    <LijstRij data-kandidaat-hier={k.id} data-stand={k.stand}
      titel={<Link href={bronPad(k.bron_iri, o.werkgebied_id)} className="focus-ring rounded text-lint hover:underline">{k.label || k.bron_iri}</Link>}
      meta={meta}
      status={<StatusLabel toon={k.stand === "voorgesteld" ? "geel" : "neutraal"}>{STAND_LABEL[k.stand]}</StatusLabel>}
      acties={uitsluiten ? (
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
          <Button size="xs" variant="secondary" disabled={bezig}
            onClick={() => doe({ besluit: "opnemen", verwachte_revisie: o.revisie, rol: k.rol === "kern" ? "analyseren" : "context" })}>
            Opnemen
          </Button>
          <Button size="xs" variant="secondary" disabled={bezig} onClick={() => setUitsluiten(true)}>Uitsluiten…</Button>
        </>
      ) : (
        <Button size="xs" variant="secondary" disabled={bezig} onClick={() => doe({ besluit: "heropenen", overal: k.overal })}>
          Heropenen
        </Button>
      )} />
  );
}
