"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { BronBoom } from "@/components/ui/BronBoom";
import { Dialog } from "@/components/ui/Dialog";
import { Meer } from "@/components/ui/Icoon";
import { Popover } from "@/components/ui/Popover";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Lijst, LijstRij, Sectie, StatusLabel, Voorstel as VoorstelRij } from "@/components/ui/Lijst";
import type { Mutatie } from "@/components/werkgebieden/WerkgebiedProject";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import {
  koppelDeelvraag, lijstBegrippen, maakDeelvraag, verwijderDeelvraag, wijzigDeelvraag,
} from "@/lib/api";
import {
  STAND_LABEL, STAND_TOON, STAND_UITLEG, dekkingZin, overgenomenZin, splits, vervangtZin, wissel, zelfdeSet,
} from "@/lib/deelvragen";
import type { BegripSamenvatting, Deelvraag, DeelvragenDekking, Werkgebied } from "@/lib/types";
import { useDeelvragenDekking } from "@/lib/useDeelvragenDekking";
import { bouwBoom, omvangZin, regelingUitLabel } from "@/lib/bronPlaats";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { deelvraagPad } from "@/lib/werkgebiedPaden";

/** Deelvragen bij een werkgebied, bovenaan de tab Bronnen (optioneel; open keuze 4).
 *
 *  Een deelvraag splitst de analysevraag. Per deelvraag leg je vast welke bronnen en begrippen haar
 *  beantwoorden; de dekking zegt dan of er een geaccordeerd begrip bij hoort. Lex stelt deelvragen voor
 *  als je hem dat in het gesprek vraagt (geel): overnemen of afwijzen, met een reden. *Vraag Lex* bij een
 *  deelvraag zet haar als onderwerp in het gesprek (F3e). Zonder deelvragen verandert er niets aan
 *  het werkgebied. Elke wijziging draagt de revisie in beeld (`muteer`), want deelvragen horen bij de
 *  scope; Lex zoekt bij een volgende ronde ook per deelvraag naar bepalingen. */
export function Deelvragen({ wg, muteer }: { wg: Werkgebied; muteer: Mutatie }) {
  const { actief, voorgesteld } = splits(wg.deelvragen);
  const stand = useDeelvragenDekking(wg.id, wg.revisie, actief.length);
  const [nieuw, setNieuw] = useState("");

  async function voegToe(e: React.FormEvent) {
    e.preventDefault();
    const vraag = nieuw.trim();
    if (!vraag) return;
    if (await muteer((r) => maakDeelvraag(wg.id, vraag, r), { gelukt: "Deelvraag toegevoegd." })) setNieuw("");
  }

  const perId = new Map((stand?.deelvragen ?? []).map((d) => [d.id, d]));

  return (
    <Sectie data-deelvragen titel="Deelvragen" telling={actief.length}
      toelichting={<>Optioneel. {dekkingZin(stand) || "Splits de analysevraag; per deelvraag zie je of er een bron en een geaccordeerd begrip bij hoort."}</>}>
      {(voorgesteld.length > 0 || actief.length > 0) && (
        <div>
          {voorgesteld.length > 0 && (
            <Lijst label="Voorstellen van Lex">
              {voorgesteld.map((d) => <DeelvraagVoorstel key={d.id} wgId={wg.id} deelvraag={d} alle={wg.deelvragen}
                muteer={muteer} />)}
            </Lijst>
          )}
          {actief.length > 0 && (
            <Lijst genummerd label="Deelvragen">
              {actief.map((d, i) => (
                <DeelvraagRij key={d.id} nummer={i + 1} wg={wg} deelvraag={d} dekking={perId.get(d.id)} muteer={muteer} />
              ))}
            </Lijst>
          )}
        </div>
      )}

      <form onSubmit={voegToe} className="flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="nieuwe-deelvraag">Nieuwe deelvraag</label>
        <Input id="nieuwe-deelvraag" value={nieuw} onChange={(e) => setNieuw(e.target.value)} maxLength={1000}
          placeholder="Bijvoorbeeld: Wanneer vervalt de betalingstermijn?" />
        <Button type="submit" size="sm" variant="secondary" className="w-full sm:w-auto" disabled={!nieuw.trim()}>
          Toevoegen
        </Button>
      </form>
    </Sectie>
  );
}

/** Een voorstel van Lex: overnemen of afwijzen met een reden. Een verbetering van een bestaande deelvraag
 *  (`vervangt`, F3d) zegt welke ze vervangt; overnemen zet haar op die plek, met haar bronnen en begrippen.
 *  Ook in het deelvraagpaneel naast het gesprek. */
export function DeelvraagVoorstel({ wgId, deelvraag: d, alle, muteer }: {
  wgId: string;
  deelvraag: Deelvraag;
  /** De deelvragen van het werkgebied, om te noemen welke dit voorstel vervangt. */
  alle?: readonly Deelvraag[];
  muteer: Mutatie;
}) {
  const [afwijzen, setAfwijzen] = useState(false);
  const [reden, setReden] = useState("");
  const vervangt = vervangtZin(d, alle);
  return (
    <VoorstelRij data-voorstel-deelvraag={d.id} titel={d.vraag} acties={!afwijzen && (
      <>
        <Button size="sm" className="w-full sm:w-auto" aria-label={`Overnemen: ${d.vraag}`}
          onClick={() => void muteer((r) => wijzigDeelvraag(wgId, d.id, { status: "actief" }, r), { gelukt: overgenomenZin(d, alle) })}>
          Overnemen
        </Button>
        <Button size="sm" variant="secondary" className="w-full sm:w-auto" aria-label={`Afwijzen: ${d.vraag}`}
          onClick={() => setAfwijzen(true)}>
          Afwijzen…
        </Button>
      </>
    )}>
      {vervangt && <p className="mt-1 text-xs text-muted" data-vervangt={d.vervangt}>{vervangt}</p>}
      {afwijzen && (
        <form className="mt-2 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => {
          e.preventDefault();
          if (!reden.trim()) return;
          void muteer((r) => wijzigDeelvraag(wgId, d.id, { status: "afgewezen", reden: reden.trim() }, r),
            { gelukt: "Voorstel afgewezen; Lex stelt het niet opnieuw voor." });
        }}>
          <label className="sr-only" htmlFor={`reden-${d.id}`}>Reden van afwijzen</label>
          <Input id={`reden-${d.id}`} value={reden} onChange={(e) => setReden(e.target.value)} autoFocus
            placeholder="Waarom hoort dit er niet bij?" maxLength={2000} />
          <Button type="submit" size="sm" variant="secondary" className="w-full sm:w-auto" disabled={!reden.trim()}>
            Afwijzen
          </Button>
          <Button type="button" size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => setAfwijzen(false)}>
            Annuleren
          </Button>
        </form>
      )}
    </VoorstelRij>
  );
}

/** Eén deelvraag als rij (spoor H3): de vraag als link naar haar pagina, waar de bronnen als boom staan;
 *  hier alleen wie haar stelde en hoeveel er bij hoort. Bewerken, koppelen en verwijderen staan achter ⋯. */
function DeelvraagRij({ nummer, wg, deelvraag: d, dekking, muteer }: {
  nummer: number;
  wg: Werkgebied;
  deelvraag: Deelvraag;
  dekking?: DeelvragenDekking["deelvragen"][number];
  muteer: Mutatie;
}) {
  const [bewerken, setBewerken] = useState(false);
  const [tekst, setTekst] = useState(d.vraag);
  const [koppelen, setKoppelen] = useState(false);
  const bronnen = wg.bronnen.filter((b) => d.bronnen.includes(b.id));
  const regelingen = new Set(bronnen.map((b) => b.bwb_id || b.bron_iri.split(":")[2])).size;
  const nBegrippen = dekking?.begrippen.length ?? d.begrippen.length;
  const omvang = [
    bronnen.length ? `${bronnen.length} ${bronnen.length === 1 ? "bron" : "bronnen"}${regelingen > 1 ? ` in ${regelingen} regelingen` : ""}` : "nog geen bronnen",
    `${nBegrippen} ${nBegrippen === 1 ? "begrip" : "begrippen"}`,
  ].join(" · ");
  return (
    <LijstRij data-deelvraag={d.id} voor={`${nummer}.`}
      titel={bewerken ? (
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={async (e) => {
          e.preventDefault();
          if (!tekst.trim() || tekst.trim() === d.vraag) return setBewerken(false);
          if (await muteer((r) => wijzigDeelvraag(wg.id, d.id, { vraag: tekst.trim() }, r), { gelukt: "Deelvraag gewijzigd." }))
            setBewerken(false);
        }}>
          <label className="sr-only" htmlFor={`vraag-${d.id}`}>Deelvraag</label>
          <Input id={`vraag-${d.id}`} value={tekst} onChange={(e) => setTekst(e.target.value)} autoFocus maxLength={1000} />
          <Button type="submit" size="sm" className="w-full sm:w-auto">Opslaan</Button>
          <Button type="button" size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => setBewerken(false)}>Annuleren</Button>
        </form>
      ) : (
        <Link href={deelvraagPad(wg.id, d.id)} className="focus-ring rounded font-medium text-ink hover:text-lint hover:underline">{d.vraag}</Link>
      )}
      meta={!bewerken && <>{d.herkomst === "lex" ? "Voorgesteld door Lex" : `Door ${d.aangemaakt_door}`} · {omvang}</>}
      status={!bewerken && (
        <span className="flex items-center gap-1.5">
          {dekking && (
            <StatusLabel toon={STAND_TOON[dekking.stand]} uitleg={STAND_UITLEG[dekking.stand]} data-stand={dekking.stand}>
              {STAND_LABEL[dekking.stand]}
            </StatusLabel>
          )}
          <Popover ariaLabel={`Acties voor deelvraag ${nummer}`} className="w-56 rounded-kaart border border-line bg-paper p-1 shadow-kaart"
            trigger={(open, toggle) => (
              <button type="button" onClick={toggle} aria-expanded={open} aria-label={`Acties: ${d.vraag}`}
                className="focus-ring inline-flex min-h-[28px] min-w-[28px] items-center justify-center rounded text-muted hover:bg-surface hover:text-lint coarse:min-h-[44px] coarse:min-w-[44px]">
                <Meer />
              </button>
            )}>
            {(sluit) => (
              <div className="flex flex-col">
                <button type="button" className={MENU} aria-label={`Bronnen en begrippen bij: ${d.vraag}`}
                  onClick={() => { sluit(); setKoppelen(true); }}>Bronnen en begrippen koppelen</button>
                <button type="button" className={MENU} aria-label={`Bewerken: ${d.vraag}`}
                  onClick={() => { sluit(); setTekst(d.vraag); setBewerken(true); }}>Bewerken</button>
                <BevestigKnop bevestigTekst="Verwijderen?" ariaLabel={`Verwijderen: ${d.vraag}`}
                  titel="Verwijdert de deelvraag; de bronnen en begrippen blijven in het werkgebied."
                  onBevestig={async () => { await muteer((r) => verwijderDeelvraag(wg.id, d.id, r), { gelukt: "Deelvraag verwijderd." }); }}
                  className={`${MENU} text-fout`} bevestigClassName="font-medium">
                  Verwijderen
                </BevestigKnop>
              </div>
            )}
          </Popover>
          <VraagLexKnop alleenInGesprek onderwerp={{ soort: "deelvraag", werkgebied_id: wg.id, id: d.id, label: d.vraag }} />
        </span>
      )}>
      {koppelen && <KoppelDialoog wg={wg} deelvraag={d} muteer={muteer} onKlaar={() => setKoppelen(false)} />}
    </LijstRij>
  );
}

const MENU = "focus-ring flex min-h-[32px] w-full items-center rounded-md px-2.5 py-1.5 text-left text-sm text-ink hover:bg-surface coarse:min-h-[44px]";

/** Welke bronselecties en begrippen deze deelvraag beantwoorden (spoor H3): in een venster, met de bronnen
 *  als boom per regeling › hoofdstuk › artikel › lid – een heel artikel of hoofdstuk in één vinkje – en de
 *  begrippen eronder. Eén keer opslaan, de hele set. */
export function KoppelDialoog({ wg, deelvraag: d, muteer, onKlaar }: {
  wg: Werkgebied;
  deelvraag: Pick<Deelvraag, "id" | "vraag" | "bronnen" | "begrippen">;
  muteer: Mutatie;
  onKlaar: () => void;
}) {
  const [bronnen, setBronnen] = useState<string[]>(d.bronnen);
  const [begrippen, setBegrippen] = useState<string[]>(d.begrippen);
  const [lijst, setLijst] = useState<BegripSamenvatting[] | null>(null);
  useEffect(() => {
    let levend = true;
    lijstBegrippen(wg.id).then((l) => { if (levend) setLijst(l.begrippen.filter((b) => b.status !== "vervangen")); })
      .catch(() => { if (levend) setLijst([]); });
    return () => { levend = false; };
  }, [wg.id]);
  const plaatsen = usePlaatsen(wg.bronnen.map((b) => b.bron_iri));
  const boom = useMemo(() => bouwBoom(wg.bronnen, {
    iri: (b) => b.bron_iri, naam: (b) => b.label || b.bron_iri, plaatsen, regelingNaam: (b) => regelingUitLabel(b.label),
  }), [wg.bronnen, plaatsen]);
  // De boom vinkt per bron-IRI; de deelvraag koppelt selecties (id's).
  const idVan = useMemo(() => new Map(wg.bronnen.map((b) => [b.bron_iri, b.id])), [wg.bronnen]);
  const gekozen = useMemo(() => new Set(wg.bronnen.filter((b) => bronnen.includes(b.id)).map((b) => b.bron_iri)), [wg.bronnen, bronnen]);
  const ongewijzigd = zelfdeSet(bronnen, d.bronnen) && zelfdeSet(begrippen, d.begrippen);
  return (
    <Dialog label={`Bronnen en begrippen bij: ${d.vraag}`} variant="compact" onSluit={onKlaar}>
      <div className="flex min-h-0 flex-1 flex-col" data-koppel-dialoog={d.id}>
        <div className="shrink-0 border-b border-line px-5 py-3.5">
          <p className="text-xs text-muted">Bronnen en begrippen bij de deelvraag</p>
          <h2 className="font-display text-base font-semibold text-lint">{d.vraag}</h2>
        </div>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4">
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-ink">Bronnen <span className="font-normal text-muted">· {omvangZin(boom)}</span></legend>
            {wg.bronnen.length === 0 ? <p className="text-sm text-muted">Nog geen bronnen in dit werkgebied.</p> : (
              <BronBoom boom={boom} label="Bronnen van het werkgebied"
                vinkjes={{ gekozen, naam: (b) => b.data.label || b.bron_iri, onZet: (iris, aan) => setBronnen((x) => {
                  const ids = iris.map((i) => idVan.get(i)).filter((i): i is string => !!i);
                  return aan ? [...new Set([...x, ...ids])] : x.filter((i) => !ids.includes(i));
                }) }}
                renderBlad={(b) => <span className="text-sm text-ink">{b.label}</span>} />
            )}
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-ink">Begrippen</legend>
            {lijst === null ? <p className="text-sm text-muted">Begrippen laden…</p> : lijst.length === 0 ? (
              <p className="text-sm text-muted">Nog geen begrippen in dit werkgebied.</p>
            ) : (
              <ul className="space-y-1">
                {lijst.map((b) => (
                  <li key={b.id}>
                    <label className="flex items-start gap-2 text-sm">
                      <input type="checkbox" className="focus-ring mt-1 accent-lint" checked={begrippen.includes(b.id)}
                        onChange={() => setBegrippen((x) => wissel(x, b.id))} />
                      <span>{b.inhoud.naam || "Naamloos begrip"} <span className="text-xs text-muted">({b.status})</span></span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>
        </div>
        <div className="flex shrink-0 flex-col gap-2 border-t border-line px-5 py-3 sm:flex-row">
          <Button size="sm" className="w-full sm:w-auto" disabled={ongewijzigd} onClick={async () => {
            if (await muteer((r) => koppelDeelvraag(wg.id, d.id, { bronnen, begrippen }, r), { gelukt: "Vastgelegd bij de deelvraag." }))
              onKlaar();
          }}>
            Opslaan
          </Button>
          <Button size="sm" variant="ghost" className="w-full sm:w-auto" onClick={onKlaar}>Annuleren</Button>
        </div>
      </div>
    </Dialog>
  );
}
