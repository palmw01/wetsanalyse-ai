"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Plus } from "@/components/ui/Icoon";
import { MenuLijst } from "@/components/ui/MeerMenu";
import { MENU_PANEEL, MENU_RIJ } from "@/components/ui/Menu";
import { Melding } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { Popover } from "@/components/ui/Popover";
import { Groep, GroepRij } from "@/components/ui/Pagina";
import { SettingGroup } from "@/components/ui/SettingRow";
import { Skeleton } from "@/components/ui/Skeleton";
import { ONDERDEEL_PARAM, SEGMENT_PARAM, ZOEK_PARAM, type Segment } from "@/lib/aanpassingen";
import { zetLijstStand } from "@/lib/instellingenVenster";

/** Eén rij: opent als tweede niveau in het venster (`onOpen`) of als pagina (`href`, een concept). */
export interface AanpassingRij {
  id: string;
  /** De naam als tekst, voor de voorleesnaam van de rij. */
  naam: string;
  titel: React.ReactNode;
  sub?: React.ReactNode;
  status?: React.ReactNode;
  /** Buiten de klikbare rij: een keuze die meteen geldt, of het menu ⋯. */
  eind?: React.ReactNode;
  /** Onder de rij: de uitkomst van een handeling (een verbindingstest). */
  onder?: React.ReactNode;
  href?: string;
  onOpen?: () => void;
  /** Waar de zoekterm op zoekt. */
  zoektekst: string;
  data?: Record<`data-${string}`, string>;
}

export interface AanpassingGroep {
  kop: string;
  sub?: React.ReactNode;
  rijen: AanpassingRij[];
  /** Rechts in de kop van de groep (*Toon ingetrokken*). */
  status?: React.ReactNode;
  /** Wat er staat als de groep (na het zoeken) leeg is; zonder valt de groep weg. */
  leeg?: string;
}

/** De stand van een lijst in Aanpassingen uit de URL: segment, zoekterm en geopend onderdeel (naast `?instellingen=`).
 *  De zoekterm volgt het veld meteen en gaat na een korte pauze naar de URL. */
export function useLijstStand(werkplaatsAan: boolean) {
  const params = useSearchParams();
  const segment: Segment = werkplaatsAan && params.get(SEGMENT_PARAM) === "concepten" ? "concepten" : "lex";
  const onderdeel = params.get(ONDERDEEL_PARAM);
  const [zoek, setZoek] = useState(params.get(ZOEK_PARAM) ?? "");
  const inUrl = params.get(ZOEK_PARAM) ?? "";
  useEffect(() => {
    if (zoek === inUrl) return;
    const t = setTimeout(() => zetLijstStand({ [ZOEK_PARAM]: zoek || null }), 300);
    return () => clearTimeout(t);
  }, [zoek, inUrl]);
  return {
    segment, onderdeel, zoek, setZoek,
    kiesSegment: (s: Segment) => zetLijstStand({ [SEGMENT_PARAM]: s === "lex" ? null : s }),
    open: (id: string | null) => zetLijstStand({ [ONDERDEEL_PARAM]: id }),
  };
}

/** Past de rij bij de zoekterm? Elk woord ergens in de zoektekst, hoofdletterongevoelig. */
export function pastBij(rij: Pick<AanpassingRij, "zoektekst">, zoek: string): boolean {
  const woorden = zoek.toLowerCase().split(/\s+/).filter(Boolean);
  const tekst = rij.zoektekst.toLowerCase();
  return woorden.every((w) => tekst.includes(w));
}

/** De ene lijstpagina van Instellingen › Aanpassingen (plan instellingen-aanpassingen), naar het voorbeeld van Claude:
 *  een kop met uitleg en *Voeg toe*, de segmenten *In Lex* / *Concepten* met tellers en een zoekveld (`OverzichtBalk`),
 *  en daaronder de groepen (`Groep` / `GroepRij`). Methodes, Agents, Connectors en Modellen gebruiken alle deze ene
 *  component; wat verschilt komt binnen als data. Een geopend onderdeel (`detail`) vervangt de lijst. */
export function AanpassingLijst({
  titel, uitleg, voegToe, segment, onSegment, tellers, zoek, onZoek, zoekLabel, groepen, boven, laden, fout, detail,
}: {
  titel: string;
  uitleg: string;
  /** *+ Voeg toe* (`VoegToeMenu`), alleen waar toevoegen kan. */
  voegToe?: React.ReactNode;
  /** Zonder `tellers.concepten` (de werkplaats staat uit) is er geen segmentkeuze. */
  segment: Segment;
  onSegment: (s: Segment) => void;
  tellers: { lex: number; concepten?: number };
  zoek: string;
  onZoek: (z: string) => void;
  zoekLabel: string;
  groepen: AanpassingGroep[];
  /** Boven de groepen, bijvoorbeeld het formulier van *Voeg toe*. */
  boven?: React.ReactNode;
  laden: boolean;
  fout: string | null;
  detail?: React.ReactNode;
}) {
  if (detail) return <>{detail}</>;
  const segmenten = tellers.concepten === undefined ? [] : [
    { waarde: "lex" as Segment, label: "In Lex", aantal: tellers.lex },
    { waarde: "concepten" as Segment, label: "Concepten", aantal: tellers.concepten },
  ];
  const zichtbaar = groepen
    .map((g) => ({ ...g, rijen: g.rijen.filter((r) => pastBij(r, zoek)) }))
    .filter((g) => g.rijen.length > 0 || g.leeg);
  return (
    <SettingGroup titel={titel} omschrijving={uitleg} acties={voegToe}>
      <div data-aanpassing-lijst={titel.toLowerCase()}>
        <OverzichtBalk<Segment> filters={segmenten} gekozen={segment} onKies={onSegment} filterLabel="Wat je ziet"
          zoekterm={zoek} onZoek={onZoek} zoekLabel={zoekLabel} placeholder="Zoek op naam of doel" />
        {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
        {boven && <div className="mb-4">{boven}</div>}
        {laden ? (
          <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
        ) : zichtbaar.length === 0 ? (
          <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
            {zoek ? "Niets gevonden bij deze zoekterm." : "Hier staat nog niets."}
          </p>
        ) : (
          <div className="space-y-6">
            {zichtbaar.map((g) => (
              <Groep key={g.kop} kop={g.kop} telling={g.rijen.length} sub={g.sub} status={g.status} label={g.kop}
                leeg={zoek ? "Niets gevonden bij deze zoekterm." : g.leeg}>
                {g.rijen.map((r) => (
                  <GroepRij key={r.id} href={r.href} onOpen={r.onOpen ? { doe: r.onOpen, label: `Open ${r.naam}` } : undefined}
                    titel={r.titel} sub={r.sub} status={r.status} eind={r.eind} onder={r.onder} {...r.data} />
                ))}
              </Groep>
            ))}
          </div>
        )}
      </div>
    </SettingGroup>
  );
}

/** *+ Voeg toe* met een menu, rechts in de kop van een lijst (naar *Voeg toe* bij Skills in Claude). Met één keuze is
 *  het een gewone knop. */
export function VoegToeMenu({ keuzes }: { keuzes: { label: string; onKies: () => void; data: string }[] }) {
  if (keuzes.length === 1) {
    return (
      <Button variant="secondary" size="sm" onClick={keuzes[0].onKies} data-actie="voeg-toe" data-voeg-toe={keuzes[0].data}>
        <Plus className="h-4 w-4" /> Voeg toe
      </Button>
    );
  }
  return (
    <Popover ariaLabel="Voeg toe" className={`w-60 ${MENU_PANEEL}`}
      trigger={(open, toggle) => (
        <Button variant="secondary" size="sm" onClick={toggle} aria-expanded={open} aria-haspopup="menu" data-actie="voeg-toe">
          <Plus className="h-4 w-4" /> Voeg toe
        </Button>
      )}>
      {(sluit) => (
        <MenuLijst>
          {keuzes.map((k) => (
            <li role="none" key={k.data}>
              <button type="button" role="menuitem" className={MENU_RIJ} data-voeg-toe={k.data}
                onClick={() => { sluit(); k.onKies(); }}>{k.label}</button>
            </li>
          ))}
        </MenuLijst>
      )}
    </Popover>
  );
}

/** Het tweede niveau van een tab: één onderdeel, met *‹ <tab>* terug naar de lijst. De kaarten komen van de tab. */
export function AanpassingDetail({ terug, onTerug, titel, sub, status, acties, laden, fout, children }: {
  terug: string;
  onTerug: () => void;
  titel?: string;
  sub?: React.ReactNode;
  status?: React.ReactNode;
  acties?: React.ReactNode;
  laden: boolean;
  fout: string | null;
  children?: React.ReactNode;
}) {
  return (
    <section data-aanpassing-detail className="space-y-4">
      <button type="button" onClick={onTerug} data-terug
        className="focus-ring -ml-2 inline-flex min-h-[36px] items-center gap-1 rounded-knop px-2 text-sm font-medium text-lint hover:bg-surface coarse:min-h-[44px]">
        <span aria-hidden>‹</span> {terug}
      </button>
      {fout && <Melding type="fout">{fout}</Melding>}
      {laden && !fout ? (
        <div className="space-y-3"><Skeleton className="h-6 w-64" /><Skeleton className="h-40 w-full" /></div>
      ) : titel ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-[999_1_16rem]">
              <h3 className="font-display text-base font-semibold text-lint [overflow-wrap:anywhere]">{titel}</h3>
              {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
              {status && <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted">{status}</div>}
            </div>
            {acties && <div className="flex shrink-0 flex-wrap items-center gap-2">{acties}</div>}
          </div>
          {children}
        </>
      ) : null}
    </section>
  );
}
