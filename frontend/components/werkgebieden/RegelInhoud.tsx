"use client";

import Link from "next/link";
import { useState } from "react";

import { AutoTextarea } from "@/components/ui/AutoTextarea";
import { Button } from "@/components/ui/Button";
import { ButtonRow } from "@/components/ui/ButtonRow";
import { LaadRegel, LaadStand } from "@/components/ui/LaadStand";
import { Leeg } from "@/components/ui/Leeg";
import { Lijst, LijstRij, Regel as RegelVeld, Regels, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import { Kaart, SplitDetail } from "@/components/ui/Pagina";
import { Uitklap } from "@/components/ui/Uitklap";
import { OpenPunten } from "@/components/werkgebieden/OpenPunten";
import { Markdown } from "@/components/werkplek/Markdown";
import {
  accordeerRegel, beoordeelRegelDrager, beoordeelVoorbeeld, haalRegelRevisies, heropenRegel, verversRegelDrager, wijsRegelAf,
} from "@/lib/api";
import { datumTijd } from "@/lib/datum";
import {
  DRAGER_BEOORDELING_LABEL, DRAGER_ROL_LABEL, HERKOMST_LABEL, REGEL_SOORT_LABEL, REGEL_STATUS_LABEL, REGEL_STATUS_TOON,
  VOORBEELD_OORDEEL_LABEL, begripNaam, bronLink, buren, dragerTekst, gevalLabels, isGeaccordeerd, isOpen, voorbeeldNr, voorbeeldTabel, voorbeeldenBij,
  type Regel, type RegelDrager, type RegelKeten, type RegelRevisie, type VoorbeeldOordeel,
} from "@/lib/regels";
import type { RegelStand } from "@/lib/useRegel";
import { begripPad, elementPad, regelPad } from "@/lib/werkgebiedPaden";

const OORDEEL_TOON: Record<VoorbeeldOordeel, "groen" | "rood" | "geel" | "neutraal"> = {
  juist: "groen", onjuist: "rood", kan_niet: "neutraal", open: "geel",
};

/** De stand van een regel in een kop: status, soort, beleid en revisie. */
export function RegelStatus({ regel }: { regel: Regel }) {
  return <>
    <StatusLabel toon={REGEL_STATUS_TOON[regel.status]}>{REGEL_STATUS_LABEL[regel.status]}</StatusLabel>
    <span className="text-xs text-muted">{REGEL_SOORT_LABEL[regel.inhoud.soort]}{regel.inhoud.brontype === "beleid" ? " · beleidsregel" : ""}{regel.inhoud.eigenaar ? ` · eigenaar ${regel.inhoud.eigenaar}` : ""} · revisie {regel.revisie}</span>
  </>;
}

/** Eén afleidingsregel: de regelkaart (ADR-018 §6), gebouwd zoals de begripskaart. Breed genoeg in twee kolommen (links
 *  de regel, de gevallen en de grondslag, rechts de beoordeling, de keten en de historie), smal onder elkaar (`SplitDetail`):
 *  op de pagina, vergroot en naast het gesprek dezelfde indeling.
 *  De regeltekst komt van de api. Geen Lex-knoppen: dat vraag je in het gesprek. */
export function RegelInhoud({ stand, keten }: {
  stand: RegelStand;
  /** De keten van het werkgebied, voor *Volgt op* en *Leidt tot*; ontbreekt hij, dan staat dat blok er niet. */
  keten?: RegelKeten | null;
}) {
  const { regel } = stand;
  if (!regel) return <LaadStand wat="De afleidingsregel" fout={stand.fout} onOpnieuw={stand.laad} />;

  const melding = stand.melding && <Melding type={stand.melding.type} className="mb-4" data-regel-melding>{stand.melding.tekst}</Melding>;
  const hoofd = <>
    <RegelTekst regel={regel} />
    <Gevallen stand={stand} regel={regel} />
    <OpenPunten werkgebiedId={regel.werkgebied_id} regelId={regel.id} revisie={regel.revisie}
      alleenLezen={stand.alleenLezen} onBesluit={stand.laad} gevallen={gevalLabels(regel)}
      regels={keten?.regels ?? []} opvolger={regel.vervangen_door} />
    <Dragers stand={stand} regel={regel} />
    {regel.inhoud.toelichting.trim() && (
      <Kaart titel="Toelichting"><p className="whitespace-pre-line text-sm text-ink">{regel.inhoud.toelichting}</p></Kaart>
    )}
  </>;
  const zij = <>
    <Beoordeling stand={stand} regel={regel} keten={keten} />
    {keten && <InDeKeten regel={regel} keten={keten} />}
    {!stand.alleenLezen && <Historie regel={regel} />}
  </>;
  return (
    <div data-regel-inhoud={regel.id} data-regel-status={regel.status}>
      {melding}
      {/* Op elke plek dezelfde indeling; de breedte van het blok beslist over twee kolommen (`SplitDetail`). */}
      <SplitDetail hoofd={hoofd} zij={zij} />
    </div>
  );
}

function BegripLink({ regel, id }: { regel: Regel; id: string }) {
  return (
    <Link href={begripPad(regel.werkgebied_id, id)} className="focus-ring rounded text-lint hover:underline" data-regel-begrip={id}>
      {begripNaam(regel, id)}
    </Link>
  );
}

/** De regel in het taalpatroon, met de begrippen die hij noemt. */
function RegelTekst({ regel }: { regel: Regel }) {
  const { inhoud } = regel;
  const invoer = inhoud.invoer.filter((i) => i.rol !== "parameter");
  const parameters = inhoud.invoer.filter((i) => i.rol === "parameter");
  return (
    <Kaart titel="Regel" toelichting="Afgeleid uit de delen hieronder, in het taalpatroon van de methode." data-regel-tekst>
      <div className="text-lees text-ink [&_ul]:mt-1"><Markdown tekst={regel.regeltekst.markdown} links="vrij" /></div>
      <Regels className="mt-3 border-t border-line">
        <RegelVeld naam="Uitvoer"><BegripLink regel={regel} id={inhoud.uitvoer_begrip_id} /></RegelVeld>
        {inhoud.onderwerp_begrip_id && <RegelVeld naam="Over"><BegripLink regel={regel} id={inhoud.onderwerp_begrip_id} /></RegelVeld>}
        <RegelVeld naam="Invoer">
          {invoer.length
            ? <span className="flex flex-wrap gap-x-3 gap-y-1">{invoer.map((i) => <BegripLink key={i.begrip_id} regel={regel} id={i.begrip_id} />)}</span>
            : <span className="text-muted">Geen</span>}
        </RegelVeld>
        {parameters.length > 0 && (
          <RegelVeld naam="Parameters">
            <span className="flex flex-wrap gap-x-3 gap-y-1">{parameters.map((i) => <BegripLink key={i.begrip_id} regel={regel} id={i.begrip_id} />)}</span>
          </RegelVeld>
        )}
        <RegelVeld naam="Regelbegrip"><BegripLink regel={regel} id={inhoud.regelbegrip_id} /></RegelVeld>
      </Regels>
    </Kaart>
  );
}

const OORDELEN: VoorbeeldOordeel[] = ["juist", "onjuist", "kan_niet"];
const OORDEEL_KNOP: Record<VoorbeeldOordeel, string> = { open: "Terug naar open", juist: "Juist", onjuist: "Niet juist", kan_niet: "Kan niet" };

/** De voorbeelden als tabel (V3): een kolom per voorbeeld, de invoer per begrip, de uitkomst en het oordeel. In een
 *  eigen vak dat zijwaarts scrollt; de lijst eronder houdt de knoppen om te beoordelen. */
function VoorbeeldTabel({ regel, voorbeelden }: { regel: Regel; voorbeelden: Regel["inhoud"]["voorbeelden"] }) {
  const t = voorbeeldTabel(regel, voorbeelden);
  if (!t) return null;
  return (
    <div className="mt-2 overflow-x-auto rounded-md border border-line" data-voorbeeld-tabel>
      <table className="min-w-full text-xs">
        <thead className="bg-surface text-muted">
          <tr><th scope="col" className="px-2 py-1 text-left font-medium">Voorbeeld</th>
            {t.kolommen.map((nr) => <th key={nr} scope="col" className="px-2 py-1 text-left font-medium">{nr}</th>)}</tr>
        </thead>
        <tbody>
          {t.rijen.map((r) => (
            <tr key={r.begrip} className="border-t border-line">
              <th scope="row" className="px-2 py-1 text-left font-normal text-muted">{r.begrip}</th>
              {r.waarden.map((w, j) => <td key={j} className="px-2 py-1 text-ink">{w || "–"}</td>)}
            </tr>
          ))}
          <tr className="border-t border-line">
            <th scope="row" className="px-2 py-1 text-left font-normal text-muted">Uitkomst</th>
            {voorbeelden.map((v, j) => <td key={j} className="px-2 py-1 text-ink">{v.uitkomst}</td>)}
          </tr>
          <tr className="border-t border-line">
            <th scope="row" className="px-2 py-1 text-left font-normal text-muted">Oordeel</th>
            {voorbeelden.map((v, j) => (
              <td key={j} className="px-2 py-1"><StatusLabel klein toon={OORDEEL_TOON[v.oordeel]}>{VOORBEELD_OORDEEL_LABEL[v.oordeel]}</StatusLabel></td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/** De gevallen met hun voorbeelden: één rij per geval, de voorbeelden met het oordeel "juridisch juist?". Een voorbeeld
 *  dat nog open is, beoordeel je hier: dat is een besluit op het artefact, apart van het maken (de api zet geen oordeel
 *  bij een wijziging van de regel). */
function Gevallen({ stand, regel }: { stand: RegelStand; regel: Regel }) {
  const enkel = regel.inhoud.gevallen.length === 1;
  const kan = !stand.alleenLezen && isOpen(regel);
  const beoordeel = (nr: number, oordeel: VoorbeeldOordeel) =>
    stand.muteer((r) => beoordeelVoorbeeld(regel.werkgebied_id, regel.id, nr, r, oordeel));
  return (
    <Kaart titel={enkel ? "Voorbeelden" : "Gevallen"} telling={enkel ? regel.inhoud.voorbeelden.length : regel.inhoud.gevallen.length}
      toelichting={enkel ? "Is de uitkomst juridisch juist?" : "Per geval de voorwaarden, de uitkomst en de voorbeelden."}>
      <Lijst label={enkel ? "Voorbeelden" : "Gevallen"}>
        {regel.inhoud.gevallen.map((g, i) => {
          const voorbeelden = voorbeeldenBij(regel, g.label);
          const tekst = regel.regeltekst.gevallen[i]?.tekst;
          return (
            <LijstRij key={g.label || i} data-regel-geval={g.label}
              titel={enkel ? undefined : <span className="font-medium">Geval {g.label}{g.voorrang ? " (gaat voor)" : ""}</span>}
              meta={!enkel && tekst && <span className="whitespace-pre-line">{tekst}</span>}>
              {voorbeelden.length > 0 && <VoorbeeldTabel regel={regel} voorbeelden={voorbeelden} />}
              {voorbeelden.length ? (
                <ul className="mt-2 space-y-1.5">
                  {voorbeelden.map((v, j) => {
                    const nr = voorbeeldNr(regel, v);
                    return (
                      <li key={j} className="text-sm" data-regel-voorbeeld={v.oordeel} data-voorbeeld-nr={nr}>
                        <div className="flex items-start justify-between gap-3">
                          <span className="min-w-0 text-ink">{v.invoer} <span className="text-muted">→</span> {v.uitkomst}</span>
                          <StatusLabel klein toon={OORDEEL_TOON[v.oordeel]}>{VOORBEELD_OORDEEL_LABEL[v.oordeel]}</StatusLabel>
                        </div>
                        {(v.door || v.beoordeeld_door) && (
                          <p className="text-xs text-muted">
                            {v.door && <>Gemaakt door {v.door}</>}{v.door && v.beoordeeld_door && " · "}
                            {v.beoordeeld_door && <>beoordeeld door {v.beoordeeld_door}</>}
                          </p>
                        )}
                        {kan && (
                          <ButtonRow className="mt-1">
                            {(v.oordeel === "open" ? OORDELEN : (["open"] as VoorbeeldOordeel[])).map((o) => (
                              <Button key={o} size="xs" variant={o === "juist" ? "secondary" : "ghost"} disabled={stand.bezig}
                                onClick={() => void beoordeel(nr, o)} data-voorbeeld-oordeel={o}
                                aria-label={`Voorbeeld ${nr}: ${OORDEEL_KNOP[o].toLowerCase()}`}>{OORDEEL_KNOP[o]}</Button>
                            ))}
                          </ButtonRow>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : <Leeg klein className="mt-2">Nog geen voorbeeld bij dit geval.</Leeg>}
            </LijstRij>
          );
        })}
      </Lijst>
    </Kaart>
  );
}

/** De markeringen waarop de regel rust: eerst de grondslag, dan de rest. Per drager akkoord of afwijzen. */
function Dragers({ stand, regel }: { stand: RegelStand; regel: Regel }) {
  const volgorde = [...regel.dragers].sort((a, b) => Number(b.rol === "grondslag") - Number(a.rol === "grondslag"));
  const beoordeel = (d: RegelDrager, beoordeling: "akkoord" | "afgewezen") =>
    stand.muteer((r) => beoordeelRegelDrager(regel.werkgebied_id, regel.id, d.id, r, beoordeling));
  const kan = !stand.alleenLezen && isOpen(regel);
  return (
    <Kaart titel="Grondslag en dragende passages" telling={regel.dragers.length}
      toelichting="De markeringen waarop de regel rust. Zonder grondslag in de tekst bestaat een regel niet.">
      <Lijst label="Dragende passages">
        {volgorde.map((d) => (
          <LijstRij key={d.id} data-regel-drager={d.rol}
            titel={<Link href={elementPad(d.element_id)} className="focus-ring rounded text-lint hover:underline">{DRAGER_ROL_LABEL[d.rol]}{d.geval ? ` · geval ${d.geval}` : ""}</Link>}
            meta={<DragerBron d={d} />}
            status={<StatusLabel toon={d.beoordeling === "akkoord" ? "groen" : d.beoordeling === "afgewezen" ? "rood" : "geel"}>
              {DRAGER_BEOORDELING_LABEL[d.beoordeling]}</StatusLabel>}
            acties={kan && d.beoordeling !== "afgewezen" && d.actualiteit && d.actualiteit !== "actueel" ? (
              // De markering veranderde: de drager draagt het bewijs van toen. Verversen zet hem op de stand van nu, en
              // dan beoordeel je hem opnieuw (de poort houdt een gewijzigde drager tegen).
              <Button size="xs" variant="secondary" disabled={stand.bezig}
                onClick={() => void stand.muteer((r) => verversRegelDrager(regel.werkgebied_id, regel.id, d.id, r))}
                aria-label={`${DRAGER_ROL_LABEL[d.rol]} ${d.element_id} verversen op de stand van nu`}>Verversen</Button>
            ) : kan && d.beoordeling === "open" && <>
              <Button size="xs" variant="secondary" disabled={stand.bezig} onClick={() => void beoordeel(d, "akkoord")}
                aria-label={`Akkoord met ${DRAGER_ROL_LABEL[d.rol].toLowerCase()} ${d.element_id}`}>Akkoord</Button>
              <Button size="xs" variant="ghost" disabled={stand.bezig} onClick={() => void beoordeel(d, "afgewezen")}
                aria-label={`${DRAGER_ROL_LABEL[d.rol]} ${d.element_id} afwijzen`}>Afwijzen</Button>
            </>} />
        ))}
      </Lijst>
    </Kaart>
  );
}

/** Waarop een drager rust: de letterlijke passage, de vindplaats en de weg naar de wettekst (de jci, anders het anker).
 *  Zonder jci zegt de rij dat, in plaats van een link te verzinnen. */
function DragerBron({ d }: { d: RegelDrager }) {
  const { tekst, vindplaats } = dragerTekst(d);
  const link = bronLink(d.bron);
  return (
    <span className="block space-y-0.5" data-drager-bron={d.bron?.soort ?? "onbekend"}>
      {tekst && <q className="block text-ink">{tekst}</q>}
      <span className="block">
        {link
          ? <a href={link} target="_blank" rel="noreferrer" className="focus-ring rounded text-lint hover:underline">{vindplaats || "Wettekst"}</a>
          : vindplaats || d.element_id}
        {d.bron?.soort === "anker" ? " · geen jci, link naar de vindplaats" : d.bron?.soort === "geen" ? " · geen bronreferentie" : ""}
        {d.actualiteit && d.actualiteit !== "actueel" ? ` · passage ${d.actualiteit}` : ""}
      </span>
    </span>
  );
}

/** De beoordeling: wat er openstaat (de poort van de api, letterlijk), de signalen, en accorderen, heropenen of afwijzen.
 *  Afwijzen kan met een opvolger: dan is de regel vervangen, en hang je zijn open punten om naar de opvolger. */
function Beoordeling({ stand, regel, keten }: { stand: RegelStand; regel: Regel; keten?: RegelKeten | null }) {
  const [reden, setReden] = useState("");
  const [afwijzen, setAfwijzen] = useState(false);
  const [opvolger, setOpvolger] = useState("");
  const kan = !stand.alleenLezen;
  const kandidaten = (keten?.regels ?? []).filter((r) => r.id !== regel.id);
  const accordeer = async () => {
    if (await stand.muteer((r) => accordeerRegel(regel.werkgebied_id, regel.id, r, reden.trim()), "De regel is geaccordeerd.")) setReden("");
  };
  const wijsAf = async () => {
    if (await stand.muteer((r) => wijsRegelAf(regel.werkgebied_id, regel.id, r, reden.trim(), opvolger),
      opvolger ? "De regel is vervangen. Hang zijn open punten om naar de opvolger." : "De regel is afgewezen.")) {
      setReden("");
      setAfwijzen(false);
      setOpvolger("");
    }
  };
  const naam = (id: string) => keten?.regels.find((r) => r.id === id)?.naam || id;
  return (
    <Kaart titel="Beoordeling" data-regel-beoordeling>
      <Regels>
        <RegelVeld naam="Status"><StatusLabel toon={REGEL_STATUS_TOON[regel.status]}>{REGEL_STATUS_LABEL[regel.status]}</StatusLabel></RegelVeld>
        <RegelVeld naam="Herkomst">{HERKOMST_LABEL[regel.herkomst] ?? regel.herkomst}</RegelVeld>
        {regel.vervangen_door && (
          <RegelVeld naam="Vervangen door">
            <Link href={regelPad(regel.werkgebied_id, regel.vervangen_door)} className="focus-ring rounded text-lint hover:underline"
              data-regel-vervangen-door>{naam(regel.vervangen_door)}</Link>
          </RegelVeld>
        )}
        {regel.opvolger_van && (
          <RegelVeld naam="Vervangt">
            <Link href={regelPad(regel.werkgebied_id, regel.opvolger_van)} className="focus-ring rounded text-lint hover:underline">
              {naam(regel.opvolger_van)}</Link>
          </RegelVeld>
        )}
        {isGeaccordeerd(regel) && regel.geaccordeerd_door && (
          <RegelVeld naam="Geaccordeerd">{regel.geaccordeerd_door}, {datumTijd(regel.geaccordeerd_op)}</RegelVeld>
        )}
      </Regels>
      {isOpen(regel) && (regel.accorderen.mag
        ? <Melding type="bevestiging" compact className="mt-3">Alles is beoordeeld: de regel kan worden geaccordeerd.</Melding>
        : (
          <Sectie titel="Nog open voor accorderen" niveau={3} className="mt-3" data-regel-poort>
            <ul className="list-disc space-y-1 pl-5 text-sm text-ink">{regel.accorderen.redenen.map((r) => <li key={r}>{r}</li>)}</ul>
          </Sectie>
        ))}
      {regel.signalen.length > 0 && (
        <Sectie titel="Signalen" niveau={3} className="mt-3" toelichting="Vragen aandacht, maar blokkeren het accorderen niet." data-regel-signalen>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">{regel.signalen.map((s) => <li key={s}>{s}</li>)}</ul>
        </Sectie>
      )}
      {kan && (isOpen(regel) || (regel.status === "afgewezen" && !regel.vervangen_door)) && (
        <div className="mt-4 space-y-2">
          <label className="block text-sm text-muted" htmlFor={`reden-${regel.id}`}>
            {!isOpen(regel) ? "Vervangt een andere regel deze afgewezen regel? Zeg waarom." : afwijzen ? "Waarom wijs je de regel af?" : "Waarom accordeer je de regel?"}
          </label>
          <AutoTextarea id={`reden-${regel.id}`} value={reden} onChange={(e) => setReden(e.target.value)} rows={2}
            className="w-full" data-regel-reden />
          {(afwijzen || !isOpen(regel)) && kandidaten.length > 0 && (
            <Select aria-label="Vervangen door" value={opvolger} onChange={(e) => setOpvolger(e.target.value)} className="w-full"
              data-regel-opvolger>
              <option value="">Niet vervangen door een andere regel</option>
              {kandidaten.map((r) => <option key={r.id} value={r.id}>Vervangen door: {r.naam || r.id}</option>)}
            </Select>
          )}
          <ButtonRow>
            {afwijzen || !isOpen(regel) ? <>
              <Button size="sm" variant="danger" disabled={stand.bezig || !reden.trim() || (!isOpen(regel) && !opvolger)}
                onClick={() => void wijsAf()}>{opvolger ? "Vervangen" : "Afwijzen"}</Button>
              {isOpen(regel) && <Button size="sm" variant="ghost" onClick={() => setAfwijzen(false)}>Annuleren</Button>}
            </> : <>
              <Button size="sm" disabled={stand.bezig || !regel.accorderen.mag || !reden.trim()} onClick={() => void accordeer()}
                data-regel-accorderen>Accorderen</Button>
              <Button size="sm" variant="secondary" onClick={() => setAfwijzen(true)}>Afwijzen…</Button>
            </>}
          </ButtonRow>
        </div>
      )}
      {kan && isGeaccordeerd(regel) && (
        <ButtonRow className="mt-4">
          <Button size="sm" variant="secondary" disabled={stand.bezig}
            onClick={() => void stand.muteer((r) => heropenRegel(regel.werkgebied_id, regel.id, r), "De regel staat weer open.")}>
            Heropenen
          </Button>
        </ButtonRow>
      )}
    </Kaart>
  );
}

/** Waar de regel in de keten staat: de regels waarvan hij een uitkomst gebruikt, en de regels die de zijne gebruiken. */
function InDeKeten({ regel, keten }: { regel: Regel; keten: RegelKeten }) {
  const { volgtOp, leidtTot } = buren(keten, regel.id);
  const naam = (id: string) => keten.regels.find((r) => r.id === id)?.naam || id;
  const rij = (ids: string[]) => ids.length
    ? <ul className="space-y-1">{ids.map((id) => (
      <li key={id}><Link href={regelPad(regel.werkgebied_id, id)} className="focus-ring rounded text-sm text-lint hover:underline">{naam(id)}</Link></li>
    ))}</ul>
    : <span className="text-sm text-muted">Geen</span>;
  const signalen = keten.signalen.filter((s) => s.regel_ids.includes(regel.id));
  return (
    <Kaart titel="In de keten" data-regel-keten>
      <Regels>
        <RegelVeld naam="Volgt op">{rij(volgtOp)}</RegelVeld>
        <RegelVeld naam="Leidt tot">{rij(leidtTot)}</RegelVeld>
      </Regels>
      {signalen.map((s) => <Melding key={s.soort} type="waarschuwing" compact className="mt-3">{s.melding}</Melding>)}
    </Kaart>
  );
}

const ACTIE_ZIN: Record<string, string> = {
  "regel-aangemaakt": "Aangemaakt", "regel-gewijzigd": "Gewijzigd", "drager-beoordeeld": "Passage beoordeeld",
  "drager-toegevoegd": "Passages toegevoegd", "drager-verwijderd": "Passage verwijderd",
  "regel-geaccordeerd": "Geaccordeerd", "regel-heropend": "Heropend", "regel-afgewezen": "Afgewezen",
  "regel-vervangen": "Vervangen", "voorbeeld-beoordeeld": "Voorbeeld beoordeeld", "drager-ververst": "Passage ververst",
};

/** De revisies, pas geladen bij openklappen en opnieuw bij een nieuwe revisie. */
function Historie({ regel }: { regel: Regel }) {
  const [revisies, setRevisies] = useState<RegelRevisie[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [geladen, setGeladen] = useState(0);
  const laad = () => {
    if (geladen === regel.revisie) return;
    setGeladen(regel.revisie);
    haalRegelRevisies(regel.werkgebied_id, regel.id).then(setRevisies).catch(() => setFout("De historie kon niet worden geladen."));
  };
  return (
    <Uitklap vorm="kader" samenvatting="Historie" onToggle={(e) => (e.currentTarget as HTMLDetailsElement).open && laad()} data-regel-historie>
      <div className="mt-2">
        {fout ? <Melding type="waarschuwing" compact>{fout}</Melding>
          : !revisies ? <LaadRegel klein />
          : (
            <Lijst label="Revisies">
              {revisies.map((r) => (
                <LijstRij key={r.revisie} voor={r.revisie} titel={ACTIE_ZIN[r.actie] ?? r.actie}
                  meta={`${r.actor} · ${datumTijd(r.tijdstip)}`} />
              ))}
            </Lijst>
          )}
      </div>
    </Uitklap>
  );
}
