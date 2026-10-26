"use client";

import { Lijst, LijstRij, Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { STAND_LABEL, STAND_TOON, STAND_UITLEG, dekkingZin, splits } from "@/lib/deelvragen";
import type { Werkgebied } from "@/lib/types";
import { useDeelvragenDekking } from "@/lib/useDeelvragenDekking";
import { DOSSIER_VELDEN } from "@/lib/werkgebied";
import { metLeesbareBronnen } from "@/lib/bronKandidaten";

/** Wat het werkgebied is, in één oogopslag: het dossier in de volgorde van de methode (aanleiding,
 *  context, doel, analysevraag, praktijkvoorbeeld, afbakening), de actieve deelvragen met hun stand en de
 *  bronnen die geanalyseerd worden. In de lijststijl van de samenvatting op de vraagkaart.
 *
 *  Eén samenvatting op twee plekken (F3a): het paneel naast het gesprek en de kop van de werkgebiedpagina.
 *  Een leeg veld staat er ook, zodat zichtbaar is wat er nog ontbreekt – met *Vraag Lex*, die het veld
 *  laat aanvullen met de vraagkaarten (de suggestie *Vul … aan*). */
export function WerkgebiedSamenvatting({ wg, vraagLex = false, className = "" }: {
  wg: Werkgebied;
  /** *Vraag Lex* bij elke deelvraag (F3d) en bij elk leeg dossierveld: in de werkplek zet hij het object als
   *  onderwerp, daarbuiten opent hij een gesprek. */
  vraagLex?: boolean;
  className?: string;
}) {
  const deelvragen = splits(wg.deelvragen).actief;
  const dekking = useDeelvragenDekking(wg.id, wg.revisie, deelvragen.length);
  const analyse = wg.bronnen.filter((b) => b.rol === "analyseren");
  const stand = new Map((dekking?.deelvragen ?? []).map((d) => [d.id, d.stand]));
  return (
    <Regels data-werkgebied-samenvatting className={`text-sm ${className}`}>
      {DOSSIER_VELDEN.map(({ veld, label }) => (
        <Regel key={veld} naam={label} data-dossier-veld={veld}>
          {(wg[veld] ?? "").trim()
            ? <span className="whitespace-pre-line">{metLeesbareBronnen(wg[veld] ?? "")}</span>
            : (
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-muted">{`Nog geen ${label.toLowerCase()}.`}</span>
                {vraagLex && (
                  <VraagLexKnop alleenInGesprek naam={`Vraag Lex: ${label.toLowerCase()} aanvullen`}
                    onderwerp={{ soort: "werkgebied", werkgebied_id: wg.id, id: "", label: wg.naam, veld }} />
                )}
              </span>
            )}
        </Regel>
      ))}
      <Regel naam={`Deelvragen (${deelvragen.length})`} data-samenvatting="deelvragen">
        {deelvragen.length ? (
          <>
            <Lijst genummerd label="Deelvragen" className="-my-1.5">
              {deelvragen.map((d, i) => {
                const s = stand.get(d.id);
                return (
                  <LijstRij key={d.id} className="py-1.5" voor={`${i + 1}.`} titel={d.vraag} data-samenvatting-deelvraag={d.id}
                    acties={vraagLex ? <VraagLexKnop alleenInGesprek onderwerp={{ soort: "deelvraag", werkgebied_id: wg.id, id: d.id, label: d.vraag }} />
                      : undefined}
                    status={s && (
                      <StatusLabel toon={STAND_TOON[s]} uitleg={STAND_UITLEG[s]} data-samenvatting-stand={s}>
                        {STAND_LABEL[s]}
                      </StatusLabel>
                    )} />
                );
              })}
            </Lijst>
            {dekkingZin(dekking) && <p className="mt-1.5 text-xs text-muted">{dekkingZin(dekking)}</p>}
          </>
        ) : (
          <span className="text-muted">Nog geen deelvragen.</span>
        )}
      </Regel>
      <Regel naam={`Bronnen (${analyse.length})`} data-samenvatting="bronnen">
        {analyse.length ? (
          <ul className="space-y-0.5">
            {analyse.map((b) => <li key={b.id}>{b.label || b.bron_iri}</li>)}
          </ul>
        ) : (
          <span className="text-muted">Nog geen bronnen.</span>
        )}
      </Regel>
    </Regels>
  );
}
