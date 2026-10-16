"use client";

import { useCallback, useEffect, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import {
  bevestigRelatie, combineerBegrippen, foutTekst, geefNieuweBetekenis, haalRelaties, legRelatieVast, verwijderRelatie,
  wijsRelatieAf,
} from "@/lib/api";
import {
  HERKOMST_LABEL, KEUZES, TYPE_LABEL, magVastleggen, ordenRelaties, relatieInvoer, relatieZin,
} from "@/lib/begripRelaties";
import type { Begrip, BegripRelatie, BegripSamenvatting, RelatiesAntwoord } from "@/lib/types";
import { isRevisieConflict } from "@/lib/werkgebied";

const KNOP =
  "focus-ring inline-flex min-h-[24px] items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50 coarse:min-h-[44px]";

/** Relaties met andere begrippen en de opvolging (fase F2). Een relatie is een eigen object met type en
 *  richting: "belastingaanslag omvat ook navorderingsaanslag", nooit alleen "verwant". Voorstellen van
 *  Lex staan geel, met de passages waarop ze rusten; de analist legt vast of wijst af.
 *
 *  *Nieuwe betekenis* en *Combineren* leveren een ander begrip op; daarna opent de tab dat begrip. Het
 *  oude wordt vervangen: alleen-lezen en vindbaar, en terug te halen door de opvolger te verwijderen. */
export function BegripRelaties({ id, begrip, andere, onGewijzigd, onNaarBegrip }: {
  id: string;
  begrip: Begrip;
  andere: readonly BegripSamenvatting[];
  onGewijzigd: () => void;
  onNaarBegrip?: (begripId: string) => void;
}) {
  const [data, setData] = useState<RelatiesAntwoord | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const vervangen = begrip.status === "vervangen";

  const laad = useCallback(async () => {
    setData(await haalRelaties(id, begrip.id).catch(() => null));
  }, [id, begrip.id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad, begrip.revisie]);

  async function doe(actie: () => Promise<RelatiesAntwoord>, gelukt: string) {
    setFout(null);
    setMelding(null);
    try {
      await actie();
      await laad();
      setMelding(gelukt);
      onGewijzigd();
      return true;
    } catch (e) {
      setFout(foutTekst(e));
      return false;
    }
  }

  const kandidaten = andere.filter((b) => b.id !== begrip.id && b.status !== "vervangen");
  const { vastgelegd, afgewezen } = ordenRelaties(data?.relaties ?? []);

  return (
    <section aria-label="Relaties en opvolging" className="space-y-3 rounded-kaart border border-line bg-paper p-4">
      <h3 className="font-display text-sm font-semibold text-lint">Relaties</h3>
      {begrip.vervangen_door && (
        <Melding type="uitleg" compact>
          Vervangen door{" "}
          <button type="button" className="focus-ring rounded text-lint underline" onClick={() => onNaarBegrip?.(begrip.vervangen_door!.begrip_id)}>
            {begrip.vervangen_door.naam}
          </button>
          {begrip.vervangen_door.reden && <> – {begrip.vervangen_door.reden}</>}. Dit begrip is alleen nog te lezen.
        </Melding>
      )}
      {(begrip.vervangt?.length ?? 0) > 0 && (
        <p className="text-xs text-muted">
          Vervangt{" "}
          {begrip.vervangt!.map((v, i) => (
            <span key={v.begrip_id}>
              {i > 0 && ", "}
              <button type="button" className="focus-ring rounded text-lint underline" onClick={() => onNaarBegrip?.(v.begrip_id)}>
                {v.naam}
              </button>
              {v.reden && ` (${v.reden})`}
            </span>
          ))}
          . Verwijder je dit begrip, dan krijgt het oude zijn status terug.
        </p>
      )}
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {melding && <Melding type="bevestiging" compact>{melding}</Melding>}

      {data && data.voorstellen.length > 0 && !vervangen && (
        <ul className="space-y-2" aria-label="Voorgestelde relaties">
          {data.voorstellen.map((v) => (
            <VoorstelRij key={v.id} voorstel={v}
              onAkkoord={() => doe(() => legRelatieVast(id, { voorstel_id: v.id }), "Relatie vastgelegd.")}
              onAfwijzen={(reden) => doe(() => wijsRelatieAf(id, v.id, reden), "Voorstel afgewezen; Lex stelt het niet opnieuw voor.")} />
          ))}
        </ul>
      )}

      {vastgelegd.length === 0 && !data?.voorstellen.length ? (
        <p className="text-sm text-muted">Nog geen relaties met andere begrippen.</p>
      ) : (
        <ul className="space-y-1.5" aria-label="Vastgelegde relaties">
          {vastgelegd.map((r) => (
            <RelatieRij key={r.id} relatie={r} vervangen={vervangen}
              onBevestig={() => doe(() => bevestigRelatie(id, r.id), "Relatie bevestigd.")}
              onWeg={() => doe(() => verwijderRelatie(id, r.id), "Relatie weggehaald.")} />
          ))}
        </ul>
      )}
      {afgewezen.length > 0 && (
        <details className="text-xs text-muted">
          <summary className="focus-ring cursor-pointer rounded">Afgewezen voorstellen ({afgewezen.length})</summary>
          <ul className="mt-1 space-y-0.5">
            {afgewezen.map((r) => (
              <li key={r.id}>{relatieZin(r.type, r.van_naam, r.naar_naam).join(" ")} – {r.toelichting}</li>
            ))}
          </ul>
        </details>
      )}

      {!vervangen && kandidaten.length > 0 && (
        <NieuweRelatie dit={begrip} kandidaten={kandidaten}
          onVastleggen={(keuze, ander, toelichting) => doe(
            () => legRelatieVast(id, relatieInvoer(keuze, begrip.id, ander, toelichting)), "Relatie vastgelegd.")} />
      )}

      {!vervangen && (
        <Opvolging id={id} begrip={begrip} kandidaten={kandidaten} onFout={setFout}
          onKlaar={(naar) => { onGewijzigd(); onNaarBegrip?.(naar); }} />
      )}
    </section>
  );
}

function Zin({ r }: { r: Pick<BegripRelatie, "type" | "van_naam" | "naar_naam"> }) {
  const [links, verband, rechts] = relatieZin(r.type, r.van_naam, r.naar_naam);
  return (
    <span className="text-sm text-ink">
      <span className="font-medium">{links}</span> {verband} <span className="font-medium">{rechts}</span>
    </span>
  );
}

function VoorstelRij({ voorstel: v, onAkkoord, onAfwijzen }: {
  voorstel: BegripRelatie;
  onAkkoord: () => Promise<boolean>;
  onAfwijzen: (reden: string) => Promise<boolean>;
}) {
  const [afwijzen, setAfwijzen] = useState(false);
  const [reden, setReden] = useState("");
  const naam = relatieZin(v.type, v.van_naam, v.naar_naam).join(" ");
  return (
    <li className="space-y-1.5 rounded border border-aandacht-geel-rand bg-aandacht-geel-bg/40 px-2.5 py-2">
      <div className="flex flex-wrap items-baseline gap-x-2"><Zin r={v} />
        <span className="text-[11px] text-aandacht-geel-tekst">{HERKOMST_LABEL.lex} · {TYPE_LABEL[v.type]}</span></div>
      {(v.bewijs.van || v.bewijs.naar) && (
        <p className="text-xs text-muted">
          Uit de passages {v.bewijs.van && <>“{v.bewijs.van.tekst}” ({v.bewijs.van.vindplaats})</>}
          {v.bewijs.van && v.bewijs.naar && " en "}
          {v.bewijs.naar && <>“{v.bewijs.naar.tekst}” ({v.bewijs.naar.vindplaats})</>}
          {v.bewijs.uitleg?.length ? ` – ${v.bewijs.uitleg.join("; ")}` : ""}
        </p>
      )}
      {afwijzen ? (
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => {
          e.preventDefault();
          if (reden.trim()) void onAfwijzen(reden.trim());
        }}>
          <Input autoFocus value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom niet"
            aria-label={`Reden om “${naam}” af te wijzen`} maxLength={2000} />
          <Button type="submit" size="sm" variant="secondary" disabled={!reden.trim()} className="w-full sm:w-auto">Afwijzen</Button>
        </form>
      ) : (
        <div className="flex gap-1.5">
          <button type="button" className={`${KNOP} border-lint text-lint hover:bg-surface`} aria-label={`Leg vast: ${naam}`}
            onClick={() => void onAkkoord()}>Akkoord</button>
          <button type="button" className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`}
            aria-label={`Wijs af: ${naam}`} onClick={() => setAfwijzen(true)}>Afwijzen</button>
        </div>
      )}
    </li>
  );
}

function RelatieRij({ relatie: r, vervangen, onBevestig, onWeg }: {
  relatie: BegripRelatie;
  vervangen: boolean;
  onBevestig: () => Promise<boolean>;
  onWeg: () => Promise<boolean>;
}) {
  const naam = relatieZin(r.type, r.van_naam, r.naar_naam).join(" ");
  return (
    <li className={`rounded border px-2.5 py-1.5 ${r.veranderd ? "border-aandacht-geel-rand bg-aandacht-geel-bg/40" : "border-line"}`}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <Zin r={r} />
          <span className="block text-[11px] text-muted">
            {TYPE_LABEL[r.type]} · {HERKOMST_LABEL[r.herkomst]}{r.door ? ` · ${r.door}` : ""}{r.toelichting ? ` – ${r.toelichting}` : ""}
          </span>
          {r.veranderd && (
            <span className="block text-[11px] text-aandacht-geel-tekst">
              Een van beide begrippen veranderde sinds het vastleggen; klopt de relatie nog?
            </span>
          )}
        </div>
        {!vervangen && (
          <span className="flex shrink-0 gap-1.5">
            {r.veranderd && (
              <button type="button" className={`${KNOP} border-lint text-lint hover:bg-surface`} aria-label={`Klopt nog: ${naam}`}
                onClick={() => void onBevestig()}>Klopt nog</button>
            )}
            <BevestigKnop bevestigTekst="Weghalen?" ariaLabel={`Haal weg: ${naam}`} onBevestig={async () => { await onWeg(); }}
              className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`} bevestigClassName="border-fout/40 text-fout">
              Weghalen
            </BevestigKnop>
          </span>
        )}
      </div>
    </li>
  );
}

function NieuweRelatie({ dit, kandidaten, onVastleggen }: {
  dit: Begrip;
  kandidaten: readonly BegripSamenvatting[];
  onVastleggen: (keuze: string, ander: string, toelichting: string) => Promise<boolean>;
}) {
  const [keuze, setKeuze] = useState(KEUZES[0].waarde);
  const [ander, setAnder] = useState("");
  const [toelichting, setToelichting] = useState("");
  const mag = magVastleggen(keuze, dit.id, ander, toelichting);
  return (
    <form aria-label="Relatie toevoegen" className="space-y-2 border-t border-line pt-3" onSubmit={async (e) => {
      e.preventDefault();
      if (mag && await onVastleggen(keuze, ander, toelichting)) { setAnder(""); setToelichting(""); }
    }}>
      <p className="text-xs font-medium text-ink">Relatie toevoegen</p>
      {/* De kaart staat vanaf xl in een halve kolom: de velden volgen die breedte, niet het scherm. */}
      <p className="text-sm font-medium text-ink">{dit.inhoud.naam}</p>
      <div className="grid min-w-0 gap-2 sm:grid-cols-2">
        <Select value={keuze} onChange={(e) => setKeuze(e.target.value)} aria-label="Soort relatie" className="min-w-0">
          {KEUZES.map((k) => <option key={k.waarde} value={k.waarde}>{k.label}</option>)}
        </Select>
        <Select value={ander} onChange={(e) => setAnder(e.target.value)} aria-label="Ander begrip" className="min-w-0">
          <option value="">Kies een begrip…</option>
          {kandidaten.map((b) => <option key={b.id} value={b.id}>{b.inhoud.naam}</option>)}
        </Select>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input value={toelichting} onChange={(e) => setToelichting(e.target.value)}
          placeholder={keuze === "verwant" ? "Toelichting (verplicht bij verwant)" : "Toelichting (optioneel)"}
          aria-label="Toelichting bij de relatie" maxLength={4000} />
        <Button type="submit" size="sm" variant="secondary" disabled={!mag} className="w-full sm:w-auto">Vastleggen</Button>
      </div>
    </form>
  );
}

/** Nieuwe betekenis en combineren. Beide maken het ene begrip `vervangen`; de vergelijking staat vooraf in
 *  beeld, zodat de analist ziet welke definitie blijft. */
function Opvolging({ id, begrip, kandidaten, onFout, onKlaar }: {
  id: string;
  begrip: Begrip;
  kandidaten: readonly BegripSamenvatting[];
  onFout: (f: string) => void;
  onKlaar: (begripId: string) => void;
}) {
  const [open, setOpen] = useState<"nieuw" | "combineren" | null>(null);
  const [reden, setReden] = useState("");
  const [ander, setAnder] = useState("");
  const [blijft, setBlijft] = useState<"dit" | "ander">("dit");
  const [bezig, setBezig] = useState(false);
  const a = kandidaten.find((b) => b.id === ander);

  async function voer(actie: () => Promise<Begrip>) {
    setBezig(true);
    try {
      const b = await actie();
      setOpen(null);
      setReden("");
      onKlaar(b.id);
    } catch (e) {
      onFout(isRevisieConflict(e) ? "Een van beide begrippen veranderde net; laad opnieuw en kijk of het nog klopt."
        : foutTekst(e));
    } finally {
      setBezig(false);
    }
  }

  return (
    <div className="space-y-2 border-t border-line pt-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="button" size="sm" variant="secondary" aria-expanded={open === "nieuw"} className="w-full sm:w-auto"
          onClick={() => setOpen(open === "nieuw" ? null : "nieuw")}>Nieuwe betekenis</Button>
        {kandidaten.length > 0 && (
          <Button type="button" size="sm" variant="secondary" aria-expanded={open === "combineren"} className="w-full sm:w-auto"
            onClick={() => setOpen(open === "combineren" ? null : "combineren")}>Combineren met…</Button>
        )}
      </div>
      {open === "nieuw" && (
        <form aria-label="Nieuwe betekenis" className="space-y-2" onSubmit={(e) => {
          e.preventDefault();
          if (reden.trim()) void voer(() => geefNieuweBetekenis(id, begrip.id, { verwachte_revisie: begrip.revisie, reden: reden.trim() }));
        }}>
          <p className="text-xs text-muted">
            Een andere betekenis is een nieuw begrip. De opvolger krijgt deze kaart en de passages (opnieuw ter
            beoordeling); dit begrip wordt vervangen en blijft te lezen. Een tekstuele verbetering doe je gewoon op de kaart.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input autoFocus value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom de betekenis verandert"
              aria-label="Reden voor de nieuwe betekenis" maxLength={2000} />
            <Button type="submit" size="sm" disabled={bezig || !reden.trim()} className="w-full sm:w-auto">Maak opvolger</Button>
          </div>
        </form>
      )}
      {open === "combineren" && (
        <form aria-label="Combineren" className="space-y-2" onSubmit={(e) => {
          e.preventDefault();
          if (!a || !reden.trim()) return;
          void voer(() => blijft === "dit"
            ? combineerBegrippen(id, begrip.id, { verwachte_revisie: begrip.revisie, ander_begrip_id: a.id, ander_revisie: a.revisie, reden: reden.trim() })
            : combineerBegrippen(id, a.id, { verwachte_revisie: a.revisie, ander_begrip_id: begrip.id, ander_revisie: begrip.revisie, reden: reden.trim() }));
        }}>
          <Select value={ander} onChange={(e) => setAnder(e.target.value)} aria-label="Combineren met">
            <option value="">Kies een begrip…</option>
            {kandidaten.map((b) => <option key={b.id} value={b.id}>{b.inhoud.naam}</option>)}
          </Select>
          {a && (
            <>
              <div role="radiogroup" aria-label="Welk begrip blijft" className="grid gap-2 sm:grid-cols-2">
                {([["dit", begrip.inhoud], ["ander", a.inhoud]] as const).map(([w, inh]) => (
                  <label key={w} className={`cursor-pointer rounded border p-2 text-xs ${blijft === w ? "border-lint" : "border-line"}`}>
                    <input type="radio" name="blijft" className="focus-ring mr-1.5 accent-lint" checked={blijft === w}
                      onChange={() => setBlijft(w)} />
                    <span className="font-medium text-ink">{inh.naam}</span> blijft
                    <span className="mt-1 block text-muted">{inh.definitie || "Nog geen definitie."}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-muted">
                Het begrip dat blijft krijgt de passages van het andere (opnieuw ter beoordeling) en diens naam als
                alternatieve term; het andere wordt vervangen.
              </p>
            </>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom dit één begrip is"
              aria-label="Reden om te combineren" maxLength={2000} />
            <Button type="submit" size="sm" disabled={bezig || !a || !reden.trim()} className="w-full sm:w-auto">Combineren</Button>
          </div>
        </form>
      )}
    </div>
  );
}
