"use client";

import { useEffect, useMemo, useState } from "react";

import { BronBoom } from "@/components/ui/BronBoom";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input, Select } from "@/components/ui/Field";
import { IcoonBevestig } from "@/components/ui/IcoonBevestig";
import { KlasseLabel, Lijst, LijstRij, StatusLabel } from "@/components/ui/Lijst";
import { MeerMenu, MenuKeuze, MenuKnop, MenuLink, MenuVerwijder } from "@/components/ui/MeerMenu";
import { Melding } from "@/components/ui/Melding";
import { BegripBlok, type BegripWeergaveVorm } from "@/components/werkgebieden/BegripBlok";
import { Herbeoordeling } from "@/components/werkgebieden/Herbeoordeling";
import { foutTekst, haalInventaris, koppelElementen, ontkoppel, wijzigKoppeling } from "@/lib/api";
import { ACTUALITEIT_LABEL, BEOORDELING_LABEL, KOPPELROL_LABEL, sorteerKoppelingen } from "@/lib/begrippen";
import { bouwBoom, regelingUitLabel } from "@/lib/bronPlaats";
import { klasseLabel } from "@/lib/jas";
import type { Begrip, GeraakteKoppeling, InventarisElement, KoppelBeoordeling, KoppelRol, Koppeling } from "@/lib/types";
import type { BegripMutatie } from "@/lib/useBegrip";
import { usePlaatsen } from "@/lib/usePlaatsen";
import { annotatieHref, filterElementen } from "@/lib/werkgebied";
import { elementPad } from "@/lib/werkgebiedPaden";

const ROLLEN = Object.keys(KOPPELROL_LABEL) as KoppelRol[];
const BEOORDELING_TOON = { akkoord: "groen", afgewezen: "rood", open: "neutraal" } as const;

/** De bronpassages van het begrip, elk een eigen rij: de letterlijke tekst zoals die gekoppeld werd, waar hij staat,
 *  en hoe het er nu mee staat. Een samenvatting vervangt de passages nooit. Akkoord is een vinkje in de rij; de rol,
 *  afwijzen, losmaken en de weg naar het element staan achter ⋯. */
export function BegripPassages({ id, begrip, primair, muteer, geraakt, weergave }: {
  id: string;
  begrip: Begrip;
  primair: Record<string, { begrip_id: string; naam: string }>;
  muteer: BegripMutatie;
  /** Herbeoordelen (fase F1): de passages die veranderden, op koppeling-id. */
  geraakt?: Map<string, GeraakteKoppeling>;
  weergave: BegripWeergaveVorm;
}) {
  const [kiezerOpen, setKiezerOpen] = useState(false);
  const passages = sorteerKoppelingen(begrip.koppelingen);
  return (
    <BegripBlok weergave={weergave} titel="Passages" telling={passages.length} data-blok="passages"
      acties={begrip.status !== "vervangen" && (
        <Button size="xs" variant="secondary" onClick={() => setKiezerOpen(true)}>Passages toevoegen</Button>
      )}>
      {passages.length === 0 ? (
        <p className="text-sm text-muted">
          Nog geen passages. Een begrip krijgt zijn onderbouwing uit de annotaties: voeg de passages toe die
          het aanduiden of de definitie dragen.
        </p>
      ) : (
        <Lijst label="Passages van dit begrip">
          {passages.map((k) => (
            <Passage key={k.id} id={id} begrip={begrip} koppeling={k} muteer={muteer} geraakt={geraakt?.get(k.id)} />
          ))}
        </Lijst>
      )}
      {kiezerOpen && (
        <PassagesDialoog id={id} begrip={begrip} primair={primair} muteer={muteer} onKlaar={() => setKiezerOpen(false)} />
      )}
    </BegripBlok>
  );
}

function Passage({ id, begrip, koppeling: k, muteer, geraakt }: {
  id: string;
  begrip: Begrip;
  koppeling: Koppeling;
  muteer: BegripMutatie;
  geraakt?: GeraakteKoppeling;
}) {
  const wijzig = (w: { beoordeling?: KoppelBeoordeling; rol?: KoppelRol }) =>
    muteer((r) => wijzigKoppeling(id, begrip.id, k.id, { verwachte_revisie: r, ...w }));
  // Elke passage heeft dezelfde knoppen; voor een schermlezer zegt de naam bij welke passage ze horen.
  const bij = `“${k.bewijs.tekst}”`;
  const vervangen = begrip.status === "vervangen";
  const open = k.beoordeling === "open";
  return (
    <LijstRij data-passage={k.element_id} className={k.beoordeling === "afgewezen" ? "opacity-70" : ""}
      titel={<blockquote>{bij}</blockquote>}
      meta={
        <span className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
          <KlasseLabel klasse={k.bewijs.klasse} klein />
          <span>{k.bewijs.vindplaats} · {KOPPELROL_LABEL[k.rol]}</span>
        </span>
      }
      status={<>
        {!open && (
          <StatusLabel toon={BEOORDELING_TOON[k.beoordeling]} uitleg={k.beoordeeld_door ? `Door ${k.beoordeeld_door}` : undefined}>
            {BEOORDELING_LABEL[k.beoordeling]}
          </StatusLabel>
        )}
        {open && !vervangen && (
          <IcoonBevestig soort="akkoord" label={`Akkoord met ${bij}`} onBevestig={async () => { await wijzig({ beoordeling: "akkoord" }); }} />
        )}
        <MeerMenu label={`Acties: ${bij}`}>
          {(sluit) => <>
            {!vervangen && ROLLEN.map((r) => (
              <MenuKeuze key={r} gekozen={k.rol === r} onClick={() => { sluit(); void wijzig({ rol: r }); }}>{KOPPELROL_LABEL[r]}</MenuKeuze>
            ))}
            {!vervangen && (open ? (
              <MenuKnop ariaLabel={`Wijs ${bij} af`} onClick={() => { sluit(); void wijzig({ beoordeling: "afgewezen" }); }}>Afwijzen</MenuKnop>
            ) : (
              <MenuKnop ariaLabel={`Beoordeling van ${bij} terugzetten`} onClick={() => { sluit(); void wijzig({ beoordeling: "open" }); }}>Beoordeling terugzetten</MenuKnop>
            ))}
            <MenuLink href={elementPad(k.element_id)} ariaLabel={`Open het element ${bij}`}>Element</MenuLink>
            <MenuLink href={annotatieHref(k.bewijs.eigenaar_iri, k.element_id)} ariaLabel={`Bekijk ${bij} in de annotatie`}>Bekijk in de annotatie</MenuLink>
            {!vervangen && (
              <MenuVerwijder vraag="Losmaken?" ariaLabel={`Maak ${bij} los van dit begrip`}
                titel="Maakt de passage los van dit begrip; de annotatie blijft staan."
                onBevestig={async () => { await muteer((r) => ontkoppel(id, begrip.id, k.id, r)); }}>Losmaken</MenuVerwijder>
            )}
          </>}
        </MeerMenu>
      </>}>
      {k.vervangt && (
        <details className="mt-1 text-xs text-muted">
          <summary className="focus-ring cursor-pointer rounded">Vervangt een eerdere passage</summary>
          <p className="mt-0.5">
            Toen: “{k.vervangt.bewijs.tekst}” · {klasseLabel(k.vervangt.bewijs.klasse)} · {k.vervangt.bewijs.vindplaats}
          </p>
        </details>
      )}
      {(k.bevestigingen?.length ?? 0) > 0 && (
        <p className="mt-1 text-xs text-muted">
          Na een wijziging bevestigd door {k.bevestigingen!.at(-1)!.door}; de stand van het koppelen blijft bewaard.
        </p>
      )}
      {geraakt && <Herbeoordeling id={id} begrip={begrip} geraakt={geraakt} muteer={muteer} />}
      {!geraakt && (k.actualiteit !== "actueel" || !k.annotatie_beoordeeld) && (
        <p className="mt-1 text-xs text-aandacht-geel-tekst">
          {[k.actualiteit !== "actueel" && ACTUALITEIT_LABEL[k.actualiteit],
            k.actualiteit === "actueel" && !k.annotatie_beoordeeld && "annotatie nog niet door een jurist beoordeeld"]
            .filter(Boolean).join(" · ")}
        </p>
      )}
    </LijstRij>
  );
}

/** Passages toevoegen uit de inventaris van het werkgebied, als boom met vinkjes, zoals *Bronnen koppelen*. Wat al bij
 *  dit begrip hoort staat er niet in; wat een ander begrip aanduidt, zegt dat erbij. */
function PassagesDialoog({ id, begrip, primair, muteer, onKlaar }: {
  id: string;
  begrip: Begrip;
  primair: Record<string, { begrip_id: string; naam: string }>;
  muteer: BegripMutatie;
  onKlaar: () => void;
}) {
  const [elementen, setElementen] = useState<InventarisElement[] | null>(null);
  const [labels, setLabels] = useState<Map<string, string>>(new Map());
  const [fout, setFout] = useState<string | null>(null);
  const [term, setTerm] = useState("");
  const [gekozen, setGekozen] = useState<ReadonlySet<string>>(new Set());
  const [rol, setRol] = useState<KoppelRol>("duiding");
  const [bezig, setBezig] = useState(false);

  useEffect(() => {
    let levend = true;
    haalInventaris(id)
      .then((inv) => {
        if (!levend) return;
        setElementen(inv.elementen);
        setLabels(new Map(inv.selecties.map((s) => [s.id, s.label])));
      })
      .catch((e) => levend && setFout(foutTekst(e, "De inventaris kon niet worden geladen.")));
    return () => { levend = false; };
  }, [id]);

  const getoond = useMemo(() => {
    const al = new Set(begrip.koppelingen.map((k) => k.element_id));
    return elementen ? filterElementen(elementen.filter((e) => !al.has(e.id)), { rol: "alle", klasse: "alle", term }) : [];
  }, [elementen, begrip.koppelingen, term]);
  const plaatsen = usePlaatsen(getoond.map((e) => e.eigenaar_iri));
  const boom = useMemo(() => bouwBoom(getoond, {
    iri: (e) => e.eigenaar_iri, sleutel: (e) => e.id, naam: (e) => e.eigenaar_iri, plaatsen,
    regelingNaam: (e) => regelingUitLabel(labels.get(e.selecties[0]) ?? ""),
  }), [getoond, plaatsen, labels]);

  async function koppel() {
    setBezig(true);
    const gelukt = await muteer(
      (r) => koppelElementen(id, begrip.id, { verwachte_revisie: r, element_ids: [...gekozen], rol }),
      {
        gelukt: gekozen.size === 1 ? "1 passage toegevoegd." : `${gekozen.size} passages toegevoegd.`,
        opFout: (e) => { setFout(foutTekst(e)); return true; },
      },
    );
    setBezig(false);
    if (gelukt) onKlaar();
  }

  return (
    <Dialog label={`Passages bij ${begrip.inhoud.naam}`} variant="compact" onSluit={onKlaar}>
      <div className="flex min-h-0 flex-1 flex-col" data-passages-dialoog={begrip.id}>
        <div className="shrink-0 border-b border-line px-5 py-3.5">
          <p className="text-xs text-muted">Passages toevoegen</p>
          <h2 className="font-display text-base font-semibold text-lint">{begrip.inhoud.naam}</h2>
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input type="search" value={term} onChange={(e) => setTerm(e.target.value)} aria-label="Zoeken in de inventaris"
              placeholder="Zoek in de passages van het werkgebied" />
            <Select value={rol} onChange={(e) => setRol(e.target.value as KoppelRol)} aria-label="Rol van de nieuwe passages" className="shrink-0 sm:w-56">
              {ROLLEN.map((r) => <option key={r} value={r}>{KOPPELROL_LABEL[r]}</option>)}
            </Select>
          </div>
          {fout && <Melding type="fout" compact>{fout}</Melding>}
          {elementen === null && !fout ? (
            <p className="text-xs text-muted">De inventaris wordt opgehaald…</p>
          ) : getoond.length === 0 ? (
            <p className="text-xs text-muted">Geen passage die hierop past.</p>
          ) : (
            <BronBoom boom={boom} label="Passages om toe te voegen"
              vinkjes={{ gekozen, naam: (b) => `Kies “${b.data.tekst}”`, onZet: (ids, aan) => setGekozen((s) => {
                const n = new Set(s);
                for (const k of ids) { if (aan) n.add(k); else n.delete(k); }
                return n;
              }) }}
              renderBlad={(b) => {
                const elders = primair[b.data.id] && primair[b.data.id].begrip_id !== begrip.id ? primair[b.data.id] : undefined;
                return (
                  <span className="min-w-0 text-sm">
                    <span className="mr-1 text-xs text-muted">{b.label}</span>
                    <KlasseLabel klasse={b.data.klasse} klein className="mr-1.5" />
                    <span className="text-ink">“{b.data.tekst}”</span>
                    {elders && <span className="block text-xs text-muted">duidt al “{elders.naam}” aan</span>}
                  </span>
                );
              }} />
          )}
        </div>
        <div className="flex shrink-0 flex-col gap-2 border-t border-line px-5 py-3 sm:flex-row">
          <Button size="sm" className="w-full sm:w-auto" disabled={bezig || gekozen.size === 0} onClick={() => void koppel()}>
            {bezig ? "Bezig…" : gekozen.size ? `Toevoegen (${gekozen.size})` : "Toevoegen"}
          </Button>
          <Button size="sm" variant="ghost" className="w-full sm:w-auto" onClick={onKlaar}>Annuleren</Button>
        </div>
      </div>
    </Dialog>
  );
}
