"use client";

import { KNOP_XS } from "@/components/ui/Button";
import Link from "next/link";
import { useState } from "react";

import { Input } from "@/components/ui/Field";
import type { BegripMutatie } from "@/components/werkgebieden/BegripWerk";
import { bevestigKoppeling, herkoppel } from "@/lib/api";
import { ACTIE_LABEL, RICHTING_LABEL, RICHTING_TEKEN, markeer } from "@/lib/herbeoordeling";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Begrip, BronSignaal, GeraakteKoppeling, Opvolger } from "@/lib/types";
import { annotatieHref } from "@/lib/werkgebied";

const KNOP = KNOP_XS;

const RICHTING_KLEUR = {
  steun: "text-ink",
  tegen: "text-fout",
  onbeslist: "text-muted",
} as const;

/** Een dragende passage die veranderde (fase F1): wat er veranderde, de stand van toen naast die van
 *  nu, en wat de analist kan doen. Toen is het bewaarde bewijs en blijft staan, wat er ook gebeurt;
 *  herkoppelen en bevestigen zetten er een nieuwe stand naast. Een geaccordeerd begrip blijft daarbij
 *  geaccordeerd. */
export function Herbeoordeling({ id, begrip, geraakt: g, muteer }: {
  id: string;
  begrip: Begrip;
  geraakt: GeraakteKoppeling;
  muteer: BegripMutatie;
}) {
  const [motivatie, setMotivatie] = useState("");
  const [bezig, setBezig] = useState(false);

  async function doe(actie: (revisie: number) => Promise<Begrip>, gelukt: string) {
    setBezig(true);
    await muteer(actie, { gelukt });
    setBezig(false);
  }

  const kan = (a: GeraakteKoppeling["acties"][number]) => g.acties.includes(a);
  const wetGewijzigd = g.bron.filter((b) => b.stand !== "ongewijzigd");

  return (
    <div role="group" aria-label="Herbeoordelen" className="mt-2 space-y-3 rounded-kaart border border-aandacht-geel-rand bg-aandacht-geel-bg/40 p-3">
      <div>
        <p className="text-xs font-semibold text-aandacht-geel-tekst">Herbeoordelen</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-ink">
          {g.redenen.map((r) => <li key={r}>{r}</li>)}
        </ul>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Toen (bij koppelen)</p>
          <Stand tekst={g.toen.tekst} klasse={g.toen.klasse} />
          {g.bevestigingen.length > 0 && (
            <p className="mt-1 text-[11px] text-muted">
              Laatst bevestigd door {g.bevestigingen.at(-1)!.door}: “{g.bevestigingen.at(-1)!.tekst}”
            </p>
          )}
        </div>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Nu</p>
          {g.nu ? (
            <Stand tekst={g.nu.tekst} klasse={g.nu.klasse} extra={g.nu.verouderd ? "annotatie verouderd" : undefined} />
          ) : (
            <p className="text-sm text-muted">De annotatie bestaat niet meer.</p>
          )}
        </div>
      </div>

      {wetGewijzigd.map((b) => <Wettekst key={b.bron_iri} bron={b} />)}

      {g.opvolgers.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-ink">
            {g.opvolgers.length === 1 ? "Mogelijke opvolger" : `${g.opvolgers.length} mogelijke opvolgers`} – kies er
            zelf een; er wordt niets automatisch herkoppeld.
          </p>
          <ul className="space-y-1.5" aria-label="Mogelijke opvolgers">
            {g.opvolgers.map((o) => (
              <OpvolgerRij
                key={o.element_id}
                opvolger={o}
                bezig={bezig}
                kanHerkoppelen={kan("herkoppelen")}
                onHerkoppel={() => doe(
                  (r) => herkoppel(id, begrip.id, g.koppeling_id, {
                    verwachte_revisie: r, element_id: o.element_id, ...(motivatie.trim() ? { motivatie: motivatie.trim() } : {}),
                  }),
                  "Herkoppeld. De oude passage blijft als historie bij de nieuwe staan.",
                )}
              />
            ))}
          </ul>
        </div>
      )}

      {g.opnieuw_annoteren.length > 0 && (
        <p className="text-xs text-ink">
          De tekst op de gemarkeerde plek veranderde en er is nog geen nieuwe annotatie.{" "}
          {g.opnieuw_annoteren.map((iri) => (
            <Link key={iri} href={annotatieHref(iri)} className="focus-ring rounded text-lint underline">
              Annoteer {g.bron.find((b) => b.bron_iri === iri)?.vindplaats || "de bepaling"} opnieuw
            </Link>
          ))}
          ; daarna verschijnt hier de opvolger.
        </p>
      )}

      {(kan("herkoppelen") || kan("bevestigen")) && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input
            value={motivatie}
            onChange={(e) => setMotivatie(e.target.value)}
            placeholder="Toelichting (optioneel)"
            aria-label={`Toelichting bij het herbeoordelen van “${g.toen.tekst}”`}
            maxLength={4000}
          />
          {kan("bevestigen") && (
            <button
              type="button"
              disabled={bezig}
              className={`${KNOP} shrink-0 border-lint text-lint hover:bg-surface`}
              title="De passage veranderde, maar het begrip klopt nog. De oude bewijsstand blijft; de nieuwe komt ernaast."
              onClick={() => void doe(
                (r) => bevestigKoppeling(id, begrip.id, g.koppeling_id, {
                  verwachte_revisie: r, ...(motivatie.trim() ? { motivatie: motivatie.trim() } : {}),
                }),
                "Bevestigd. De oude bewijsstand blijft bewaard.",
              )}
            >
              {ACTIE_LABEL.bevestigen}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Stand({ tekst, klasse, extra }: { tekst: string; klasse: string; extra?: string }) {
  return (
    <div className="mt-0.5 space-y-0.5">
      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${jasStyle(klasse)}`}>
        {klasseLabel(klasse)}
      </span>
      <blockquote className="text-sm text-ink">“{tekst}”</blockquote>
      {extra && <p className="text-[11px] text-aandacht-geel-tekst">{extra}</p>}
    </div>
  );
}

/** De wettekst van nu, met het gemarkeerde fragment aangewezen als het er nog staat. */
function Wettekst({ bron: b }: { bron: BronSignaal }) {
  const plek = b.vindplaats || b.bron_iri;
  if (b.stand === "weg") return <p className="text-xs text-ink">{plek} staat niet meer in de wettekst.</p>;
  if (b.stand === "onbekend") return <p className="text-xs text-muted">De wettekst van {plek} was niet op te halen.</p>;
  const delen = markeer(b.tekst_nu ?? "", b.fragment);
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Wettekst nu · {plek}</p>
      <p className="mt-0.5 whitespace-pre-line text-sm text-ink">
        {delen ? (
          <>{delen[0]}<mark className="rounded bg-aandacht-geel-bg px-0.5 text-ink">{delen[1]}</mark>{delen[2]}</>
        ) : (
          b.tekst_nu
        )}
      </p>
      {!delen && <p className="text-[11px] text-aandacht-geel-tekst">Het gemarkeerde fragment “{b.fragment}” staat er niet meer.</p>}
    </div>
  );
}

function OpvolgerRij({ opvolger: o, bezig, kanHerkoppelen, onHerkoppel }: {
  opvolger: Opvolger;
  bezig: boolean;
  kanHerkoppelen: boolean;
  onHerkoppel: () => void;
}) {
  return (
    <li className="rounded border border-line bg-paper px-2.5 py-2">
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <span className={`mr-1.5 inline-flex rounded-full border px-1.5 text-[10px] ${jasStyle(o.klasse)}`}>{klasseLabel(o.klasse)}</span>
          <span className="text-sm text-ink">“{o.tekst}”</span>
          {!o.annotatie_beoordeeld && (
            <span className="block text-[11px] text-aandacht-geel-tekst">annotatie nog niet door een jurist beoordeeld</span>
          )}
          <ul className="mt-1 space-y-0.5" aria-label="Signalen">
            {o.signalen.map((s) => (
              <li key={s.uitleg} className={`text-[11px] ${RICHTING_KLEUR[s.richting]}`}>
                <span aria-hidden="true" className="mr-1 font-semibold">{RICHTING_TEKEN[s.richting]}</span>
                <span className="sr-only">{RICHTING_LABEL[s.richting]}: </span>
                {s.uitleg}
              </li>
            ))}
          </ul>
        </div>
        {kanHerkoppelen && (
          <button
            type="button"
            disabled={bezig}
            onClick={onHerkoppel}
            aria-label={`Herkoppel aan “${o.tekst}”`}
            className={`${KNOP} shrink-0 self-start border-lint text-lint hover:bg-surface`}
          >
            {ACTIE_LABEL.herkoppelen}
          </button>
        )}
      </div>
    </li>
  );
}
