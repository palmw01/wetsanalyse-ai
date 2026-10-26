"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart, PaginaKop, SplitDetail, Stip } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { KnoopTekst } from "@/components/graaf/KnoopTekst";
import { WaaromUitklap } from "@/components/annotaties/WaaromUitklap";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { beslisElement, haalElementDetail, nodeLink, type ElementDetail } from "@/lib/annotatieNode";
import { foutTekst } from "@/lib/api";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Lifecycle, ReviewReason } from "@/lib/types";
import { metSpoor } from "@/lib/uiSpoor";
import { bronPad } from "@/lib/werkgebiedPaden";

const REDENEN: { waarde: ReviewReason; label: string }[] = [
  { waarde: "verkeerde_klasse", label: "verkeerde klasse" },
  { waarde: "bron_gemist", label: "bron gemist" },
  { waarde: "tekst", label: "tekst onjuist" },
  { waarde: "interpretatie", label: "interpretatie" },
  { waarde: "onvoldoende_context", label: "onvoldoende context" },
  { waarde: "anders", label: "anders" },
];

const AANDACHT: Record<string, { label: string; toon: "groen" | "geel" }> = {
  groen: { label: "Bevestigd door review", toon: "groen" },
  geel: { label: "Keuze voor jou", toon: "geel" },
};

const BESLISSING: Record<string, string> = {
  approve: "akkoord", reject: "verworpen", heropen: "heropend", edit: "aangepast", comment: "opmerking", grens: "andere grens",
};

function kort(tekst: string, max = 60): string {
  const t = tekst.trim();
  return t.length <= max ? t : `${t.slice(0, max).replace(/\s+\S*$/, "")}…`;
}

/** Eén JAS-element op een eigen pagina (spoor G3, mock-up v4 `annotationPage`): het bronvoorkomen in de
 *  letterlijke wettekst, de classificatie met haar herkomst, en de beoordeling – accorderen, afwijzen met
 *  een reden, of heropenen. Klasse en grens aanpassen blijft in de annotatie van de bepaling, waar de
 *  andere markeringen ernaast staan. */
export function ElementPagina({ id }: { id: string }) {
  const [d, setD] = useState<ElementDetail | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [melding, setMelding] = useState<string | null>(null);
  const [afwijzen, setAfwijzen] = useState(false);
  const [bezig, setBezig] = useState(false);

  const laad = useCallback(async () => {
    try {
      setD(await haalElementDetail(id));
      setFout(null);
    } catch (e) {
      setFout(foutTekst(e, "Dit element kon niet worden geladen."));
    }
  }, [id]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  async function beslis(type: "approve" | "reject" | "heropen", review_reason?: ReviewReason) {
    if (!d || bezig) return;
    setBezig(true);
    setMelding(null);
    try {
      await metSpoor("review_beslissing", () => beslisElement(d, { type, ...(review_reason ? { review_reason } : {}) }));
      setAfwijzen(false);
      setMelding(type === "approve" ? "Akkoord vastgelegd." : type === "reject" ? "Verworpen." : "Heropend: het element staat weer ter beoordeling.");
      await laad();
    } catch (e) {
      setFout(foutTekst(e));
    } finally {
      setBezig(false);
    }
  }

  const el = d?.element;
  const bepaling = d?.bronnen.find((b) => b.bron_iri === el?.eigenaar_iri);
  const bepalingNaam = bepaling?.label || "Bepaling";
  const naarAnnotatie = el ? `${nodeLink({ bron_iri: el.eigenaar_iri })}&element=${encodeURIComponent(el.id)}` : "/annotaties";
  const afgerond = d?.laag.status === "geaccordeerd";
  const beoordeeld = !!el && ["human_approved", "rejected", "published"].includes(el.lifecycle);
  const aandacht = el?.aandacht ? AANDACHT[el.aandacht] : undefined;

  return (
    <WerkgebiedSchil titel={el ? klasseLabel(el.klasse) : "JAS-element"} onFout={setFout}>
      {!d ? (
        fout ? <Melding type="fout">{fout}</Melding> : (
          <div className="space-y-3"><Skeleton className="h-6 w-64" /><Skeleton className="h-3 w-96 max-w-full" /></div>
        )
      ) : el && (
        <div data-element-pagina={el.id} data-lifecycle={el.lifecycle}>
          <PaginaKop
            kruimels={[{ label: "Annotaties", href: "/annotaties" }, { label: bepalingNaam, href: naarAnnotatie }, { label: klasseLabel(el.klasse) }]}
            titel={<>{klasseLabel(el.klasse)} · “{kort(el.tekst)}”</>}
            sub="Bronvoorkomen, classificatie en beoordeling van één JAS-element."
            meta={<>
              <StatusLabel toon={el.lifecycle === "human_approved" ? "groen" : "neutraal"}>
                {LIFECYCLE_LABEL[el.lifecycle as Lifecycle] ?? el.lifecycle}
              </StatusLabel>
              {aandacht && <StatusLabel toon={aandacht.toon} uitleg={el.review_uitleg || undefined}>{aandacht.label}</StatusLabel>}
              <Stip /><span>{bepalingNaam}</span>
            </>}
            acties={<Link href={naarAnnotatie}
              className="focus-ring inline-flex min-h-[32px] items-center rounded-button border border-lint px-3 text-sm font-medium text-lint hover:bg-surface coarse:min-h-[44px]">
              Naar de bepaling
            </Link>}
          />
          {fout && <Melding type="fout" className="mb-4">{fout}</Melding>}
          {melding && <Melding type="bevestiging" compact className="mb-4">{melding}</Melding>}
          <SplitDetail
            hoofd={<>
              <Kaart titel="Bronvoorkomen" toelichting="De letterlijke wettekst, met dit element gemarkeerd.">
                {el.verouderd && (
                  <Melding type="waarschuwing" compact className="mb-3">
                    De wettekst is veranderd sinds dit element is gemaakt. Het blijft staan als historie en is alleen-lezen.
                  </Melding>
                )}
                <KnoopTekst groot segmenten={d.bronnen} elementen={[el]} kiesbaar={() => false} onKies={() => {}} />
              </Kaart>
              <Kaart titel="Classificatie">
                <Regels className="text-sm">
                  <Regel naam="JAS-klasse">
                    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${jasStyle(el.klasse)}`}>{klasseLabel(el.klasse)}</span>
                  </Regel>
                  {el.jas_subtype && <Regel naam="Subtype">{el.jas_subtype}</Regel>}
                  <Regel naam="Fragment">“{el.tekst}”</Regel>
                  <Regel naam="Toelichting">{el.toelichting?.trim() || <span className="text-muted">Geen toelichting.</span>}</Regel>
                  {el.review_uitleg && <Regel naam="Review">{el.review_uitleg}</Regel>}
                  {!!el.alternatieven?.length && (
                    <Regel naam="Alternatieven">{el.alternatieven.map((a) => a.klasse).join(", ")}</Regel>
                  )}
                </Regels>
                <div className="mt-3"><WaaromUitklap el={el} /></div>
              </Kaart>
              <Kaart titel="Beoordeling" toelichting="Een geaccordeerde annotatie keurt een begrip dat erop rust niet automatisch goed.">
                {el.verouderd ? (
                  <p className="text-sm text-muted">Alleen-lezen: de wettekst veranderde.</p>
                ) : afgerond ? (
                  <p className="text-sm text-muted">De annotatie van deze bepaling is afgerond. Heropen haar in de annotatie om te wijzigen.</p>
                ) : beoordeeld ? (
                  <Button size="sm" variant="secondary" disabled={bezig} onClick={() => void beslis("heropen")}>Opnieuw ter beoordeling</Button>
                ) : (
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button size="sm" disabled={bezig} onClick={() => void beslis("approve")}>Accorderen</Button>
                    <Button size="sm" variant="danger" disabled={bezig} aria-expanded={afwijzen} onClick={() => setAfwijzen((v) => !v)}>Afwijzen…</Button>
                  </div>
                )}
                {afwijzen && (
                  <div className="mt-3" role="group" aria-label="Reden van afwijzen">
                    <p className="mb-1.5 text-xs text-muted">Waarom klopt dit element niet?</p>
                    <div className="flex flex-wrap gap-1.5">
                      {REDENEN.map((r) => (
                        <button key={r.waarde} type="button" disabled={bezig} onClick={() => void beslis("reject", r.waarde)}
                          className="focus-ring min-h-[32px] rounded-full border border-line px-3 text-xs font-medium text-ink hover:border-fout hover:text-fout">
                          {r.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {!!el.beslissingen?.length && (
                  <ol className="mt-4 divide-y divide-line border-t border-line text-xs" aria-label="Beslissingen">
                    {el.beslissingen.map((b, i) => (
                      <li key={i} className="py-1.5 text-muted">
                        <span className="text-ink">{BESLISSING[b.type] ?? b.type}</span> door {b.actor} · {new Date(b.tijd).toLocaleString("nl-NL")}
                        {b.review_reason && ` · ${REDENEN.find((r) => r.waarde === b.review_reason)?.label ?? b.review_reason}`}
                        {b.comment && ` · ${b.comment}`}
                      </li>
                    ))}
                  </ol>
                )}
              </Kaart>
            </>}
            zij={<>
              <Kaart titel="Relaties">
                <ul className="space-y-1 text-sm">
                  <li><Link href={naarAnnotatie} className="focus-ring block rounded-md px-2 py-1.5 hover:bg-surface">
                    <span className="block font-medium text-lint">JAS-analyse van {bepalingNaam}</span>
                    <span className="block text-xs text-muted">Alle markeringen van de bepaling, met klasse en grens aanpassen</span>
                  </Link></li>
                  <li><Link href={bronPad(el.eigenaar_iri)} className="focus-ring block rounded-md px-2 py-1.5 hover:bg-surface">
                    <span className="block font-medium text-lint">{bepalingNaam}</span>
                    <span className="block text-xs text-muted">De bepaling, met wat de kennisgraaf erover weet</span>
                  </Link></li>
                </ul>
              </Kaart>
              <Kaart titel="Herleidbaarheid">
                <Regels className="text-xs">
                  <Regel naam="Laag">revisie {d.laag.revisie}{afgerond ? " · afgerond" : ""}</Regel>
                  <Regel naam="Bronstand"><span className="break-all font-mono">{d.snapshot_id.slice(0, 16)}</span></Regel>
                  <Regel naam="Herkomst">{el.herkomst === "mens" ? `door ${el.aangemaakt_door ?? "een jurist"} gemarkeerd` : "voorstel van Lex"}</Regel>
                </Regels>
              </Kaart>
              <Melding type="uitleg" compact>
                Advies van Lex over deze markering vraag je met Vraag Lex op de markering in de annotatie van de bepaling.
              </Melding>
            </>}
          />
        </div>
      )}
    </WerkgebiedSchil>
  );
}
