"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Tag } from "@/components/ui/Badge";
import { Lijst, LijstRij, Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart, PaginaKop, SplitDetail } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { ConceptBewerken } from "@/components/werkwijze/Concepten";
import { ModelLabel } from "@/components/werkwijze/ModelLabel";
import { foutTekst, haalOnderdeel } from "@/lib/api";
import { CONCEPT_LABEL, SOORT_LABEL, onderdeelPad, soortVan, type OnderdeelDetail, type Soort } from "@/lib/catalogus";
import { werkplaatsSoortVan } from "@/lib/werkplaats";

type Rij = Record<string, unknown>;
const lijst = (x: unknown): Rij[] => (Array.isArray(x) ? (x as Rij[]) : []);
const tekst = (x: unknown): string => (typeof x === "string" ? x : Array.isArray(x) ? x.join(", ") : x == null ? "" : String(x));

/** Eén onderdeel van de werkwijze van Lex (ADR-014): het contract (ADR-010), de stappen van een workflow, de inhoud
 *  per soort, de herkomst en waar het in de repo staat. Alleen lezen. */
export function OnderdeelPagina({ soort, naam }: { soort: Soort; naam: string }) {
  const [o, setO] = useState<OnderdeelDetail | null>(null);
  const [fout, setFout] = useState<string | null>(null);

  useEffect(() => {
    let weg = false;
    haalOnderdeel(soort, naam).then((d) => { if (!weg) setO(d); })
      .catch((e) => { if (!weg) setFout(foutTekst(e, "Dit onderdeel kon niet worden geladen.")); });
    return () => { weg = true; };
  }, [soort, naam]);

  // Een methode is in de werkplaats een skill met dezelfde naam (ADR-016 §B5).
  const werkplaatsSoort = werkplaatsSoortVan(soort);
  const kruimels = [{ label: "Werkwijze van Lex", href: "/werkwijze" },
    ...(o ? [{ label: CONCEPT_LABEL[o.concept].kop, href: `/werkwijze?concept=${o.concept}` }] : []),
    { label: o?.label ?? naam }];

  return (
    <WerkgebiedSchil titel={o?.label ?? "Werkwijze van Lex"} onFout={setFout}>
      {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
      {!o ? (!fout && <div className="space-y-3"><Skeleton className="h-6 w-64" /><Skeleton className="h-40 w-full" /></div>) : (
        <>
          <PaginaKop kruimels={kruimels} titel={o.label} sub={o.doel}
            meta={<><StatusLabel toon="lint" uitleg={CONCEPT_LABEL[o.concept].uitleg} data-concept={o.concept}>
              {SOORT_LABEL[soort].een}</StatusLabel><ModelLabel model={o.model} aan={o.aan} />
              {o.laag && <span>laag: {o.laag}</span>}<span>versie <span className="font-mono">{o.versie}</span></span></>}
            acties={werkplaatsSoort ? <ConceptBewerken soort={werkplaatsSoort} naam={naam} /> : undefined} />
          <SplitDetail
            hoofd={<>
              <Contract o={o} />
              {o.stappen.length > 0 && <Stappen o={o} />}
              <Inhoud o={o} />
            </>}
            zij={<>
              <Herkomst o={o} />
              {o.deel_van && <Samenhang titel="Deel van" ids={[o.deel_van]} />}
              <Samenhang titel="Leunt op" ids={o.hangt_af_van} />
              <Samenhang titel="Gebruikt door" ids={o.gebruikt_door} />
              <InDeRepo o={o} />
            </>}
          />
        </>
      )}
    </WerkgebiedSchil>
  );
}

function Contract({ o }: { o: OnderdeelDetail }) {
  const regels: [string, string][] = ([
    ["Ingang", tekst(o.ingang)], ["Context", o.context], ["Tools", tekst(o.tools)], ["Uitvoer", o.uitvoer],
    ["Bij twijfel", o.twijfel], ["Straat", o.straat ? `${o.straat} · ${o.aan ? "hier aan" : "hier uit"}` : ""],
  ] as [string, string][]).filter(([, w]) => w);
  if (!regels.length) return null;
  return (
    <Kaart titel="Hoe het werkt" data-blok="contract">
      <Regels className="text-sm">{regels.map(([n, w]) => <Regel key={n} naam={n}>{w}</Regel>)}</Regels>
    </Kaart>
  );
}

function Stappen({ o }: { o: OnderdeelDetail }) {
  return (
    <Kaart titel="Stappen" telling={o.stappen.length} toelichting="In de volgorde waarin de keten ze uitvoert." data-blok="stappen">
      <Lijst genummerd label="Stappen">
        {o.stappen.map((s) => (
          <LijstRij key={s.naam} titel={s.onderdeel ? <Link className="focus-ring rounded hover:underline" href={onderdeelPad(s.onderdeel)}>{s.naam}</Link> : s.naam}
            status={<ModelLabel model={s.model} />} data-stap={s.naam} />
        ))}
      </Lijst>
    </Kaart>
  );
}

function Inhoud({ o }: { o: OnderdeelDetail }) {
  const i = o.inhoud;
  switch (o.soort) {
    case "methode":
      return (
        <Kaart titel="Rollen en secties" data-blok="inhoud">
          <Regels className="text-sm">{Object.entries((i.rollen as Record<string, string[]>) ?? {}).map(([rol, ids]) => (
            <Regel key={rol} naam={<Link className="focus-ring rounded hover:underline" href={onderdeelPad(`rol/${rol}`)}>{rol}</Link>}>{ids.join(", ")}</Regel>
          ))}</Regels>
        </Kaart>
      );
    case "rol":
      return (
        <Kaart titel="Methodetekst" toelichting="Deze tekst gaat letterlijk mee in de systeemprompt." data-blok="inhoud">
          <div className="space-y-4">{lijst(i.secties).map((s) => (
            <Sectie key={tekst(s.id)} s={s} />
          ))}</div>
        </Kaart>
      );
    case "agentprofiel":
      return (
        <Kaart titel="Instructie" toelichting="Bovenop de identiteit van Lex en de methodetekst van zijn rol." data-blok="inhoud">
          <p className="whitespace-pre-wrap text-sm text-ink">{tekst(i.systeemtekst)}</p>
        </Kaart>
      );
    case "agent":
      return (
        <Kaart titel="Taken" data-blok="inhoud">
          <Lijst label="Taken">{lijst(i.taken).map((t) => (
            <LijstRij key={tekst(t.taak)} titel={tekst(t.taak)} meta={tekst(t.acties) || undefined}
              status={<ModelLabel model={t.model ? "strict" : "geen"} />} />
          ))}</Lijst>
        </Kaart>
      );
    case "sjabloon":
      return (
        <Kaart titel="Velden" toelichting={tekst(i.beschrijving)} data-blok="inhoud">
          <Regels className="text-sm">{Object.entries((i.velden as Record<string, string>) ?? {}).map(([n, w]) => <Regel key={n} naam={n}>{w}</Regel>)}</Regels>
        </Kaart>
      );
    case "connector":
      return (
        <Kaart titel="Wat deze bron dekt" data-blok="inhoud">
          <Regels className="text-sm">
            {(["dekt", "rol_in_antwoord", "levert", "niet_in_tekst"] as const).filter((k) => tekst(i[k])).map((k) => (
              <Regel key={k} naam={{ dekt: "Dekt", rol_in_antwoord: "In een antwoord", levert: "Levert", niet_in_tekst: "Niet in de tekst" }[k]}>{tekst(i[k])}</Regel>
            ))}
            {lijst(i.voorbeeldvragen).length > 0 && <Regel naam="Voorbeeldvragen">
              <ul className="list-disc pl-4">{(i.voorbeeldvragen as string[]).map((v) => <li key={v}>{v}</li>)}</ul></Regel>}
          </Regels>
        </Kaart>
      );
    case "regelset":
      return <RegelsetInhoud i={i} />;
    case "tool":
      return (
        <Kaart titel="Wat de handeling doet" data-blok="inhoud">
          <p className="whitespace-pre-wrap text-sm text-ink">{tekst(i.beschrijving)}</p>
          {lijst(i.argumenten).length > 0 && <p className="mt-3 text-xs text-muted">Argumenten: {tekst(i.argumenten)}</p>}
        </Kaart>
      );
    case "route":
      return (
        <Kaart titel="Herkenning" data-blok="inhoud">
          <Regels className="text-sm">
            <Regel naam="Moment">{tekst(i.moment)}</Regel>
            <Regel naam="Herkenner"><span className="font-mono text-xs">{tekst(i.herkenner)}</span></Regel>
          </Regels>
        </Kaart>
      );
    default:
      return null;
  }
}

/** Eén methodesectie: alleen lezen. Wie de methode wil aanpassen, maakt een concept van de skill (*Bewerken* op de
 *  pagina van de methode, ADR-016 §B7); de sectie-editor van ADR-014 C7 is daarmee vervangen. */
function Sectie({ s }: { s: Rij }) {
  const id = tekst(s.id);
  return (
    <section data-sectie={id}>
      <h3 className="text-sm font-semibold text-ink">{id} <span className="font-normal text-muted">
        · uit {tekst(s.skill) || "de methode"} · bronnen {tekst(s.bronnen)}</span></h3>
      <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{tekst(s.tekst)}</p>
    </section>
  );
}

function RegelsetInhoud({ i }: { i: Record<string, unknown> }) {
  if (lijst(i.profielen).length) {
    return (
      <Kaart titel="Profielen" telling={lijst(i.profielen).length} data-blok="inhoud">
        <Lijst label="Profielen">{lijst(i.profielen).map((p) => (
          <LijstRij key={tekst(p.bestand)} titel={tekst(p.klasse)} meta={tekst(p.regels) || "geen detectorregels"} />
        ))}</Lijst>
      </Kaart>
    );
  }
  const regels = lijst(i.regels);
  if (!regels.length) {
    return (
      <Kaart titel="Inhoud" data-blok="inhoud">
        <p className="text-sm text-muted">Een lijst zonder losse regels{lijst(i.sleutels).length ? `: ${tekst(i.sleutels)}` : ""}.</p>
      </Kaart>
    );
  }
  return (
    <Kaart titel="Regels" telling={regels.length} toelichting="Elke regel draait bij elke wijziging zijn eigen voorbeeldzinnen als test." data-blok="inhoud">
      <Lijst label="Regels">{regels.map((r) => {
        const vb = (r.voorbeelden as Record<string, string[]>) ?? {};
        return (
          <LijstRij key={tekst(r.id)} titel={<span className="font-mono text-xs">{tekst(r.id)}</span>} data-regel={tekst(r.id)}
            meta={[tekst(r.klassen ?? r.hypothese ?? r.masker), r.code && `code ${tekst(r.code)}`, r.bron && `bron ${tekst(r.bron)}`,
              r.versie != null && `versie ${tekst(r.versie)}`].filter(Boolean).join(" · ")}>
            {(vb.positief?.length || vb.negatief?.length) ? (
              <ul className="mt-1 space-y-0.5 text-xs text-muted">
                {vb.positief?.map((z) => <li key={`p-${z}`}>Wel: “{z}”</li>)}
                {vb.negatief?.map((z) => <li key={`n-${z}`}>Niet: “{z}”</li>)}
              </ul>
            ) : null}
          </LijstRij>
        );
      })}</Lijst>
    </Kaart>
  );
}

function Herkomst({ o }: { o: OnderdeelDetail }) {
  return (
    <Kaart titel="Herkomst" data-blok="herkomst">
      <Regels className="text-sm">
        <Regel naam="Bron">{o.herkomst.bron}</Regel>
        <Regel naam="Licentie">{o.herkomst.licentie === "repo" ? "eigen werk, de licentie van deze repo" : o.herkomst.licentie}</Regel>
        <Regel naam="Tekst">{o.herkomst.letterlijk ? "letterlijk uit de bron, met de licentietekst erbij" : "in eigen woorden"}</Regel>
        {o.herkomst.verwijzing.length > 0 && <Regel naam="Verwijst naar">{o.herkomst.verwijzing.join(", ")}</Regel>}
      </Regels>
    </Kaart>
  );
}

function Samenhang({ titel, ids }: { titel: string; ids: string[] }) {
  if (!ids.length) return null;
  return (
    <Kaart titel={titel} telling={ids.length > 1 ? ids.length : undefined}
      data-blok={{ "Leunt op": "leunt-op", "Gebruikt door": "gebruikt-door", "Deel van": "deel-van" }[titel]}>
      <ul className="space-y-1 text-sm">{ids.map((id) => {
        const s = soortVan(id);
        return (
          <li key={id}>
            <Link className="focus-ring rounded text-lint hover:underline" href={onderdeelPad(id)}>{id.slice(id.indexOf("/") + 1)}</Link>
            {s && <span className="text-xs text-muted"> · {SOORT_LABEL[s].een.toLowerCase()}</span>}
          </li>
        );
      })}</ul>
    </Kaart>
  );
}

function InDeRepo({ o }: { o: OnderdeelDetail }) {
  return (
    <Kaart titel="In de repo" toelichting="Wijzigen gaat via een pull request; de poort draait de tests hieronder." data-blok="repo">
      <div className="space-y-3">
        <div className="flex flex-wrap gap-1.5">{o.bestand.map((b) => <Tag key={b}>{b}</Tag>)}</div>
        <div>
          <p className="mb-1 text-xs text-muted">Tests</p>
          <div className="flex flex-wrap gap-1.5">{o.tests.map((t) => <Tag key={t}>{t}</Tag>)}</div>
        </div>
      </div>
    </Kaart>
  );
}
