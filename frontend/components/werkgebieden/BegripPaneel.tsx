"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Field } from "@/components/ui/Field";
import { Lijst, LijstRij, Regel, Regels, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { VerwijderKnop } from "@/components/ui/VerwijderKnop";
import { KaartVoorstelKaart } from "@/components/werkgebieden/KaartVoorstel";
import { VoorbeeldRijen } from "@/components/werkgebieden/Voorbeelden";
import {
  foutTekst, haalBegrip, haalKaartVoorstellen, haalRelaties, neemKaartVoorstelOver, verwijderBegrip, wijsKaartVoorstelAf,
  wijzigBegrip,
} from "@/lib/api";
import { metSpoor } from "@/lib/uiSpoor";
import { verwijderdUit, verwijderdZin, type Verwijderd } from "@/lib/verwijderen";
import { VELD_LABEL, definitieDoor, openPerVeld, verouderdUit, type Verouderd } from "@/lib/kaartVoorstel";
import { relatieZin } from "@/lib/begripRelaties";
import { definitieAard, handmatigeInhoud } from "@/lib/begrippen";
import { BEGRIP_STATUS_LABEL } from "@/lib/begrippenOverzicht";
import type { Begrip, KaartVeld, KaartVoorstel, KaartVoorstellenAntwoord, RelatiesAntwoord } from "@/lib/types";
import { isRevisieConflict } from "@/lib/werkgebied";

const VELDEN: KaartVeld[] = ["definitie", "uitleg", "context", "voorbeelden"];
const STATUS_TOON = { geaccordeerd: "groen", concept: "neutraal", vervangen: "neutraal" } as const;

/** Eén begrip naast het gesprek (F3d): wat Lex voor dit begrip opleverde, om te beoordelen.
 *
 * *  - een rustige leesweergave: naam, status, termen, definitie met haar label, uitleg, toelichting, voorbeelden, en de
 *    relaties ingeklapt;
 *  - de open voorstellen van Lex per veld, met *Overnemen · Aanpassen · Afwijzen* (`KaartVoorstelKaart`,
 *    dezelfde als op de begripskaart);
 *  - een kleine bewerking van definitie en uitleg; de rest staat op de begripskaart.
 *
 *  Geen Lex-knoppen: wat Lex moet doen vraag je in het gesprek. Overnemen en bewerken dragen de revisie;
 *  een 412 laadt de nieuwe stand en zegt dat. */
export function BegripPaneel({ werkgebiedId, begripId, onOnbewaard, onNaarBegrip, onVerwijderd }: {
  werkgebiedId: string;
  begripId: string;
  /** De bewerking heeft niet-bewaarde wijzigingen: het paneel vraagt dan bevestiging bij sluiten. */
  onOnbewaard: (onbewaard: boolean) => void;
  /** Naar het begrip dat dit vervangt (een vervangen begrip). */
  onNaarBegrip?: (begripId: string) => void;
  /** Het begrip is verwijderd (de Begrippen-tab laadt dan de lijst opnieuw); zonder blijft het paneel
   *  staan met de verwijderd-stand. */
  onVerwijderd?: () => void;
}) {
  const [begrip, setBegrip] = useState<Begrip | null>(null);
  const [lex, setLex] = useState<KaartVoorstellenAntwoord | null>(null);
  const [relaties, setRelaties] = useState<RelatiesAntwoord | null>(null);
  const [verouderd, setVerouderd] = useState<Verouderd | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ type: "bevestiging" | "waarschuwing"; tekst: string } | null>(null);
  const [bewerk, setBewerk] = useState<{ definitie: string; uitleg: string } | null>(null);
  const [bezig, setBezig] = useState(false);
  const [verwijderd, setVerwijderd] = useState<Verwijderd | null>(null);

  const laad = useCallback(async () => {
    try {
      setBegrip(await haalBegrip(werkgebiedId, begripId));
      setFout(null);
    } catch (e) {
      // Een verwijderd begrip is een toestand, geen fout – zoals een verwijderde annotatie.
      const v = verwijderdUit(e);
      if (v) {
        setVerwijderd(v);
        setBegrip(null);
      } else setFout(foutTekst(e, "Het begrip kon niet worden geladen."));
    }
  }, [werkgebiedId, begripId]);

  /** Echt wissen, zoals een annotatie (`lib/verwijderen.ts`). Een vervangen begrip gaat niet weg (409: verwijder
   *  de opvolger); een 412 laadt de nieuwe stand. */
  async function verwijder() {
    if (!begrip) return;
    setMelding(null);
    try {
      await metSpoor("begrip_verwijderen", () => verwijderBegrip(werkgebiedId, begripId, begrip.revisie));
      onOnbewaard(false);
      await laad();                          // de api zegt nu wanneer en door wie
      onVerwijderd?.();
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde dit begrip net. Bekijk de nieuwe stand voordat je het verwijdert." });
      } else setMelding({ type: "waarschuwing", tekst: foutTekst(e, "Het begrip is niet verwijderd.") });
    }
  }

  // De voorstellen en relaties per revisie: een eigen wijziging kan een open voorstel verouderd maken.
  // Beide falen stil – de leesweergave staat er dan gewoon.
  const revisie = begrip?.revisie;
  useEffect(() => {
    let levend = true;
    haalKaartVoorstellen(werkgebiedId, begripId).then((l) => levend && setLex(l)).catch(() => {});
    haalRelaties(werkgebiedId, begripId).then((r) => levend && setRelaties(r)).catch(() => {});
    return () => { levend = false; };
  }, [werkgebiedId, begripId, revisie]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  const onbewaard = !!bewerk && !!begrip
    && (bewerk.definitie.trim() !== begrip.inhoud.definitie.trim() || bewerk.uitleg.trim() !== begrip.inhoud.uitleg.trim());
  useEffect(() => { onOnbewaard(onbewaard); }, [onbewaard, onOnbewaard]);
  useEffect(() => () => onOnbewaard(false), [onOnbewaard]);

  async function muteer(actie: (revisie: number) => Promise<Begrip>, gelukt: string, opFout?: (e: unknown) => boolean) {
    if (!begrip) return false;
    setMelding(null);
    try {
      setBegrip(await actie(begrip.revisie));
      setMelding({ type: "bevestiging", tekst: gelukt });
      return true;
    } catch (e) {
      if (isRevisieConflict(e)) {
        await laad();
        setMelding({ type: "waarschuwing", tekst: "Iemand anders wijzigde dit begrip net. De nieuwste stand staat nu in beeld." });
      } else if (!opFout?.(e)) {
        setMelding({ type: "waarschuwing", tekst: foutTekst(e) });
      }
      return false;
    }
  }

  async function overnemen(v: KaartVoorstel, extra: Parameters<typeof neemKaartVoorstelOver>[4]) {
    const ok = await muteer((r) => neemKaartVoorstelOver(werkgebiedId, begripId, v.id, r, extra),
      "Overgenomen van Lex; dat is een nieuwe revisie.", (e) => {
        const oud = verouderdUit(e, v.id);
        if (oud) setVerouderd(oud);
        return !!oud;
      });
    if (ok) setVerouderd(null);
    return ok;
  }

  async function afwijzen(v: KaartVoorstel, reden: string) {
    try {
      setLex(await wijsKaartVoorstelAf(werkgebiedId, begripId, v.id, reden));
      return true;
    } catch (e) {
      setMelding({ type: "waarschuwing", tekst: foutTekst(e, "Afwijzen is niet gelukt.") });
      return false;
    }
  }

  async function bewaar(e: React.FormEvent) {
    e.preventDefault();
    if (!begrip || !bewerk || !onbewaard || bezig) return;
    setBezig(true);
    const inhoud = handmatigeInhoud(begrip.inhoud, bewerk);
    if (await muteer((r) => wijzigBegrip(werkgebiedId, begripId, r, inhoud), "Opgeslagen.")) setBewerk(null);
    setBezig(false);
  }

  if (verwijderd) {
    return <Melding type="uitleg"><span data-verwijderd>{verwijderdZin(verwijderd)}</span></Melding>;
  }
  if (!begrip) {
    return fout ? (
      <Melding type="fout" titel="Het begrip kon niet worden geladen.">
        {fout}{" "}
        <button type="button" className="focus-ring rounded font-medium text-lint underline" onClick={() => void laad()}>
          Opnieuw proberen
        </button>
      </Melding>
    ) : <SkeletonCard regels={4} />;
  }

  const b = begrip.inhoud;
  const open = openPerVeld(lex?.voorstellen ?? []);
  const aantalOpen = VELDEN.reduce((n, v) => n + (open[v]?.length ?? 0), 0);
  const vervangen = begrip.status === "vervangen";
  const vast = (relaties?.relaties ?? []).filter((r) => r.beoordeling === "akkoord");
  const voorgesteld = relaties?.voorstellen ?? [];

  return (
    <div data-begrip-paneel={begrip.id} data-status={begrip.status} className="space-y-5 text-sm text-ink">
      <div className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-display text-base font-semibold text-lint">{b.naam || "Naamloos begrip"}</p>
          <StatusLabel toon={STATUS_TOON[begrip.status]}>{BEGRIP_STATUS_LABEL[begrip.status]}</StatusLabel>
          {!vervangen && <VerwijderKnop soort="begrip" onBevestig={verwijder} className="ml-auto" />}
        </div>
        {b.alternatieve_termen.length > 0 && <p className="text-xs text-muted">Ook: {b.alternatieve_termen.join(", ")}</p>}
        {vervangen && begrip.vervangen_door && (
          <p className="text-xs text-muted">
            Vervangen door{" "}
            {onNaarBegrip ? (
              <button type="button" className="focus-ring rounded font-medium text-lint underline"
                onClick={() => onNaarBegrip(begrip.vervangen_door!.begrip_id)}>{begrip.vervangen_door.naam}</button>
            ) : begrip.vervangen_door.naam}
          </p>
        )}
      </div>

      {melding && <Melding type={melding.type} compact>{melding.tekst}</Melding>}

      {aantalOpen > 0 && !vervangen && (
        <Sectie titel="Voorstellen van Lex" telling={aantalOpen} niveau={3}
          toelichting={onbewaard ? "Bewaar of annuleer eerst je eigen wijziging; dan kun je overnemen." : undefined}>
          <div className="space-y-3" data-voorstellen>
            {VELDEN.flatMap((veld) => (open[veld] ?? []).map((v) => (
              <div key={v.id} className="space-y-1">
                <p className="text-xs font-medium text-muted">{VELD_LABEL[veld]}</p>
                <KaartVoorstelKaart v={v} verouderd={verouderd?.voorstelId === v.id ? verouderd : null} onbewaard={onbewaard}
                  geaccordeerd={begrip.status === "geaccordeerd"}
                  onOvernemen={(extra) => overnemen(v, extra)} onAfwijzen={(reden) => afwijzen(v, reden)} />
              </div>
            )))}
          </div>
        </Sectie>
      )}

      {bewerk ? (
        <form onSubmit={bewaar} className="space-y-3" aria-label="Definitie en uitleg bewerken">
          <Field label="Definitie" hint="een gewijzigde definitie heet geformuleerd">
            <AutoTextarea value={bewerk.definitie} rows={3} maxLength={8000} autoFocus
              onChange={(e) => setBewerk({ ...bewerk, definitie: e.target.value })} />
          </Field>
          <Field label="Uitleg">
            <AutoTextarea value={bewerk.uitleg} rows={2} maxLength={8000}
              onChange={(e) => setBewerk({ ...bewerk, uitleg: e.target.value })} />
          </Field>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button type="submit" size="sm" className="w-full sm:w-auto" disabled={!onbewaard || bezig}>
              {bezig ? "Bezig…" : "Opslaan"}
            </Button>
            <Button type="button" size="sm" variant="ghost" className="w-full sm:w-auto" onClick={() => setBewerk(null)}>
              Annuleren
            </Button>
          </div>
        </form>
      ) : (
        <Regels data-begrip-lees>
          <Regel naam="Definitie">
            {b.definitie ? (
              <>
                <span className="whitespace-pre-line">{b.definitie}</span>
                {/* Brondefinitie of analysebegrip (spoor G5): een geformuleerde definitie is geen wettelijke. */}
                <span className="mt-1 block text-xs font-medium text-ink" data-definitie-aard={definitieAard(b).soort}>
                  {definitieAard(b).titel}
                </span>
                {definitieDoor(b) && <span className="mt-0.5 block text-xs text-muted">{definitieDoor(b)}</span>}
              </>
            ) : <span className="text-muted">Nog geen definitie.</span>}
          </Regel>
          <Regel naam="Uitleg">
            {b.uitleg ? <span className="whitespace-pre-line">{b.uitleg}</span> : (
              // Spoor I2: Lex schrijft de uitleg in B1; dat vraag je in het gesprek (geen knop in het paneel, spoor K).
              <span className="text-muted">Nog geen uitleg.</span>
            )}
          </Regel>
          {b.context && (
            <Regel naam="Toelichting"><span className="whitespace-pre-line">{b.context}</span></Regel>
          )}
          <Regel naam={`Voorbeelden (${b.voorbeelden.length})`}>
            {b.voorbeelden.length ? <VoorbeeldRijen voorbeelden={b.voorbeelden} />
              : <span className="text-muted">Nog geen voorbeelden.</span>}
          </Regel>
        </Regels>
      )}
      {!bewerk && !vervangen && (
        <Button size="sm" variant="secondary" className="w-full sm:w-auto"
          onClick={() => setBewerk({ definitie: b.definitie, uitleg: b.uitleg })}>
          Definitie en uitleg bewerken
        </Button>
      )}

      {(vast.length > 0 || voorgesteld.length > 0) && (
        <details data-begrip-relaties>
          <summary className="focus-ring cursor-pointer rounded text-sm font-medium text-ink">
            Relaties ({vast.length} vastgelegd{voorgesteld.length ? `, ${voorgesteld.length} voorgesteld` : ""})
          </summary>
          <Lijst label="Relaties" className="mt-2">
            {[...vast, ...voorgesteld].map((r) => (
              <LijstRij key={r.id} titel={relatieZin(r.type, r.van_naam, r.naar_naam).join(" ")}
                meta={r.beoordeling === "voorgesteld" ? "Voorstel van Lex – leg het vast op de begripskaart" : undefined} />
            ))}
          </Lijst>
        </details>
      )}
    </div>
  );
}
