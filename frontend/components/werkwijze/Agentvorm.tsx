"use client";

import Link from "next/link";

import { Lijst, LijstRij, Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Kaart } from "@/components/ui/Pagina";
import { AGENTVORM_STANDEN, ingangTekst, naamVan, onderdeelPad, type Agentvorm, type Onderdeel } from "@/lib/catalogus";

/** Hoe een getypte vraag op deze omgeving binnenkomt (ADR-016): de stand van de vlag komt uit de configuratie van
 *  graph-qa, de profielen en wat altijd in code blijft uit de registers (`catalogus.agentvorm`). Alleen lezen. */
export function AgentvormBlok({ vorm, onderdelen }: { vorm: Agentvorm; onderdelen: Onderdeel[] }) {
  const label = (id: string) => onderdelen.find((o) => o.id === id)?.label ?? naamVan(id);
  const link = (id: string, tekst?: string) => (
    <Link className="focus-ring rounded text-lint hover:underline" href={onderdeelPad(id)}>{tekst ?? label(id)}</Link>
  );
  return (
    <Kaart titel="Hoe een vraag binnenkomt" data-blok="agentvorm" data-stand={vorm.stand}
      toelichting={<>Op deze omgeving staat <span className="font-mono text-xs">{vorm.vlag}</span> op <strong>{vorm.stand}</strong>.
        {" "}{ingangTekst(vorm)} leest een getypte vraag; wat hieronder <em>altijd in code</em> staat, gaat daar zonder model aan vooraf.</>}
      acties={<StatusLabel toon="lint" uitleg={vorm.standen[vorm.stand]}>{ingangTekst(vorm)}</StatusLabel>}>
      <Regels className="text-sm">
        <Regel naam="Nu">{vorm.standen[vorm.stand]} <span className="text-muted">Ingang: {link(vorm.ingang)}.</span></Regel>
        <Regel naam="Altijd in code">
          <ul className="space-y-1" data-altijd-in-code>
            {vorm.altijd_in_code.map((r) => (
              <li key={r.wat}><span className="font-medium text-ink">{r.wat}</span>
                <span className="text-muted"> ({r.aantal}) · {r.uitleg}</span></li>
            ))}
          </ul>
        </Regel>
        <Regel naam="Centrale agent">
          {link(vorm.centrale_agent)} beantwoordt een gewone vraag zelf en geeft werk door met zijn overdrachten. Werk dat op
          zichzelf staat, gaat naar {link(vorm.subagents)}; het werk per deelvraag naar {link(vorm.regie)}.
        </Regel>
        <Regel naam="Andere standen">
          <ul className="space-y-1">
            {AGENTVORM_STANDEN.filter((s) => s !== vorm.stand).map((s) => (
              <li key={s} data-stand-uitleg={s}><span className="font-mono text-xs">{s}</span>
                <span className="text-muted"> · {vorm.standen[s]}</span></li>
            ))}
          </ul>
        </Regel>
      </Regels>
      <h3 className="mb-1 mt-4 text-sm font-semibold text-ink">Agentprofielen op deze omgeving</h3>
      <Lijst label="Agentprofielen en hun plek">
        {vorm.profielen.map((p) => (
          <LijstRij key={p.id} titel={link(p.id)} meta={`${p.label} · ${p.nu}`} data-profiel={p.id}
            status={p.plek ? undefined : <StatusLabel toon="geel">zonder plek</StatusLabel>} />
        ))}
      </Lijst>
      <p className="mt-3 text-xs text-muted" data-vooruitblik>{vorm.vooruitblik}</p>
    </Kaart>
  );
}
