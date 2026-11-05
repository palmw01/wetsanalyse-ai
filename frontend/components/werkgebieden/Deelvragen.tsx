"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { BewerkKnop, BewerkVoet, useBewerken } from "@/components/ui/Bewerkbaar";
import { BronBoom } from "@/components/ui/BronBoom";
import { Dialog } from "@/components/ui/Dialog";
import { Koppelen, Prullenbak } from "@/components/ui/Icoon";
import { MeerMenu, MenuKnop } from "@/components/ui/MeerMenu";
import { Button, IcoonKnop } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Lijst, LijstRij, Sectie, StatusLabel, Voorstel as VoorstelRij } from "@/components/ui/Lijst";
import { useWerkgebied, type Mutatie } from "@/components/werkgebieden/WerkgebiedProject";
import { koppelDeelvraag, maakDeelvraag, verwijderDeelvraag, wijzigDeelvraag } from "@/lib/api";
import { bronnenZin, deelvraagStand, voortgangZin, type DeelvraagSelectie } from "@/lib/bronselectie";
import {
  conceptFout, conceptVan, deelvraagStappen, overgenomenZin, splits, vervangtZin, zelfdeSet, type DeelvraagConcept,
} from "@/lib/deelvragen";
import type { Deelvraag, Werkgebied } from "@/lib/types";
import { useBronselectieStand } from "@/lib/useBronselectieStand";
import { bouwBoom, omvangZin, regelingUitLabel } from "@/lib/bronPlaats";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { deelvraagPad } from "@/lib/werkgebiedPaden";

/** Deelvragen bij een werkgebied, bovenaan de tab Bronnen (optioneel; open keuze 4).
 *
 *  Een deelvraag splitst de analysevraag. Per deelvraag leg je vast welke bronnen haar beantwoorden (methode
 *  1g); de stand is de voortgang van haar bronselectie. Begrippen horen bij het werkgebied, niet bij een
 *  deelvraag (spoor K). Lex stelt deelvragen voor
 *  als je hem dat in het gesprek vraagt (geel): overnemen of afwijzen, met een reden. Zonder deelvragen verandert er niets aan
 *  het werkgebied. Elke wijziging draagt de revisie in beeld (`muteer`), want deelvragen horen bij de
 *  scope; Lex zoekt bij een volgende ronde ook per deelvraag naar bepalingen. */
export function Deelvragen({ wg, muteer, onOnbewaard }: {
  wg: Werkgebied;
  muteer: Mutatie;
  /** Meldt aan de bewaker van het werkgebied of er onbewaard iets openstaat. */
  onOnbewaard?: (onbewaard: boolean) => void;
}) {
  const { actief, voorgesteld } = splits(wg.deelvragen);
  const stand = useBronselectieStand(wg.id, wg.revisie, actief.length);
  const { laad } = useWerkgebied();
  // Eén *Bewerken* voor het hele blok, zoals de analyseopdracht erboven (besluit gebruiker 5 nov 2026): in rust staan
  // de deelvragen met hun stand, in de bewerkstand is elke deelvraag een veld, met *+ Nog een deelvraag* en een
  // prullenbak per regel. Pas *Opslaan* legt alles vast, in één handeling met de revisie in beeld.
  const bw = useBewerken<DeelvraagConcept[]>({
    // Zonder deelvragen begint de bewerkstand met één leeg veld: je komt om er een toe te voegen.
    begin: actief.length ? conceptVan(actief) : [{ vraag: "" }],
    onOnbewaard,
    opslaan: async (concept) => {
      const fout = conceptFout(concept);
      if (fout) throw new Error(fout);
      const stappen = deelvraagStappen(actief, concept);
      if (!stappen.length) return;
      return (await muteer(async (r) => {
        let revisie = r;
        let uit: Werkgebied = wg;
        for (const stap of stappen) {
          uit = stap.soort === "verwijder" ? await verwijderDeelvraag(wg.id, stap.id, revisie)
            : stap.soort === "wijzig" ? await wijzigDeelvraag(wg.id, stap.id, { vraag: stap.vraag }, revisie)
            : await maakDeelvraag(wg.id, stap.vraag, revisie);
          revisie = uit.revisie;
        }
        return uit;
      }, {
        gelukt: "Deelvragen opgeslagen.",
        // Ging een stap mis nadat er al iets was opgeslagen: laad de stand van nu, anders klopt de revisie niet meer.
        opFout: () => { void laad(); return false; },
      })) || false;
    },
  });

  const perId = new Map((stand?.deelvragen ?? []).map((d) => [d.id, d]));

  return (
    <Sectie data-deelvragen titel="Deelvragen" telling={actief.length}
      acties={!bw.open && <BewerkKnop wat="Deelvragen" onClick={bw.start} />}
      toelichting={<>Optioneel. {(stand?.modus === "deelvragen" && voortgangZin(stand)) || "Splits de analysevraag; per deelvraag zie je haar bronnen en hoe ver de bronselectie is."}</>}>
      {voorgesteld.length > 0 && (
        <Lijst label="Voorstellen van Lex">
          {voorgesteld.map((d) => <DeelvraagVoorstel key={d.id} wgId={wg.id} deelvraag={d} alle={wg.deelvragen}
            muteer={muteer} />)}
        </Lijst>
      )}
      {bw.open ? (
        <DeelvragenBewerken bw={bw} oud={actief} />
      ) : actief.length > 0 ? (
        <Lijst genummerd label="Deelvragen">
          {actief.map((d, i) => (
            <DeelvraagRij key={d.id} nummer={i + 1} wg={wg} deelvraag={d} selectie={perId.get(d.id)} muteer={muteer} />
          ))}
        </Lijst>
      ) : (
        <p className="text-sm text-muted" data-geen-deelvragen>
          Nog geen deelvragen. Voeg ze toe met <em>Bewerken</em>, of vraag Lex in het gesprek om ze voor te stellen.
        </p>
      )}
    </Sectie>
  );
}

/** De bewerkstand van het blok: per deelvraag een veld en een prullenbak; een verwijderde staat doorgestreept met
 *  *Terugzetten* tot *Opslaan*. Enter in een gevulde regel opent een nieuwe eronder (zoals `MeerRegels`), Ctrl/⌘+Enter
 *  slaat op, Escape annuleert. */
function DeelvragenBewerken({ bw, oud }: {
  bw: ReturnType<typeof useBewerken<DeelvraagConcept[]>>;
  /** De deelvragen zoals ze nu bewaard zijn. */
  oud: readonly Deelvraag[];
}) {
  const [focus, setFocus] = useState<number | null>(null);
  const regels = bw.concept;
  const zet = (i: number, w: Partial<DeelvraagConcept>) => bw.zet(regels.map((c, j) => (j === i ? { ...c, ...w } : c)));
  const erbij = (na: number) => {
    bw.zet([...regels.slice(0, na + 1), { vraag: "" }, ...regels.slice(na + 1)]);
    setFocus(na + 1);
  };
  const fout = conceptFout(regels);
  const toetsen = (i: number) => (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); bw.annuleer(); return; }
    if (e.key !== "Enter" || e.shiftKey) return;
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) void bw.slaOp();
    else if (regels[i].vraag.trim()) erbij(i);
  };
  return (
    <form data-deelvragen-bewerken onSubmit={(e) => { e.preventDefault(); void bw.slaOp(); }}>
      <ol className="space-y-2">
        {regels.map((c, i) => (
          <li key={c.id ?? `nieuw-${i}`} className="flex items-start gap-3" data-concept={c.id ?? "nieuw"} data-weg={c.weg ? "" : undefined}>
            <span className="shrink-0 pt-2 text-sm tabular-nums text-muted">{i + 1}.</span>
            {c.weg ? (
              <p className="min-w-0 flex-1 pt-2 text-sm">
                <span className="text-muted line-through">{c.vraag}</span>
                <span className="ml-2 text-xs text-fout">wordt verwijderd</span>
                <button type="button" onClick={() => zet(i, { weg: false })}
                  className="focus-ring ml-2 rounded text-xs font-medium text-lint hover:underline">Terugzetten</button>
              </p>
            ) : (
              <>
                <div className="min-w-0 flex-1">
                  <AutoTextarea aria-label={`Deelvraag ${i + 1}`} rows={1} value={c.vraag} maxLength={1000}
                    autoFocus={focus === i || (focus === null && i === 0)}
                    placeholder={c.id ? "" : "Bijvoorbeeld: Wanneer vervalt de betalingstermijn?"}
                    onChange={(e) => zet(i, { vraag: e.target.value })} onKeyDown={toetsen(i)} />
                </div>
                <IcoonKnop aria-label={`Deelvraag ${i + 1} verwijderen`} className="mt-1.5"
                  onClick={() => c.id ? zet(i, { weg: true }) : bw.zet(regels.filter((_, j) => j !== i))}>
                  <Prullenbak />
                </IcoonKnop>
              </>
            )}
          </li>
        ))}
      </ol>
      <button type="button" onClick={() => erbij(regels.length - 1)}
        className="focus-ring mt-2 rounded text-sm font-medium text-lint hover:underline">
        + Nog een deelvraag
      </button>
      <BewerkVoet submit onAnnuleer={bw.annuleer} bezig={bw.bezig}
        gewijzigd={bw.gewijzigd && !fout && deelvraagStappen(oud, regels).length > 0} fout={bw.fout ?? (bw.gewijzigd ? fout : null)} />
    </form>
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
 *  hier alleen wie haar stelde en hoeveel er bij hoort. Bewerken en verwijderen gaan via *Bewerken* van het blok
 *  (5 nov 2026); *Bronnen koppelen* staat achter ⋯. */
function DeelvraagRij({ nummer, wg, deelvraag: d, selectie, muteer }: {
  nummer: number;
  wg: Werkgebied;
  deelvraag: Deelvraag;
  selectie?: DeelvraagSelectie;
  muteer: Mutatie;
}) {
  const [koppelen, setKoppelen] = useState(false);
  const bronnen = wg.bronnen.filter((b) => d.bronnen.includes(b.id));
  const regelingen = new Set(bronnen.map((b) => b.bwb_id || b.bron_iri.split(":")[2])).size;
  const omvang = `${bronnenZin(bronnen.length)}${regelingen > 1 ? ` in ${regelingen} regelingen` : ""}`;
  const st = deelvraagStand(selectie);
  return (
    <LijstRij data-deelvraag={d.id} voor={`${nummer}.`}
      titel={<Link href={deelvraagPad(wg.id, d.id)} className="focus-ring rounded font-medium text-ink hover:text-lint hover:underline">{d.vraag}</Link>}
      meta={<>{d.herkomst === "lex" ? "Voorgesteld door Lex" : `Door ${d.aangemaakt_door}`} · {omvang}</>}
      status={(
        <span className="flex items-center gap-1.5">
          {st && <StatusLabel toon={st.toon} data-stand={selectie?.status}>{st.label}</StatusLabel>}
          <MeerMenu label={`Acties: ${d.vraag}`}>
            {(sluit) => (
              <MenuKnop icoon={<Koppelen />} ariaLabel={`Bronnen bij: ${d.vraag}`} onClick={() => { sluit(); setKoppelen(true); }}>
                Bronnen koppelen
              </MenuKnop>
            )}
          </MeerMenu>
        </span>
      )}>
      {koppelen && <KoppelDialoog wg={wg} deelvraag={d} muteer={muteer} onKlaar={() => setKoppelen(false)} />}
    </LijstRij>
  );
}

/** Welke bronselecties deze deelvraag beantwoorden (spoor H3, methode 1g): in een venster, als boom per
 *  regeling › hoofdstuk › artikel › lid – een heel artikel of hoofdstuk in één vinkje. Eén keer opslaan, de hele
 *  set. Begrippen koppel je hier niet: die horen bij het werkgebied (spoor K); wat er al gekoppeld was, blijft. */
export function KoppelDialoog({ wg, deelvraag: d, muteer, onKlaar }: {
  wg: Werkgebied;
  deelvraag: Pick<Deelvraag, "id" | "vraag" | "bronnen" | "begrippen">;
  muteer: Mutatie;
  onKlaar: () => void;
}) {
  const [bronnen, setBronnen] = useState<string[]>(d.bronnen);
  const plaatsen = usePlaatsen(wg.bronnen.map((b) => b.bron_iri));
  const boom = useMemo(() => bouwBoom(wg.bronnen, {
    iri: (b) => b.bron_iri, naam: (b) => b.label || b.bron_iri, plaatsen, regelingNaam: (b) => regelingUitLabel(b.label),
  }), [wg.bronnen, plaatsen]);
  // De boom vinkt per bron-IRI; de deelvraag koppelt selecties (id's).
  const idVan = useMemo(() => new Map(wg.bronnen.map((b) => [b.bron_iri, b.id])), [wg.bronnen]);
  const gekozen = useMemo(() => new Set(wg.bronnen.filter((b) => bronnen.includes(b.id)).map((b) => b.bron_iri)), [wg.bronnen, bronnen]);
  const ongewijzigd = zelfdeSet(bronnen, d.bronnen);
  return (
    <Dialog label={`Bronnen bij: ${d.vraag}`} variant="compact" onSluit={onKlaar}>
      <div className="flex min-h-0 flex-1 flex-col" data-koppel-dialoog={d.id}>
        <div className="shrink-0 border-b border-line px-5 py-3.5">
          <p className="text-xs text-muted">Bronnen bij de deelvraag</p>
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
        </div>
        <div className="flex shrink-0 flex-col gap-2 border-t border-line px-5 py-3 sm:flex-row">
          <Button size="sm" className="w-full sm:w-auto" disabled={ongewijzigd} onClick={async () => {
            if (await muteer((r) => koppelDeelvraag(wg.id, d.id, { bronnen, begrippen: d.begrippen }, r), { gelukt: "Vastgelegd bij de deelvraag." }))
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
