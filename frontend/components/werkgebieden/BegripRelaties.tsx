"use client";

import { useCallback, useEffect, useState } from "react";

import { BewerkVoet } from "@/components/ui/Bewerkbaar";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { IcoonBevestig } from "@/components/ui/IcoonBevestig";
import { Lijst, LijstRij, Voorstel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { BegripBlok, type BegripWeergaveVorm } from "@/components/werkgebieden/BegripBlok";
import {
  bevestigRelatie, foutTekst, haalRelaties, legRelatieVast, verwijderRelatie, wijsRelatieAf,
} from "@/lib/api";
import {
  HERKOMST_LABEL, KEUZES, TYPE_LABEL, magVastleggen, ordenRelaties, relatieInvoer, relatieZin,
} from "@/lib/begripRelaties";
import type { Begrip, BegripRelatie, BegripSamenvatting, RelatiesAntwoord } from "@/lib/types";

/** Relaties met andere begrippen (fase F2). Een relatie is een eigen object met type en richting: "belastingaanslag
 *  omvat ook navorderingsaanslag", nooit alleen "verwant". Voorstellen van Lex staan geel, met de passages waarop ze
 *  rusten; de analist legt vast of wijst af. Nieuwe betekenis en combineren staan in het menu van het begrip. */
export function BegripRelaties({ id, begrip, andere, onGewijzigd, onNaarBegrip, weergave }: {
  id: string;
  begrip: Begrip;
  andere: readonly BegripSamenvatting[];
  onGewijzigd: () => void;
  onNaarBegrip?: (begripId: string) => void;
  weergave: BegripWeergaveVorm;
}) {
  const [data, setData] = useState<RelatiesAntwoord | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [toevoegen, setToevoegen] = useState(false);
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
  const voorstellen = !vervangen ? data?.voorstellen ?? [] : [];

  return (
    <BegripBlok weergave={weergave} titel="Relaties" telling={vastgelegd.length} aria-label="Relaties" data-blok="relaties"
      acties={!vervangen && kandidaten.length > 0 && !toevoegen && (
        <Button size="xs" variant="secondary" onClick={() => setToevoegen(true)}>Relatie toevoegen</Button>
      )}>
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

      {voorstellen.length > 0 && (
        <Lijst label="Voorgestelde relaties">
          {voorstellen.map((v) => (
            <VoorstelRij key={v.id} voorstel={v}
              onAkkoord={() => doe(() => legRelatieVast(id, { voorstel_id: v.id }), "Relatie vastgelegd.")}
              onAfwijzen={(reden) => doe(() => wijsRelatieAf(id, v.id, reden), "Voorstel afgewezen; Lex stelt het niet opnieuw voor.")} />
          ))}
        </Lijst>
      )}

      {vastgelegd.length > 0 ? (
        <Lijst label="Vastgelegde relaties">
          {vastgelegd.map((r) => (
            <RelatieRij key={r.id} relatie={r} vervangen={vervangen}
              onBevestig={() => doe(() => bevestigRelatie(id, r.id), "Relatie bevestigd.")}
              onWeg={() => doe(() => verwijderRelatie(id, r.id), "Relatie verwijderd.")} />
          ))}
        </Lijst>
      ) : !voorstellen.length && <p className="text-sm text-muted">Nog geen relaties met andere begrippen.</p>}
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

      {toevoegen && (
        <NieuweRelatie dit={begrip} kandidaten={kandidaten} onSluit={() => setToevoegen(false)}
          onVastleggen={(keuze, ander, toelichting) => doe(
            () => legRelatieVast(id, relatieInvoer(keuze, begrip.id, ander, toelichting)), "Relatie vastgelegd.")} />
      )}
    </BegripBlok>
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
    <Voorstel titel={<Zin r={v} />}
      acties={!afwijzen && <>
        <Button size="xs" variant="secondary" aria-label={`Leg vast: ${naam}`} onClick={() => void onAkkoord()}>Akkoord</Button>
        <Button size="xs" variant="ghost" aria-label={`Wijs af: ${naam}`} onClick={() => setAfwijzen(true)}>Afwijzen</Button>
      </>}>
      <p className="mt-0.5 text-xs text-aandacht-geel-tekst">{HERKOMST_LABEL.lex} · {TYPE_LABEL[v.type]}</p>
      {(v.bewijs.van || v.bewijs.naar) && (
        <p className="mt-1 text-xs text-muted">
          Uit de passages {v.bewijs.van && <>“{v.bewijs.van.tekst}” ({v.bewijs.van.vindplaats})</>}
          {v.bewijs.van && v.bewijs.naar && " en "}
          {v.bewijs.naar && <>“{v.bewijs.naar.tekst}” ({v.bewijs.naar.vindplaats})</>}
          {v.bewijs.uitleg?.length ? ` – ${v.bewijs.uitleg.join("; ")}` : ""}
        </p>
      )}
      {afwijzen && (
        <form className="mt-2 space-y-2" onSubmit={(e) => {
          e.preventDefault();
          if (reden.trim()) void onAfwijzen(reden.trim());
        }}>
          <Input autoFocus value={reden} onChange={(e) => setReden(e.target.value)} placeholder="Waarom niet"
            aria-label={`Reden om “${naam}” af te wijzen`} maxLength={2000} />
          <Button type="submit" size="sm" variant="secondary" disabled={!reden.trim()} className="w-full sm:w-auto">Afwijzen</Button>
        </form>
      )}
    </Voorstel>
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
    <LijstRij titel={<Zin r={r} />}
      status={!vervangen && <IcoonBevestig soort="verwijderen" label={`Verwijder: ${naam}`} onBevestig={async () => { await onWeg(); }} />}
      meta={<>
        {TYPE_LABEL[r.type]} · {HERKOMST_LABEL[r.herkomst]}{r.door ? ` · ${r.door}` : ""}{r.toelichting ? ` – ${r.toelichting}` : ""}
        {r.veranderd && (
          <span className="block text-aandacht-geel-tekst">Een van beide begrippen veranderde sinds het vastleggen; klopt de relatie nog?</span>
        )}
      </>}
      acties={r.veranderd && !vervangen && (
        <Button size="xs" variant="secondary" aria-label={`Klopt nog: ${naam}`} onClick={() => void onBevestig()}>Klopt nog</Button>
      )} />
  );
}

/** Een relatie vastleggen vanuit dit begrip. De velden staan onder elkaar: het blok staat in een smalle kolom. */
function NieuweRelatie({ dit, kandidaten, onVastleggen, onSluit }: {
  dit: Begrip;
  kandidaten: readonly BegripSamenvatting[];
  onVastleggen: (keuze: string, ander: string, toelichting: string) => Promise<boolean>;
  onSluit: () => void;
}) {
  const [keuze, setKeuze] = useState(KEUZES[0].waarde);
  const [ander, setAnder] = useState("");
  const [toelichting, setToelichting] = useState("");
  const mag = magVastleggen(keuze, dit.id, ander, toelichting);
  return (
    <form aria-label="Relatie toevoegen" className="space-y-2 border-t border-line pt-3" onSubmit={async (e) => {
      e.preventDefault();
      if (mag && await onVastleggen(keuze, ander, toelichting)) { setAnder(""); setToelichting(""); onSluit(); }
    }}>
      <p className="text-sm font-medium text-ink">{dit.inhoud.naam}</p>
      <Select value={keuze} onChange={(e) => setKeuze(e.target.value)} aria-label="Soort relatie">
        {KEUZES.map((k) => <option key={k.waarde} value={k.waarde}>{k.label}</option>)}
      </Select>
      <Select value={ander} onChange={(e) => setAnder(e.target.value)} aria-label="Ander begrip">
        <option value="">Kies een begrip…</option>
        {kandidaten.map((b) => <option key={b.id} value={b.id}>{b.inhoud.naam}</option>)}
      </Select>
      <Input value={toelichting} onChange={(e) => setToelichting(e.target.value)}
        placeholder={keuze === "verwant" ? "Toelichting (verplicht bij verwant)" : "Toelichting (optioneel)"}
        aria-label="Toelichting bij de relatie" maxLength={4000} />
      <BewerkVoet submit onAnnuleer={onSluit} bezig={false} gewijzigd={mag} opslaanTekst="Vastleggen" />
    </form>
  );
}
