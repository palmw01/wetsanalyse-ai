"use client";

import { useEffect, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
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
        </form>
      ) : d.vraag}
      meta={!bewerken && (
        <>
          {d.herkomst === "lex" ? "Voorgesteld door Lex" : `Door ${d.aangemaakt_door}`}
          {bronnen.length > 0 && ` · bronnen: ${bronnen.map((b) => b.label || b.bron_iri).join(", ")}`}
          {dekking && dekking.begrippen.length > 0 && ` · begrippen: ${dekking.begrippen.map((b) => b.naam || "naamloos").join(", ")}`}
        </>
      )}
      status={dekking && (
        <StatusLabel toon={STAND_TOON[dekking.stand]} uitleg={STAND_UITLEG[dekking.stand]} data-stand={dekking.stand}>
          {STAND_LABEL[dekking.stand]}
        </StatusLabel>
      )}
      acties={!bewerken && (
        <>
          <Button size="sm" variant="secondary" className="w-full sm:w-auto" aria-expanded={koppelen}
            aria-label={`Bronnen en begrippen bij: ${d.vraag}`} onClick={() => setKoppelen((k) => !k)}>
            Bronnen en begrippen
          </Button>
          <Button size="sm" variant="ghost" className="w-full sm:w-auto" aria-label={`Bewerken: ${d.vraag}`}
            onClick={() => { setTekst(d.vraag); setBewerken(true); }}>
            Bewerken
          </Button>
          <VraagLexKnop alleenInGesprek onderwerp={{ soort: "deelvraag", werkgebied_id: wg.id, id: d.id, label: d.vraag }}
            className="justify-center" />
          <BevestigKnop bevestigTekst="Weghalen?" ariaLabel={`Weghalen: ${d.vraag}`}
            onBevestig={async () => { await muteer((r) => verwijderDeelvraag(wg.id, d.id, r), { gelukt: "Deelvraag weggehaald." }); }}
            className="focus-ring inline-flex min-h-[32px] w-full items-center justify-center rounded-button px-3 py-1.5 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink coarse:min-h-[44px] sm:w-auto"
            bevestigClassName="text-fout">
            Weghalen
          </BevestigKnop>
        </>
      )}>
      {koppelen && <Koppelen wg={wg} deelvraag={d} muteer={muteer} onKlaar={() => setKoppelen(false)} />}
    </LijstRij>
  );
}

/** Welke bronselecties en begrippen deze deelvraag beantwoorden: vinkjes, één keer opslaan. */
function Koppelen({ wg, deelvraag: d, muteer, onKlaar }: {
  wg: Werkgebied;
  deelvraag: Deelvraag;
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
  const ongewijzigd = zelfdeSet(bronnen, d.bronnen) && zelfdeSet(begrippen, d.begrippen);
  return (
    <div className="mt-3 grid gap-3 rounded-field bg-surface p-3 sm:grid-cols-2">
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-muted">Bronnen</legend>
        {wg.bronnen.length === 0 ? <p className="text-xs text-muted">Nog geen bronnen in dit werkgebied.</p> : (
          <ul className="space-y-1">
            {wg.bronnen.map((b) => (
              <li key={b.id}>
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" className="mt-1" checked={bronnen.includes(b.id)}
                    onChange={() => setBronnen((x) => wissel(x, b.id))} />
                  <span>{b.label || b.bron_iri}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-xs font-medium text-muted">Begrippen</legend>
        {lijst === null ? <p className="text-xs text-muted">Begrippen laden…</p> : lijst.length === 0 ? (
          <p className="text-xs text-muted">Nog geen begrippen in dit werkgebied.</p>
        ) : (
          <ul className="space-y-1">
            {lijst.map((b) => (
              <li key={b.id}>
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" className="mt-1" checked={begrippen.includes(b.id)}
                    onChange={() => setBegrippen((x) => wissel(x, b.id))} />
                  <span>{b.inhoud.naam || "Naamloos begrip"} <span className="text-xs text-muted">({b.status})</span></span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </fieldset>
      <div className="flex flex-col gap-2 sm:col-span-2 sm:flex-row">
        <Button size="sm" className="w-full sm:w-auto" disabled={ongewijzigd} onClick={async () => {
          if (await muteer((r) => koppelDeelvraag(wg.id, d.id, { bronnen, begrippen }, r), { gelukt: "Vastgelegd bij de deelvraag." }))
            onKlaar();
        }}>
          Opslaan
        </Button>
        <Button size="sm" variant="ghost" className="w-full sm:w-auto" onClick={onKlaar}>Annuleren</Button>
      </div>
    </div>
  );
}
