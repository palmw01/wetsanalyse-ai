"use client";

import { useState } from "react";

import { BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { IcoonBevestig } from "@/components/ui/IcoonBevestig";
import { Waarschuwing } from "@/components/ui/Icoon";
import { KlasseLabel, Lijst, LijstRij, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { foutTekst } from "@/lib/api";
import type { NodeEindpunt, NodeImpliciet, NodeRelatie, NodeWeergave, RelatieInvoer } from "@/lib/annotatieNode";
import {
  eigenRelatie, relatieAfgehandeld, relatiesBijElement, relatieStatus, typeKeuzes, verbindbaar, type RelatieRegel,
  type TypeKeuze, type Verbindbaar,
} from "@/lib/annotatieNodeAdapter";

/** Wat het blok kan doen. Zonder (de rondleiding, een oude versie, een afgeronde annotatie) is het alleen te lezen. */
export interface RelatieBediening {
  leg(invoer: RelatieInvoer): Promise<void>;
  beslis(relatie: NodeRelatie, type: "approve" | "reject" | "heropen", comment?: string): Promise<void>;
  wis(relatie: NodeRelatie): Promise<void>;
}

/** Wat de andere kant is, in één regel: de tekst van de markering, of het label van een impliciete partij. */
function AndereKant({ ep }: { ep: NodeEindpunt }) {
  if (!ep.bestaat) return <span className="text-muted">(niet meer aanwezig)</span>;
  if (ep.soort === "impliciet") {
    return <><span className="font-medium">{ep.tekst}</span> <StatusLabel klein>impliciet</StatusLabel></>;
  }
  return <>“{ep.tekst}”{ep.klasse && <> <KlasseLabel klasse={ep.klasse} klein /></>}</>;
}

/** Het blok *Relaties* op de reviewkaart (ADR-011): wat dit element met andere markeringen verbindt, gelezen vanaf dit
 *  element, en *Verbind met…* om er een te leggen. Een lijst, geen tabel; een veranderde relatie staat bovenaan. */
export function RelatieBlok({ view, elementId, gebruiker, bediening }: {
  view: NodeWeergave;
  elementId: string;
  /** De userid van wie kijkt: alleen een eigen relatie kun je wissen. */
  gebruiker?: string;
  bediening?: RelatieBediening;
}) {
  const [verbinden, setVerbinden] = useState(false);
  const [fout, setFout] = useState("");
  const regels = relatiesBijElement(view, elementId);
  const kandidaten = verbindbaar(view);
  const dit = kandidaten.find((k) => k.ref.soort === "element" && k.ref.id === elementId);
  const anderen = kandidaten.filter((k) => k !== dit && (!dit || typeKeuzes(dit, k).length > 0));

  async function doe(actie: () => Promise<void>): Promise<boolean> {
    setFout("");
    try {
      await actie();
      return true;
    } catch (e) {
      setFout(foutTekst(e, "Dat lukte niet."));
      return false;
    }
  }

  return (
    <Sectie niveau={3} titel="Relaties" telling={regels.length} className="mt-2 border-t border-line/60 pt-2"
      data-relaties={elementId}
      acties={bediening && dit && anderen.length > 0 && !verbinden && (
        <Button size="xs" variant="secondary" onClick={() => setVerbinden(true)}>Verbind met…</Button>
      )}>
      {fout && <p role="alert" className="text-xs text-fout">{fout}</p>}
      {regels.length > 0 ? (
        <Lijst label="Relaties van dit element">
          {regels.map((r) => (
            <RelatieRij key={r.relatie.id} regel={r} gebruiker={gebruiker} bediening={bediening} doe={doe} />
          ))}
        </Lijst>
      ) : !verbinden && <p className="text-xs text-muted">Nog geen relaties met andere markeringen.</p>}
      {verbinden && bediening && dit && (
        <Verbind dit={dit} anderen={anderen} onSluit={() => setVerbinden(false)}
          onLeg={async (invoer) => (await doe(() => bediening.leg(invoer))) && setVerbinden(false)} />
      )}
    </Sectie>
  );
}

function RelatieRij({ regel, gebruiker, bediening, doe }: {
  regel: RelatieRegel;
  gebruiker?: string;
  bediening?: RelatieBediening;
  doe: (actie: () => Promise<void>) => Promise<boolean>;
}) {
  const { relatie: r, zin, ander } = regel;
  const [afwijzen, setAfwijzen] = useState(false);
  const [reden, setReden] = useState("");
  const [bezig, setBezig] = useState(false);
  const afgewezen = r.lifecycle === "rejected";
  const afgehandeld = relatieAfgehandeld(r);
  const naam = `${zin} ${ander.tekst ?? ""}`.trim();

  async function stuur(actie: () => Promise<void>) {
    setBezig(true);
    try { return await doe(actie); } finally { setBezig(false); }
  }

  const acties = bediening && !afwijzen && (
    <>
      {!afgewezen && (!afgehandeld || r.veranderd) && (
        r.veranderd && afgehandeld ? (
          <Button size="xs" variant="secondary" disabled={bezig} aria-label={`Klopt nog: ${naam}`}
            onClick={() => void stuur(() => bediening.beslis(r, "approve"))}>Klopt nog</Button>
        ) : (
          <IcoonBevestig soort="akkoord" label={`Akkoord: ${naam}`} disabled={bezig}
            onBevestig={async () => { await stuur(() => bediening.beslis(r, "approve")); }} />
        )
      )}
      {!afgewezen && (!afgehandeld || r.veranderd) && (
        <Button size="xs" variant="ghost" disabled={bezig} aria-label={`Wijs af: ${naam}`} onClick={() => setAfwijzen(true)}>
          Afwijzen
        </Button>
      )}
      {afgehandeld && !r.veranderd && (
        <Button size="xs" variant="secondary" disabled={bezig} aria-label={`Heropen: ${naam}`}
          title="Terugzetten, zodat je er opnieuw over kunt beslissen"
          onClick={() => void stuur(() => bediening.beslis(r, "heropen"))}>Heropenen</Button>
      )}
    </>
  );

  return (
    <LijstRij data-relatie={r.id}
      titel={<span className="text-sm"><span className="text-muted">{zin}</span> <AndereKant ep={ander} /></span>}
      status={bediening && eigenRelatie(r, gebruiker) && (
        <IcoonBevestig soort="verwijderen" vraag="Wissen?" label={`Wis relatie: ${naam}`} disabled={bezig}
          onBevestig={async () => { await stuur(() => bediening.wis(r)); }} />
      )}
      meta={<>
        {relatieStatus(r, gebruiker)}
        {r.volgorde != null && ` · plek ${r.volgorde}`}
        {r.toelichting ? ` – ${r.toelichting}` : ""}
        {r.veranderd && (
          <span className="mt-0.5 flex items-center gap-1 text-aandacht-geel-tekst">
            <Waarschuwing /> Een eindpunt is veranderd sinds deze relatie werd vastgelegd. Klopt ze nog?
          </span>
        )}
      </>}
      acties={acties || undefined}>
      {afwijzen && bediening && (
        <form className="mt-2" aria-label={`Afwijzen: ${naam}`} onSubmit={async (e) => {
          e.preventDefault();
          if (await stuur(() => bediening.beslis(r, "reject", reden.trim()))) { setAfwijzen(false); setReden(""); }
        }}>
          <Input autoFocus value={reden} onChange={(e) => setReden(e.target.value)} maxLength={2000}
            placeholder="Waarom niet? (mag leeg)" aria-label={`Reden om “${naam}” af te wijzen`} />
          <BewerkVoet submit onAnnuleer={() => { setAfwijzen(false); setReden(""); }} bezig={bezig} gewijzigd
            opslaanTekst="Afwijzen" />
        </form>
      )}
    </LijstRij>
  );
}

const sleutel = (k: Verbindbaar) => `${k.ref.soort}:${k.ref.id}`;
const keuzeSleutel = (k: TypeKeuze) => `${k.richting}:${k.code}`;

/** *Verbind met…*: kies een andere markering in beeld of een impliciete partij, dan het type. De typen komen uit de
 *  catalogus (`typenTussen` op het klassenpaar), in beide richtingen; de zin eronder zegt welke kant van en welke naar is.
 *  Geen zoekvenster: wat niet in beeld staat, haal je via het gesprek. De velden staan onder elkaar, want de kaart is
 *  smal. */
function Verbind({ dit, anderen, onLeg, onSluit }: {
  dit: Verbindbaar;
  anderen: readonly Verbindbaar[];
  onLeg: (invoer: RelatieInvoer) => Promise<unknown>;
  onSluit: () => void;
}) {
  const [anderKey, setAnderKey] = useState("");
  const [typeKey, setTypeKey] = useState("");
  const [volgorde, setVolgorde] = useState("");
  const [toelichting, setToelichting] = useState("");
  const [bezig, setBezig] = useState(false);
  const ander = anderen.find((k) => sleutel(k) === anderKey);
  const keuzes = ander ? typeKeuzes(dit, ander) : [];
  const keuze = keuzes.find((k) => keuzeSleutel(k) === typeKey);
  const [van, naar] = keuze?.richting === "in" ? [ander!, dit] : [dit, ander];
  const plek = keuze?.volgorde && volgorde.trim() ? Number(volgorde) : null;
  const plekGeldig = plek === null || (Number.isInteger(plek) && plek >= 1 && plek <= 99);
  const kort = (k: Verbindbaar) => (k.impliciet ? k.naam : `“${k.naam.length > 50 ? `${k.naam.slice(0, 47)}…` : k.naam}”`);

  return (
    <form aria-label="Verbind met een andere markering" className="space-y-2 border-t border-line pt-3" onSubmit={async (e) => {
      e.preventDefault();
      if (!ander || !keuze || !plekGeldig) return;
      setBezig(true);
      try {
        await onLeg({ van: van!.ref, naar: naar!.ref, type: keuze.code, volgorde: plek,
          toelichting: toelichting.trim() });
      } finally { setBezig(false); }
    }}>
      <Select value={anderKey} aria-label="Andere kant" onChange={(e) => { setAnderKey(e.target.value); setTypeKey(""); }}>
        <option value="">Kies een markering of partij…</option>
        {anderen.map((k) => (
          <option key={sleutel(k)} value={sleutel(k)}>
            {k.impliciet ? `${k.naam} (impliciet)` : `${k.klasse}: ${kort(k)}`}
          </option>
        ))}
      </Select>
      {ander && (
        <Select value={typeKey} aria-label="Soort relatie" onChange={(e) => setTypeKey(e.target.value)}>
          <option value="">Kies hoe ze samenhangen…</option>
          {(["uit", "in"] as const).map((richting) => {
            const groep = keuzes.filter((k) => k.richting === richting);
            return groep.length > 0 && (
              <optgroup key={richting} label={richting === "uit" ? "Dit element is de van-kant" : "De andere kant is de van-kant"}>
                {groep.map((k) => <option key={keuzeSleutel(k)} value={keuzeSleutel(k)}>{k.leesvorm}</option>)}
              </optgroup>
            );
          })}
        </Select>
      )}
      {keuze && (
        <p className="text-xs text-muted" data-verbind-zin>
          Zo leest het: <span className="text-ink">{kort(van!)} {keuze.leesvorm} {kort(naar!)}</span>. Van is {kort(van!)},
          naar is {kort(naar!)}.
        </p>
      )}
      {keuze?.volgorde && (
        <label className="block text-xs text-muted">
          Plek (optioneel). Bij een bewerking telt de volgorde: A min B is niet B min A.
          <Input type="number" min={1} max={99} inputMode="numeric" value={volgorde} className="mt-1"
            onChange={(e) => setVolgorde(e.target.value)} aria-label="Plek in de volgorde" />
        </label>
      )}
      {keuze && (
        <Input value={toelichting} onChange={(e) => setToelichting(e.target.value)} maxLength={2000}
          placeholder="Toelichting (optioneel)" aria-label="Toelichting bij de relatie" />
      )}
      <BewerkVoet submit onAnnuleer={onSluit} bezig={bezig} gewijzigd={!!keuze && plekGeldig} opslaanTekst="Verbinden" />
    </form>
  );
}

/** De impliciete partijen bij de bepaling (ADR-011): een rechtssubject dat de tekst niet noemt, maar wel meedoet. Alleen
 *  de jurist maakt er een, met een verplichte toelichting; daarna is ze te kiezen bij *Verbind met…*. Geen markering:
 *  ze telt niet in de review. */
export function ImplicietePartijen({ partijen, gebruiker, onMaak, onWis }: {
  partijen: readonly NodeImpliciet[];
  gebruiker?: string;
  /** Weglaten maakt het blok alleen-lezen. */
  onMaak?: (invoer: { label: string; toelichting: string }) => Promise<void>;
  onWis?: (partij: NodeImpliciet) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [toelichting, setToelichting] = useState("");
  const [bezig, setBezig] = useState(false);
  const [fout, setFout] = useState("");
  if (!partijen.length && !onMaak) return null;
  const sluit = () => { setOpen(false); setLabel(""); setToelichting(""); setFout(""); };

  return (
    <Sectie niveau={3} titel="Impliciete partijen" telling={partijen.length} data-impliciet
      className="rounded-kaart border border-line bg-surface/60 px-3 py-2"
      toelichting="Een rechtssubject dat de tekst niet noemt, maar wel meedoet. Je verbindt het daarna met een markering."
      acties={onMaak && !open && <Button size="xs" variant="secondary" onClick={() => setOpen(true)}>Partij toevoegen</Button>}>
      {fout && !open && <p role="alert" className="text-xs text-fout">{fout}</p>}
      {partijen.length > 0 && (
        <Lijst label="Impliciete partijen">
          {partijen.map((p) => (
            <LijstRij key={p.id} data-impliciete-partij={p.id}
              titel={<><span className="font-medium">{p.label}</span> <StatusLabel klein>impliciet</StatusLabel></>}
              meta={<>{p.toelichting}{p.aangemaakt_door ? ` · door ${p.aangemaakt_door === gebruiker ? "jou" : p.aangemaakt_door}` : ""}</>}
              status={onWis && gebruiker && p.aangemaakt_door === gebruiker && (
                <IcoonBevestig soort="verwijderen" vraag="Wissen?" label={`Wis partij: ${p.label}`}
                  onBevestig={async () => {
                    setFout("");
                    try { await onWis(p); } catch (e) { setFout(foutTekst(e, "Wissen lukte niet.")); }
                  }} />
              )} />
          ))}
        </Lijst>
      )}
      {open && onMaak && (
        <form aria-label="Impliciete partij toevoegen" className="space-y-2" onSubmit={async (e) => {
          e.preventDefault();
          if (!label.trim() || !toelichting.trim()) return;
          setBezig(true);
          setFout("");
          try { await onMaak({ label: label.trim(), toelichting: toelichting.trim() }); sluit(); }
          catch (e) { setFout(foutTekst(e, "Toevoegen lukte niet.")); }
          finally { setBezig(false); }
        }}>
          <Input autoFocus value={label} onChange={(e) => setLabel(e.target.value)} maxLength={200}
            placeholder="Naam, bijvoorbeeld: de belastingschuldige" aria-label="Naam van de partij" />
          <Textarea value={toelichting} onChange={(e) => setToelichting(e.target.value)} maxLength={2000} rows={2}
            placeholder="Waaruit volgt dat deze partij meedoet? (verplicht)" aria-label="Waaruit volgt de partij" />
          <BewerkVoet submit onAnnuleer={sluit} bezig={bezig} gewijzigd={!!label.trim() && !!toelichting.trim()}
            opslaanTekst="Toevoegen" fout={fout} />
        </form>
      )}
    </Sectie>
  );
}
