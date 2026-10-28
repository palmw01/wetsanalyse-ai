"use client";

import Link from "next/link";
import { useContext } from "react";

import { themaLabel } from "@/lib/tooiThemas";
import { bronHref } from "@/lib/url";
import { Lijst, LijstRij, Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { VraagLexContext } from "@/components/werkplek/VraagLexKnop";
import { bronnenZin, deelvraagStand, voortgangZin } from "@/lib/bronselectie";
import { splits } from "@/lib/deelvragen";
import type { Werkgebied } from "@/lib/types";
import { useBronselectieStand } from "@/lib/useBronselectieStand";
import { DOSSIER_VELDEN } from "@/lib/werkgebied";
import { deelvraagPad, projectPad } from "@/lib/werkgebiedPaden";
import { metLeesbareBronnen } from "@/lib/bronKandidaten";

/** Wat het werkgebied is, in één oogopslag: het dossier in de volgorde van de methode (aanleiding,
 *  context, doel, analysevraag, praktijkvoorbeeld, afbakening), de actieve deelvragen met hun stand, en hoeveel
 *  bronnen er zijn (de lijst staat per deelvraag op de tab Bronnen, spoor K). In de lijststijl van de samenvatting op de vraagkaart.
 *
 *  Eén samenvatting op twee plekken (F3a): het paneel naast het gesprek en de kop van de werkgebiedpagina.
 *  Een leeg veld staat er ook, zodat zichtbaar is wat er nog ontbreekt; aanvullen vraag je in het gesprek (de
 *  suggestie *Vul het dossier aan*). Geen *Vraag Lex* in het paneel (spoor K): naast het gesprek zet een klik op
 *  een deelvraag haar als onderwerp, daarbuiten opent hij haar pagina. */
export function WerkgebiedSamenvatting({ wg, className = "" }: {
  wg: Werkgebied;
  className?: string;
}) {
  const kies = useContext(VraagLexContext);
  const deelvragen = splits(wg.deelvragen).actief;
  const selectie = useBronselectieStand(wg.id, wg.revisie, deelvragen.length);
  const analyse = wg.bronnen.filter((b) => b.rol === "analyseren");
  const regelingen = new Set(wg.bronnen.map((b) => b.bwb_id || b.bron_iri.split(":")[2])).size;
  const stand = new Map((selectie?.deelvragen ?? []).map((d) => [d.id, d]));
  return (
    <Regels data-werkgebied-samenvatting className={`text-sm ${className}`}>
      {DOSSIER_VELDEN.map(({ veld, label }) => (
        <Regel key={veld} naam={label} data-dossier-veld={veld}>
          {(wg[veld] ?? "").trim()
            ? <span className="whitespace-pre-line">{metLeesbareBronnen(wg[veld] ?? "")}</span>
            : (
              <span className="text-muted">{`Nog geen ${label.toLowerCase()}.`}</span>
            )}
        </Regel>
      ))}
      {/* Spoor I6: het TOOI-thema, als het gekozen is; kiezen gaat in *Gegevens bewerken*. */}
      {wg.thema && (
        <Regel naam="Thema" data-dossier-veld="thema">
          {bronHref(wg.thema) ? (
            <a href={bronHref(wg.thema)} target="_blank" rel="noopener noreferrer" className="text-lint underline-offset-2 hover:underline">
              {wg.thema_label || themaLabel(wg.thema) || wg.thema}
            </a>
          ) : (wg.thema_label || themaLabel(wg.thema) || wg.thema)}
        </Regel>
      )}
      <Regel naam={`Deelvragen (${deelvragen.length})`} data-samenvatting="deelvragen">
        {deelvragen.length ? (
          <>
            <Lijst genummerd label="Deelvragen" className="-my-1.5">
              {deelvragen.map((d, i) => {
                const s = deelvraagStand(stand.get(d.id));
                return (
                  <LijstRij key={d.id} className="py-1.5" voor={`${i + 1}.`} data-samenvatting-deelvraag={d.id}
                    titel={kies ? (
                      <button type="button" className={DEELVRAAG_LINK} data-deelvraag-onderwerp={d.id}
                        aria-label={`Bespreek deelvraag ${i + 1} in dit gesprek: ${d.vraag}`}
                        onClick={() => kies({ soort: "deelvraag", werkgebied_id: wg.id, id: d.id, label: d.vraag })}>
                        {d.vraag}
                      </button>
                    ) : <Link href={deelvraagPad(wg.id, d.id)} className={DEELVRAAG_LINK}>{d.vraag}</Link>}
                    status={s && <StatusLabel toon={s.toon} data-samenvatting-stand={stand.get(d.id)?.status}>{s.label}</StatusLabel>} />
                );
              })}
            </Lijst>
            {selectie?.modus === "deelvragen" && <p className="mt-1.5 text-xs text-muted">{voortgangZin(selectie)}</p>}
          </>
        ) : (
          <span className="text-muted">Nog geen deelvragen.</span>
        )}
      </Regel>
      {/* Eén regel, geen tweede lijst (spoor K): de bronnen staan per deelvraag op de tab Bronnen. */}
      <Regel naam="Bronnen" data-samenvatting="bronnen">
        {wg.bronnen.length ? (
          <Link href={projectPad(wg.id, "bronnen")} className="focus-ring rounded text-lint underline-offset-2 hover:underline">
            {bronnenZin(wg.bronnen.length)}{regelingen > 1 ? ` in ${regelingen} regelingen` : ""}
            {analyse.length < wg.bronnen.length ? ` (${wg.bronnen.length - analyse.length} context)` : ""}
          </Link>
        ) : (
          <span className="text-muted">Nog geen bronnen.</span>
        )}
      </Regel>
    </Regels>
  );
}

const DEELVRAAG_LINK = "focus-ring rounded text-left text-ink underline-offset-2 hover:text-lint hover:underline";
