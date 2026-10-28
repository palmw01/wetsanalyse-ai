"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { KnoopFeiten } from "@/components/graaf/KnoopFeiten";
import { KnoopTekst } from "@/components/graaf/KnoopTekst";
import { Regel, Regels, StatusLabel } from "@/components/ui/Lijst";
import { Melding } from "@/components/ui/Melding";
import { Kaart, ObjectRij, ObjectRijen, PaginaKop, SplitDetail, Stip, type Kruimel } from "@/components/ui/Pagina";
import { Skeleton } from "@/components/ui/Skeleton";
import { OpnemenInWerkgebied } from "@/components/werkgebieden/OpnemenInWerkgebied";
import { WerkgebiedSchil } from "@/components/werkgebieden/WerkgebiedSchil";
import { VraagLexKnop } from "@/components/werkplek/VraagLexKnop";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import { haalNodeWeergave, nodeLink, type NodeWeergave } from "@/lib/annotatieNode";
import { foutTekst, haalWerkgebied, lijstWerkgebieden } from "@/lib/api";
import { haalKnoopInfo, type KnoopInfo } from "@/lib/graaf/knoopinfo";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Lifecycle, Werkgebied, WerkgebiedSamenvatting } from "@/lib/types";
import { ROL_LABEL } from "@/lib/werkgebied";
import { elementPad, projectPad } from "@/lib/werkgebiedPaden";

/** Eén bepaling op een eigen pagina (spoor G3, mock-up v4 `sourcePage`): de letterlijke wettekst met alle
 *  JAS-markeringen erin (een klik opent het element), de elementen als rijen, wat de kennisgraaf over de
 *  bepaling weet, en in welke werkgebieden ze staat. Met `?werkgebied=` is dat werkgebied de context: het
 *  kruimelpad en *Bespreek met Lex* gaan erover. */
export function BronPagina({ bronIri, werkgebiedId }: { bronIri: string; werkgebiedId?: string }) {
  const router = useRouter();
  const [view, setView] = useState<NodeWeergave | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [info, setInfo] = useState<KnoopInfo | "laden" | "fout">("laden");
  const [werkgebieden, setWerkgebieden] = useState<WerkgebiedSamenvatting[] | null>(null);
  const [wg, setWg] = useState<Werkgebied | null>(null);

  useEffect(() => {
    let levend = true;
    haalNodeWeergave({ bron_iri: bronIri })
      .then((v) => levend && setView(v))
      .catch((e) => levend && setFout(foutTekst(e, "De bepaling kon niet worden geladen.")));
    haalKnoopInfo(bronIri).then((i) => levend && setInfo(i)).catch(() => levend && setInfo("fout"));
    lijstWerkgebieden({ bronIri }).then((w) => levend && setWerkgebieden(w)).catch(() => levend && setWerkgebieden(null));
    if (werkgebiedId) haalWerkgebied(werkgebiedId).then((w) => levend && setWg(w)).catch(() => {});
    return () => { levend = false; };
  }, [bronIri, werkgebiedId]);

  const doel = view?.segmenten.find((s) => s.bron_iri === bronIri);
  const naam = view?.doel.label || doel?.label || "Bepaling";
  const actueel = (view?.elementen ?? []).filter((e) => !e.verouderd && e.lifecycle !== "rejected");
  const beoordeeld = actueel.filter((e) => ["human_approved", "edited", "published"].includes(e.lifecycle)).length;
  const afgerond = !!view?.lagen.length && view.lagen.every((l) => l.status === "geaccordeerd");
  const selectie = wg?.bronnen.find((b) => b.bron_iri === bronIri);
  const kruimels: Kruimel[] = wg
    ? [{ label: "Werkgebieden", href: "/werkgebieden" }, { label: wg.naam, href: projectPad(wg.id) },
        { label: "Bronnen", href: projectPad(wg.id, "bronnen") }, { label: naam }]
    : [{ label: "Annotaties", href: "/annotaties" }, { label: naam }];

  return (
    <WerkgebiedSchil titel={naam} onFout={setFout}>
      {!view ? (
        fout ? <Melding type="fout">{fout}</Melding> : (
          <div className="space-y-3"><Skeleton className="h-6 w-64" /><Skeleton className="h-3 w-96 max-w-full" /></div>
        )
      ) : (
        <div data-bron-pagina={bronIri}>
          <PaginaKop
            kruimels={kruimels}
            titel={naam}
            sub="De bepaling zoals ze in de kennisgraaf staat, met haar annotaties en waar ze gebruikt wordt."
            meta={<>
              {view.doel.bwb_id && <span>{view.doel.bwb_id}</span>}
              {selectie && <><Stip /><StatusLabel>{ROL_LABEL[selectie.rol]}</StatusLabel></>}
              <Stip />
              <StatusLabel toon={afgerond ? "groen" : beoordeeld < actueel.length ? "geel" : "neutraal"}>
                {actueel.length ? `${beoordeeld} van ${actueel.length} elementen beoordeeld` : "Nog niet geannoteerd"}
              </StatusLabel>
            </>}
            acties={<>
              <OpnemenInWerkgebied bronIri={bronIri} />
              {wg && selectie && (
                <VraagLexKnop primair onderwerp={{ soort: "bron", werkgebied_id: wg.id, id: selectie.id, label: naam }}
                  naam={`Bespreek ${naam} met Lex`} />
              )}
            </>}
          />
          <SplitDetail
            hoofd={<>
              <Kaart titel="Wettekst" toelichting="Letterlijk uit de BWB-graaf. De markeringen hebben de kleur van hun JAS-klasse; een klik opent het element.">
                <KnoopTekst groot segmenten={view.segmenten} elementen={actueel} kiesbaar={() => true}
                  onKies={(id) => router.push(elementPad(id))} />
              </Kaart>
              <Kaart titel="JAS-elementen" telling={actueel.length}
                meer={{ href: nodeLink({ bron_iri: bronIri }), label: "Beoordelen in de annotatie" }}>
                <ObjectRijen label="JAS-elementen" leeg="Deze bepaling is nog niet geannoteerd. Vraag Lex in het gesprek om haar te annoteren.">
                  {actueel.map((e) => (
                    <ObjectRij key={e.id} href={elementPad(e.id)} data-element-rij={e.id}
                      titel={<>“{e.tekst}”</>}
                      sub={<span className={`inline-block rounded border px-1.5 text-[0.7rem] ${jasStyle(e.klasse)}`}>{klasseLabel(e.klasse)}</span>}
                      status={<StatusLabel toon={e.lifecycle === "human_approved" ? "groen" : "neutraal"}>
                        {LIFECYCLE_LABEL[e.lifecycle as Lifecycle] ?? e.lifecycle}
                      </StatusLabel>} />
                  ))}
                </ObjectRijen>
              </Kaart>
              {/* `KnoopFeiten` draagt zijn eigen kop "Uit de kennisgraaf". */}
              <Kaart>
                <KnoopFeiten info={info} opKaart={() => false} onKies={() => {}} />
              </Kaart>
            </>}
            zij={<>
              <Kaart titel="Werkgebieden" telling={werkgebieden?.length}
                toelichting="Waar deze bepaling, of het artikel erboven, is opgenomen.">
                {werkgebieden === null ? <p className="text-sm text-muted">Niet geladen.</p> : (
                  <ObjectRijen label="Werkgebieden" leeg="Nog in geen werkgebied opgenomen.">
                    {werkgebieden.map((w) => (
                      <ObjectRij key={w.id} href={projectPad(w.id)} titel={w.naam} sub={w.analysevraag || undefined} />
                    ))}
                  </ObjectRijen>
                )}
              </Kaart>
              <Kaart titel="Herleidbaarheid">
                <Regels className="text-xs">
                  <Regel naam="Bron-IRI"><span className="break-all font-mono">{bronIri}</span></Regel>
                  <Regel naam="Bronstand"><span className="break-all font-mono">{view.snapshot_id.slice(0, 16)}</span></Regel>
                </Regels>
                <Link href={nodeLink({ bron_iri: bronIri })} className="focus-ring mt-2 inline-block rounded text-sm font-medium text-lint hover:underline">
                  Naar de annotatie
                </Link>
              </Kaart>
            </>}
          />
        </div>
      )}
    </WerkgebiedSchil>
  );
}
