"use client";

import { useEffect, useRef, useState } from "react";

import { Diagram2c } from "@/components/annotaties/Diagram2c";
import { ImplicietePartijen, RelatieBlok, type RelatieBediening } from "@/components/annotaties/Relaties";
import { Button } from "@/components/ui/Button";
import { LaadStand } from "@/components/ui/LaadStand";
import { Leeg } from "@/components/ui/Leeg";
import { KlasseLabel, Sectie, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { TekstEnLijst } from "@/components/ui/TekstEnLijst";
import { weergaveVersie, type NodeImpliciet, type NodeWeergave } from "@/lib/annotatieNode";
import { knoopSleutel, type DiagramData, type DiagramKnoop, type DiagramSet, type OntbrekendeRol } from "@/lib/diagram2c";

/** Wat er in een diagram gekozen is: een knoop, eventueel via een lijn (dan is die lijn gemarkeerd), of een ontbrekende
 *  rol (dan opent *Verbind met…* bij de centrale formulering, met het type voorgekozen). */
interface Keuze {
  diagram: string;
  knoop: DiagramKnoop;
  lijn?: string;
  rol?: OntbrekendeRol;
}

type Bediening = (laagId?: string) => RelatieBediening | undefined;

/** Het deel van de breedte voor het diagram, standaard: een tekening wordt in een smalle kolom onleesbaar klein. */
const DIAGRAM_AANDEEL = 70;

/** De tab *Diagram* van het annotatiepaneel: de samenhang van deelactiviteit 2c (Handleiding §3.4c) bij de bepaling in
 *  beeld. Elk diagram staat rond één centrale formulering – dezelfde keuze als het werkgebiedrapport – met wat de methode
 *  nog verwacht. Kies je een knoop of een lijn, dan staat ernaast (smal: eronder) het blok *Relaties* van die markering:
 *  daar verbind, beoordeel en wis je, met dezelfde handelingen als op de reviewkaart. Dezelfde indeling als tekst en
 *  kaartjes (`TekstEnLijst`), zodat het diagram in beeld blijft terwijl je werkt. Het diagram tekent wat is vastgelegd;
 *  na elke handeling haalt het zich opnieuw op. */
export function DiagramTab({ view, haal, gebruiker, bediening, impliciet, afronden, onToonInTekst }: {
  view: NodeWeergave;
  haal: (bronIri: string) => Promise<DiagramSet>;
  gebruiker?: string;
  /** Zonder (een afgeronde laag, een oude versie) is het diagram alleen te lezen. */
  bediening?: Bediening;
  impliciet?: { onMaak?: (invoer: { label: string; toelichting: string }) => Promise<void>; onWis?: (p: NodeImpliciet) => Promise<void> };
  /** Afronden is gevraagd: eerst de samenhang bekijken. */
  afronden?: boolean;
  onToonInTekst: (elementId: string) => void;
}) {
  const [set, setSet] = useState<DiagramSet>();
  const [fout, setFout] = useState("");
  const [keuze, setKeuze] = useState<Keuze>();
  const [poging, setPoging] = useState(0);
  const versie = weergaveVersie(view);
  const bron = view.doel.bron_iri;

  useEffect(() => {
    let actueel = true;
    haal(bron).then((s) => { if (actueel) { setSet(s); setFout(""); } })
      .catch((e) => { if (actueel) setFout(e instanceof Error ? e.message : "Het diagram kon niet worden geladen."); });
    return () => { actueel = false; };
  }, [haal, bron, versie, poging]);

  if (!set) {
    return <div className="p-5"><LaadStand wat="Het diagram" skelet="tekst" fout={fout} onOpnieuw={() => { setFout(""); setPoging((n) => n + 1); }} /></div>;
  }
  // Een keuze in een diagram dat er na een handeling niet meer is, vervalt.
  const gekozenDiagram = keuze && set.diagrammen.find((d) => d.diagram.centraal === keuze.diagram);
  const actief = gekozenDiagram ? keuze : undefined;

  const diagrammen = (
    <div className="space-y-4 p-4" data-diagram-tab>
      {afronden && (
        <Melding type="uitleg" compact>
          Bekijk eerst de samenhang: klopt elk diagram en staat erin wat de methode verwacht? Rond daarna af met
          <span className="font-medium"> Annotatie afronden</span> bovenaan.
        </Melding>
      )}
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {set.diagrammen.length === 0 ? (
        <Leeg>
          Deze bepaling heeft nog geen rechtsbetrekking, rechtsfeit, afleidingsregel of voorwaarde: er is geen diagram
          (deelactiviteit 2c).
        </Leeg>
      ) : set.diagrammen.map((d) => (
        <DiagramKaart key={d.diagram.centraal} data={d} view={view} keuze={actief?.diagram === d.diagram.centraal ? actief : undefined}
          onKies={setKeuze} bediening={bediening} />
      ))}
      {impliciet && (impliciet.onMaak || (view.impliciet ?? []).length > 0) && (
        <ImplicietePartijen partijen={view.impliciet ?? []} gebruiker={gebruiker} onMaak={impliciet.onMaak} onWis={impliciet.onWis} />
      )}
    </div>
  );
  const keuzeKolom = (
    <div className="p-4" data-diagram-keuze>
      {actief ? (
        <Gekozen keuze={actief} view={view} gebruiker={gebruiker} bediening={bediening} onToonInTekst={onToonInTekst}
          onSluit={() => setKeuze(undefined)} />
      ) : set.diagrammen.length > 0 && (
        <Leeg klein>
          Kies een knoop of een relatie in het diagram om haar relaties te zien en te bewerken, of vul aan wat nog niet is
          vastgelegd. Een gestippelde lijn is een voorstel van Lex.
        </Leeg>
      )}
    </div>
  );
  return <TekstEnLijst tekst={diagrammen} lijst={keuzeKolom} standaard={DIAGRAM_AANDEEL} opslag="lex.diagram.aandeel"
    label="Verdeling tussen diagram en relaties" />;
}

function DiagramKaart({ data, view, keuze, onKies, bediening }: {
  data: DiagramData;
  view: NodeWeergave;
  keuze?: Keuze;
  onKies: (k: Keuze | undefined) => void;
  bediening?: Bediening;
}) {
  const d = data.diagram;
  const centraal = d.knopen.find((k) => k.soort === "element" && k.id === d.centraal)!;
  const tekst = centraal.tekst.length > 90 ? `${centraal.tekst.slice(0, 87)}…` : centraal.tekst;
  const kanBewerken = !!bediening?.(view.elementen.find((e) => e.id === d.centraal)?.laag_id);
  const kies = (k: Keuze) => onKies(keuze && knoopSleutel(keuze.knoop) === knoopSleutel(k.knoop) && keuze.lijn === k.lijn
    && keuze.rol?.label === k.rol?.label ? undefined : k);

  return (
    <Sectie niveau={3} titel={<>Rond {d.klasse.toLowerCase()} <span className="font-normal text-muted">“{tekst}”</span></>}
      className="rounded-kaart border border-line bg-surface/40 p-3" data-diagram-kaart={d.centraal}>
      <div className="rounded-knop border border-line bg-paper p-2">
        <Diagram2c data={data} label={`Diagram rond de ${d.klasse.toLowerCase()} “${tekst}”. Kies een knoop of een relatie om haar te bewerken.`}
          gekozenKnoop={keuze ? knoopSleutel(keuze.knoop) : undefined} gekozenLijn={keuze?.lijn}
          onKiesKnoop={(knoop) => kies({ diagram: d.centraal, knoop })}
          onKiesLijn={(l) => {
            // Een lijn kies je via haar kant in deze bepaling: daar staat ze in het blok *Relaties*.
            const hier = (id: string) => view.elementen.some((e) => e.id === id);
            const kant = hier(l.van) ? l.van : l.naar;
            const knoop = d.knopen.find((k) => k.id === kant);
            if (knoop) kies({ diagram: d.centraal, knoop, lijn: l.relatie_id });
          }} />
      </div>
      {data.ontbreekt_rollen.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs" data-ontbreekt>
          <span className="text-muted">Nog niet vastgelegd:</span>
          {data.ontbreekt_rollen.map((r) => (
            kanBewerken ? (
              <Button key={r.label} size="xs" variant="secondary" aria-pressed={keuze?.rol?.label === r.label}
                title={`Leg de relatie: ${r.label}`} onClick={() => kies({ diagram: d.centraal, knoop: centraal, rol: r })}>
                + {r.label}
              </Button>
            ) : <StatusLabel key={r.label} klein>{r.label}</StatusLabel>
          ))}
        </div>
      )}
    </Sectie>
  );
}

/** Naast het diagram: de gekozen markering met haar relaties. Een markering in een andere bepaling bewerk je daar. */
function Gekozen({ keuze, view, gebruiker, bediening, onToonInTekst, onSluit }: {
  keuze: Keuze;
  view: NodeWeergave;
  gebruiker?: string;
  bediening?: Bediening;
  onToonInTekst: (elementId: string) => void;
  onSluit: () => void;
}) {
  const k = keuze.knoop;
  const element = k.soort === "element" ? view.elementen.find((e) => e.id === k.id) : undefined;
  const ref = useRef<HTMLDivElement>(null);
  // Smal staat de keuze onder het diagram: breng haar in beeld (en het formulier, bij een ontbrekende rol).
  useEffect(() => { ref.current?.scrollIntoView?.({ block: "nearest" }); }, [k.id, keuze.lijn, keuze.rol?.label]);
  return (
    <div ref={ref} className="rounded-knop border border-line bg-paper p-3" data-diagram-gekozen={knoopSleutel(k)}>
      {/* De klasse en de knoppen op één regel, het citaat eronder over de volle breedte: de kolom is smal. */}
      <div className="flex flex-wrap items-center gap-2">
        {k.klasse && <KlasseLabel klasse={k.klasse} klein />}
        {k.soort === "impliciet" && <StatusLabel klein>impliciet</StatusLabel>}
        <span className="ml-auto flex gap-1">
          {element && <Button size="xs" variant="ghost" onClick={() => onToonInTekst(element.id)}>Toon in de tekst</Button>}
          <Button size="xs" variant="ghost" onClick={onSluit} aria-label="Keuze opheffen">Sluiten</Button>
        </span>
      </div>
      <p className="mt-1 text-sm">
        {k.soort === "impliciet" ? <span className="font-medium">{k.tekst}</span> : <>“{k.tekst}”</>}
        {k.elders && <span className="text-muted"> · {k.elders}</span>}
      </p>
      {keuze.rol && (
        <p className="mt-2 text-xs text-muted">
          Leg de relatie <span className="text-ink">{keuze.rol.label}</span>: kies de markering die die rol heeft.
        </p>
      )}
      {element ? (
        <RelatieBlok key={`${element.id}:${keuze.rol?.label ?? ""}`} view={view} elementId={element.id} gebruiker={gebruiker}
          bediening={bediening?.(element.laag_id)} zonderDiagram gemarkeerd={keuze.lijn}
          voorkeur={keuze.rol ? { codes: keuze.rol.codes, sleutel: keuze.rol.label } : undefined} />
      ) : (
        <p className="mt-2 text-xs text-muted">
          {k.soort === "impliciet"
            ? "Een impliciete partij heeft geen eigen relaties-blok: kies de markering aan de andere kant van de lijn."
            : "Deze markering staat in een andere bepaling. Open die bepaling om haar relaties te bewerken."}
        </p>
      )}
    </div>
  );
}
