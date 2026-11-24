"use client";

import { OverzichtRaster, OverzichtSkelet } from "@/components/ui/Pagina";
import { Leeg } from "@/components/ui/Leeg";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AnnotatieKaart } from "@/components/annotaties/AnnotatieKaart";
import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { Melding, MeldingActie } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { SkipLink, HOOFDINHOUD_ID } from "@/components/ui/SkipLink";
import { foutTekst, isApiError, lijstLagen } from "@/lib/api";
import { apiOpslag, verwijderAnnotatie } from "@/lib/annotatieNode";
import { VerwijderBevestiging } from "@/components/annotaties/Prullenbak";
import { metSpoor } from "@/lib/uiSpoor";
import {
  WEERGAVEN, groepeerPerRegeling, inWeergave, legeWeergave, sorteerTeBeoordelen, uitlegWeergave, zoek,
  type Weergave, naamVan,
} from "@/lib/annotatieOverzicht";
import type { DocumentSamenvatting } from "@/lib/types";

/** Het annotatie-overzicht: de annotaties los van de gesprekken waarin ze zijn gemaakt.
 *
 *  Dat zijn de GEDEELDE lagen: één laag per bronnode voor iedereen, zodat Lex een bepaling die al
 *  geannoteerd is niet opnieuw hoeft te doen. "Door mij bewerkt" beperkt de lijst
 *  tot de lagen waar je zelf iets aan deed – een laag heeft geen eigenaar, dus dat staat in de audit.
 *
 *  Vier weergaven op één lijst, langs de weg van een annotatie. *Te beoordelen* is werkvoorraad, rood
 *  eerst. *Af te ronden*, *Afgerond* en *Alles* staan per regeling, want juristen zoeken in wetten en
 *  niet in documenten-op-datum. De stand staat in de URL zodat terugbladeren en delen werken. */
export function AnnotatiesClient({ beginWeergave }: { beginWeergave: Weergave }) {
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentSamenvatting[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [weergave, setWeergave] = useState<Weergave>(beginWeergave);
  const [term, setTerm] = useState("");
  const [alleenMijn, setAlleenMijn] = useState(false);
  // Onder `lg` is de sidebar een drawer. Zonder deze state was er op een smal scherm géén sidebar
  // én geen manier om er een te openen: geen gesprekken, geen account, geen uitloggen.
  const [drawerOpen, setDrawerOpen] = useState(false);
  // De bevestiging (welke kaart), en na verwijderen de weg terug.
  const [teVerwijderen, setTeVerwijderen] = useState<DocumentSamenvatting | null>(null);
  const [verwijderd, setVerwijderd] = useState<{ id: string; naam: string } | null>(null);
  const [teruggezet, setTeruggezet] = useState("");

  const laad = useCallback(async () => {
    setFout(null);
    try {
      setDocs(await lijstLagen({ mijn: alleenMijn }));
    } catch (e) {
      setFout(isApiError(e) ? `${e.detail} (${e.status})` : (e as Error).message);
      setDocs([]);
    }
  }, [alleenMijn]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    laad();
  }, [laad]);

  /** Verwijderen vanuit de lijst, na de bevestiging die noemt wat er verloren gaat. De kaart gaat daarna weg; een fout
   *  blijft in het venster staan. Daarna kun je het in een melding terugzetten. */
  async function verwijder(doc: DocumentSamenvatting) {
    const doel = { bron_iri: doc.bron_iri ?? "", snapshot_id: doc.snapshot_id };
    const uit = await metSpoor("annotatie_verwijderen", () => verwijderAnnotatie(doel));
    setDocs((d) => d?.filter((x) => x.slug !== doc.slug) ?? d);
    setTeruggezet("");
    setVerwijderd(uit?.prullenbak ? { id: uit.prullenbak.id, naam: naamVan(doc) } : null);
  }

  async function zetTerug(item: { id: string; naam: string }) {
    setFout(null);
    try {
      await apiOpslag.terugzetten!(item.id);
      setVerwijderd(null);
      setTeruggezet(item.naam);
      await laad();
    } catch (e) {
      setFout(foutTekst(e, "De annotatie is niet teruggezet."));
    }
  }

  function kiesWeergave(nieuw: Weergave) {
    setWeergave(nieuw);
    // `replace`, niet `push`: een wissel tussen twee weergaven van dezelfde lijst is geen stap in de
    // geschiedenis – anders moet je vijf keer terug om weg te komen.
    router.replace(nieuw === "te-beoordelen" ? "/annotaties" : `/annotaties?weergave=${nieuw}`, {
      scroll: false,
    });
  }

  const alles = docs ?? [];
  const gezocht = zoek(alles, term);
  const getoond = gezocht.filter((d) => inWeergave(d, weergave));

  return (
    <div className="relative flex h-screen h-[100dvh] flex-col overflow-hidden bg-surface">
      <SkipLink />
      <div className="flex min-h-0 flex-1">
        <AppSidebar
          activeId={null}
          onNieuw={() => router.push("/workbench")}
          onOpen={(id) => router.push(`/workbench?gesprek=${encodeURIComponent(id)}`)}
          onFout={setFout}
          drawerOpen={drawerOpen}
          onDrawerSluit={() => setDrawerOpen(false)}
        />

        <div className="flex min-w-0 flex-1 flex-col">
        <MobieleTopbar titel="Annotaties" onOpenSidebar={() => setDrawerOpen(true)} />
        <main id={HOOFDINHOUD_ID} tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-5xl px-5 py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
            <header className="mb-5">
              <h1 className="font-display text-lg font-semibold text-lint">Annotaties</h1>
              <p className="mt-1 text-sm text-muted">
                De JAS-annotaties per bepaling, gedeeld met iedereen – los van het gesprek waarin
                ze zijn gemaakt.
              </p>
            </header>

            <OverzichtBalk
              filters={WEERGAVEN.map((w) => ({ ...w, aantal: alles.filter((d) => inWeergave(d, w.waarde)).length }))}
              gekozen={weergave}
              onKies={kiesWeergave}
              filterLabel="Weergave"
              mijn={alleenMijn}
              onMijn={setAlleenMijn}
              zoekterm={term}
              onZoek={setTerm}
              zoekLabel="Zoeken in annotaties"
              placeholder="Zoek op wet, artikel of lid"
            />

            {alles.length > 0 && (
              <p className="-mt-2 mb-4 text-xs text-muted">{uitlegWeergave(weergave)}</p>
            )}

            {fout && (
              <Melding type="fout" className="mb-4">
                {fout}
              </Melding>
            )}
            {verwijderd && (
              <Melding type="bevestiging" className="mb-4" data-verwijderd-melding>
                De annotatie van {verwijderd.naam} staat in de prullenbak.{" "}
                <MeldingActie onClick={() => void zetTerug(verwijderd)} data-terugzetten>Terugzetten</MeldingActie>
              </Melding>
            )}
            {teruggezet && <Melding type="bevestiging" className="mb-4">De annotatie van {teruggezet} is teruggezet.</Melding>}
            {teVerwijderen && (
              <VerwijderBevestiging bepaling={naamVan(teVerwijderen)}
                haalImpact={() => apiOpslag.verwijderImpact!({ bron_iri: teVerwijderen.bron_iri ?? "", snapshot_id: teVerwijderen.snapshot_id ?? "" })}
                onVerwijder={() => verwijder(teVerwijderen)} onSluit={() => setTeVerwijderen(null)} />
            )}

            {docs === null ? (
              <OverzichtSkelet />
            ) : alles.length === 0 ? (
              <Leeg kader>Nog geen annotaties. Vraag Lex in de werkplek om een artikel te annoteren.</Leeg>
            ) : getoond.length === 0 ? (
              <Leeg kader>
                {term.trim() ? "Geen annotatie die hierop past." : legeWeergave(weergave)}
              </Leeg>
            ) : weergave === "te-beoordelen" ? (
              <OverzichtRaster>
                {sorteerTeBeoordelen(getoond).map((d) => (
                  <AnnotatieKaart key={d.slug} doc={d} onVerwijder={() => setTeVerwijderen(d)} />
                ))}
              </OverzichtRaster>
            ) : (
              <div className="space-y-6">
                {groepeerPerRegeling(getoond).map((regeling) => (
                  <section key={regeling.bwbId}>
                    <div className="mb-3 flex items-baseline gap-3 border-b border-line pb-2">
                      <h2 className="font-display text-base font-semibold text-lint">
                        {regeling.naam}
                      </h2>
                      <span className="font-mono text-xs text-faint">
                        {regeling.documenten.length}
                      </span>
                    </div>
                    <OverzichtRaster>
                      {regeling.documenten.map((d) => (
                        <AnnotatieKaart key={d.slug} doc={d} onVerwijder={() => setTeVerwijderen(d)} />
                      ))}
                    </OverzichtRaster>
                  </section>
                ))}
              </div>
            )}
          </div>
        </main>
        </div>
      </div>
    </div>
  );
}
