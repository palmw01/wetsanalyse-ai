"use client";

import { useState } from "react";

import { VoegToeFormulier, conceptGroep, magToevoegen, useWerkplaats } from "@/components/aanpassingen/Concepten";
import {
  AanpassingDetail, AanpassingLijst, VoegToeMenu, useLijstStand, type AanpassingGroep,
} from "@/components/instellingen/AanpassingLijst";
import { HerkomstKaart, LangeTekst, tekst, useCatalogus, useOnderdeel } from "@/components/instellingen/OnderdeelKaarten";
import { Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";
import { methodeLabel, naamVan, soortVan, type Onderdeel } from "@/lib/catalogus";
import { kiesInstellingenTab } from "@/lib/instellingenVenster";

/** Instellingen › Aanpassingen › Agents: de agentprofielen van Lex (`.claude/lex-agents/`), elk met wat het doet, zijn
 *  connectors en sjablonen, en met de werkplaats aan je eigen concepten ervan. */
export function AgentsPanel() {
  const werkplaats = useWerkplaats();
  const lijst = useLijstStand(werkplaats.stand.aan);
  const { data, fout } = useCatalogus();
  const [toonIngetrokken, setToonIngetrokken] = useState(false);
  const [voegToe, setVoegToe] = useState<"nieuw" | "vanuit" | null>(null);

  const alle = data?.onderdelen ?? [];
  const profielen = alle.filter((o) => o.soort === "agentprofiel");
  const concepten = conceptGroep(werkplaats, "agentprofiel", toonIngetrokken, setToonIngetrokken);
  const open = lijst.onderdeel?.startsWith("agentprofiel/") ? lijst.onderdeel : null;

  const groepen: AanpassingGroep[] = lijst.segment === "concepten" ? [concepten] : [{
    kop: "Agentprofielen",
    rijen: profielen.map((p) => {
      const n = afhankelijk(p, "connector").length, s = afhankelijk(p, "sjabloon").length;
      return {
        id: p.id, naam: p.label, titel: p.label, onOpen: () => lijst.open(p.id), zoektekst: `${p.label} ${p.doel} ${p.id}`,
        sub: [p.doel, n && `${n} ${n === 1 ? "connector" : "connectors"}`, s && `${s} ${s === 1 ? "sjabloon" : "sjablonen"}`]
          .filter(Boolean).join(" · "),
        status: p.aan ? undefined : <StatusLabel>hier uit</StatusLabel>, data: { "data-onderdeel": p.id },
      };
    }),
  }];

  return (
    <AanpassingLijst
      titel="Agents"
      uitleg="Wie een vraag beantwoordt: elk profiel met een eigen opdracht, connectors en sjablonen."
      voegToe={magToevoegen(werkplaats, "agentprofiel") ? <VoegToeMenu keuzes={[
        { label: "Nieuw agentprofiel", data: "nieuw", onKies: () => { lijst.kiesSegment("concepten"); setVoegToe("nieuw"); } },
        { label: "Vanuit een agent in Lex …", data: "vanuit", onKies: () => { lijst.kiesSegment("concepten"); setVoegToe("vanuit"); } },
      ]} /> : undefined}
      segment={lijst.segment}
      onSegment={lijst.kiesSegment}
      tellers={{ lex: profielen.length, concepten: werkplaats.stand.aan ? concepten.rijen.length : undefined }}
      zoek={lijst.zoek}
      onZoek={lijst.setZoek}
      zoekLabel="Zoeken in de agents"
      groepen={groepen}
      boven={voegToe && lijst.segment === "concepten" ? (
        <VoegToeFormulier soort="agentprofiel" keuze={voegToe} onAnnuleer={() => setVoegToe(null)}
          vanuitLex={profielen.map((p) => ({ naam: naamVan(p.id), label: p.label }))} />
      ) : undefined}
      laden={!data && !fout}
      fout={fout ?? (lijst.segment === "concepten" ? werkplaats.fout : null)}
      detail={open ? <AgentDetail id={open} alle={alle} onTerug={() => lijst.open(null)} /> : undefined}
    />
  );
}

/** De onderdelen van een soort waar een profiel op leunt (zijn connectors, zijn sjablonen). */
function afhankelijk(o: Pick<Onderdeel, "hangt_af_van">, soort: "connector" | "sjabloon" | "methode" | "rol"): string[] {
  return o.hangt_af_van.filter((id) => soortVan(id) === soort);
}

function AgentDetail({ id, alle, onTerug }: { id: string; alle: Onderdeel[]; onTerug: () => void }) {
  const { o, fout } = useOnderdeel(id);
  const label = (x: string) => alle.find((a) => a.id === x)?.label ?? naamVan(x);
  const connectors = o ? afhankelijk(o, "connector") : [];
  const sjablonen = o ? afhankelijk(o, "sjabloon") : [];
  const methodes = o ? afhankelijk(o, "methode") : [];
  const rol = o ? afhankelijk(o, "rol")[0] : undefined;
  return (
    <AanpassingDetail terug="Agents" onTerug={onTerug} laden={!o} fout={fout} titel={o?.label} sub={o?.doel}
      status={o && <><span>versie <span className="font-mono">{o.versie}</span></span>{!o.aan && <StatusLabel>hier uit</StatusLabel>}</>}>
      {o && (
        <div className="space-y-4">
          <Kaart titel="Wat het gebruikt" data-blok="gebruikt">
            <Regels className="text-sm">
              <Regel naam="Methode">
                {methodes.length ? methodes.map((m, i) => (
                  <span key={m}>{i > 0 && ", "}<NaarTab tab="methodes" id={m}>{label(m)}</NaarTab></span>
                )) : methodeLabel(o.methode) || "geen"}
                {rol && <> · rol <NaarTab tab="methodes" id={rol}>{naamVan(rol)}</NaarTab></>}
              </Regel>
              <Regel naam="Connectors">{connectors.length ? connectors.map((c, i) => (
                <span key={c}>{i > 0 && ", "}{label(c)}</span>)) : "geen"}</Regel>
              <Regel naam="Sjablonen">{sjablonen.length ? sjablonen.map(label).join(", ") : "geen: antwoordt in vrije tekst"}</Regel>
              {o.uitvoer && <Regel naam="Levert">{o.uitvoer}</Regel>}
              {o.twijfel && <Regel naam="Bij twijfel">{o.twijfel}</Regel>}
            </Regels>
          </Kaart>
          <LangeTekst titel="Opdracht" toelichting="Bovenop de identiteit van Lex en de methodetekst van zijn rol." data-blok="opdracht">
            {tekst(o.inhoud.systeemtekst)}
          </LangeTekst>
          <HerkomstKaart o={o} />
        </div>
      )}
    </AanpassingDetail>
  );
}

/** Een onderdeel in een andere tab van het venster: een tabwissel met het onderdeel open, geen navigatie. */
function NaarTab({ tab, id, children }: { tab: "methodes" | "agents"; id: string; children: React.ReactNode }) {
  return (
    <button type="button" onClick={() => kiesInstellingenTab(tab, { onderdeel: id })}
      className="focus-ring rounded text-lint hover:underline">{children}</button>
  );
}
