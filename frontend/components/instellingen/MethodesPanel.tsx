"use client";

import { useState } from "react";

import { ConceptBewerken, VoegToeFormulier, conceptGroep, magToevoegen, useWerkplaats } from "@/components/aanpassingen/Concepten";
import {
  AanpassingDetail, AanpassingLijst, VoegToeMenu, useLijstStand, type AanpassingGroep,
} from "@/components/instellingen/AanpassingLijst";
import { HerkomstKaart, tekst, useCatalogus, useOnderdeel } from "@/components/instellingen/OnderdeelKaarten";
import { Lijst, LijstRij, StatusLabel } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { naamVan, type Onderdeel } from "@/lib/catalogus";

/** Instellingen › Aanpassingen › Methodes: de methode-skills die Lex volgt (`.claude/skills/`), en met de werkplaats aan
 *  je eigen concepten ervan. Een methode opent als tweede niveau met haar rollen en hun methodetekst. */
export function MethodesPanel() {
  const werkplaats = useWerkplaats();
  const lijst = useLijstStand(werkplaats.stand.aan);
  const { data, fout } = useCatalogus();
  const [toonIngetrokken, setToonIngetrokken] = useState(false);
  const [voegToe, setVoegToe] = useState<"nieuw" | "vanuit" | null>(null);

  const methodes = data?.onderdelen.filter((o) => o.soort === "methode") ?? [];
  const rollen = data?.onderdelen.filter((o) => o.soort === "rol") ?? [];
  const concepten = conceptGroep(werkplaats, "skill", toonIngetrokken, setToonIngetrokken);
  // Een oude link naar een rol opent de methode waar die rol bij hoort.
  const open = lijst.onderdeel?.startsWith("rol/")
    ? rollen.find((r) => r.id === lijst.onderdeel)?.deel_van ?? null
    : lijst.onderdeel?.startsWith("methode/") ? lijst.onderdeel : null;

  const groepen: AanpassingGroep[] = lijst.segment === "concepten" ? [concepten] : [{
    kop: "Methodes",
    rijen: methodes.map((m) => {
      const aantal = rollenVan(m, rollen).length;
      return {
        id: m.id, naam: m.label, titel: m.label, onOpen: () => lijst.open(m.id), zoektekst: `${m.label} ${m.doel} ${m.id}`,
        sub: [m.doel, aantal ? `${aantal} ${aantal === 1 ? "rol" : "rollen"}` : "nog aan geen rol gekoppeld"].join(" · "),
        status: m.aan ? undefined : <StatusLabel>hier uit</StatusLabel>, data: { "data-onderdeel": m.id },
      };
    }),
  }];

  return (
    <AanpassingLijst
      titel="Methodes"
      uitleg="De methode die Lex volgt, als skill. Een methode voert zelf niets uit: ze geeft elke rol zijn methodetekst."
      voegToe={magToevoegen(werkplaats, "skill") ? <VoegToeMenu keuzes={[
        { label: "Nieuwe methode", data: "nieuw", onKies: () => { lijst.kiesSegment("concepten"); setVoegToe("nieuw"); } },
        { label: "Vanuit een methode in Lex …", data: "vanuit", onKies: () => { lijst.kiesSegment("concepten"); setVoegToe("vanuit"); } },
      ]} /> : undefined}
      segment={lijst.segment}
      onSegment={lijst.kiesSegment}
      tellers={{ lex: methodes.length, concepten: werkplaats.stand.aan ? concepten.rijen.length : undefined }}
      zoek={lijst.zoek}
      onZoek={lijst.setZoek}
      zoekLabel="Zoeken in de methodes"
      groepen={groepen}
      boven={voegToe && lijst.segment === "concepten" ? (
        <VoegToeFormulier soort="skill" keuze={voegToe} onAnnuleer={() => setVoegToe(null)}
          vanuitLex={methodes.map((m) => ({ naam: naamVan(m.id), label: m.label }))} />
      ) : undefined}
      laden={!data && !fout}
      fout={fout ?? (lijst.segment === "concepten" ? werkplaats.fout : null)}
      detail={open ? <MethodeDetail id={open} rollen={rollen} openRol={lijst.onderdeel?.startsWith("rol/") ? lijst.onderdeel : null}
        onTerug={() => lijst.open(null)} /> : undefined}
    />
  );
}

/** De rollen die hun methodetekst uit deze methode halen. */
function rollenVan(methode: Onderdeel, rollen: Onderdeel[]): Onderdeel[] {
  return rollen.filter((r) => r.deel_van === methode.id);
}

function MethodeDetail({ id, rollen, openRol, onTerug }: { id: string; rollen: Onderdeel[]; openRol: string | null; onTerug: () => void }) {
  const { o, fout } = useOnderdeel(id);
  const eigen = o ? rollenVan(o, rollen) : [];
  return (
    <AanpassingDetail terug="Methodes" onTerug={onTerug} laden={!o} fout={fout} titel={o?.label} sub={o?.doel}
      status={o && <><span>versie <span className="font-mono">{o.versie}</span></span>{!o.aan && <StatusLabel>hier uit</StatusLabel>}</>}
      acties={o ? <ConceptBewerken soort="skill" naam={naamVan(o.id)} /> : undefined}>
      {o && (
        <div className="space-y-4">
          <Kaart titel="Rollen" telling={eigen.length} data-blok="rollen"
            toelichting="Elke rol krijgt de methodetekst van zijn secties letterlijk mee in de systeemprompt.">
            {eigen.length ? (
              <Lijst label="Rollen">
                {eigen.map((r) => <RolRij key={r.id} rol={r} open={openRol === r.id} />)}
              </Lijst>
            ) : <p className="text-sm text-muted">Deze methode is nog aan geen rol van Lex gekoppeld.</p>}
          </Kaart>
          <HerkomstKaart o={o} />
        </div>
      )}
    </AanpassingDetail>
  );
}

/** Eén rol: wie hem krijgt, en zijn methodetekst als je hem opent. */
function RolRij({ rol, open }: { rol: Onderdeel; open: boolean }) {
  const [lezen, setLezen] = useState(open);
  const { o, fout } = useOnderdeel(lezen ? rol.id : null);
  type Sectie = { id: string; tekst: string; bronnen: string[] };
  const secties = (Array.isArray(o?.inhoud.secties) ? o.inhoud.secties : []) as Sectie[];
  return (
    <LijstRij titel={naamVan(rol.id)} meta={rol.ingang.length ? `voor ${rol.ingang.join(", ")}` : undefined} data-rol={naamVan(rol.id)}
      acties={<button type="button" onClick={() => setLezen((x) => !x)} aria-expanded={lezen}
        className="focus-ring rounded text-xs font-medium text-lint hover:underline">{lezen ? "Inklappen" : "Methodetekst"}</button>}>
      {lezen && (
        <div className="mt-2 space-y-3">
          {fout && <p className="text-sm text-fout">{fout}</p>}
          {!o && !fout && <Skeleton className="h-16 w-full" />}
          {secties.map((s) => (
            <section key={tekst(s.id)} data-sectie={tekst(s.id)}>
              <h4 className="text-xs font-semibold text-ink">{tekst(s.id)} <span className="font-normal text-muted">· bronnen {tekst(s.bronnen)}</span></h4>
              <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{tekst(s.tekst)}</p>
            </section>
          ))}
        </div>
      )}
    </LijstRij>
  );
}
