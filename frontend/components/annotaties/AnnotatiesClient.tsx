"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AnnotatieKaart } from "@/components/annotaties/AnnotatieKaart";
import { AppSidebar } from "@/components/werkplek/AppSidebar";
import { MobieleTopbar } from "@/components/werkplek/MobieleTopbar";
import { Melding } from "@/components/ui/Melding";
import { OverzichtBalk } from "@/components/ui/OverzichtBalk";
import { Skeleton } from "@/components/ui/Skeleton";
import { SkipLink, HOOFDINHOUD_ID } from "@/components/ui/SkipLink";
import { foutTekst, isApiError, lijstLagen } from "@/lib/api";
import { verwijderAnnotatie } from "@/lib/annotatieNode";
import { metSpoor } from "@/lib/uiSpoor";
import {
  WEERGAVEN, groepeerPerRegeling, inWeergave, legeWeergave, sorteerTeBeoordelen, uitlegWeergave, zoek,
  type Weergave,
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

  /** Verwijderen vanuit de lijst: de kaart gaat meteen weg en komt bij een fout terug. */
  async function verwijder(doc: DocumentSamenvatting) {
    const voor = docs;
    setDocs((d) => d?.filter((x) => x.slug !== doc.slug) ?? d);
    try {
      await metSpoor("annotatie_verwijderen", () =>
        verwijderAnnotatie({ bron_iri: doc.bron_iri ?? "", snapshot_id: doc.snapshot_id }));
    } catch (e) {
      setDocs(voor);
      setFout(foutTekst(e, "De annotatie is niet verwijderd."));
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

            {docs === null ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="space-y-3 rounded-kaart border border-line bg-paper shadow-zacht p-4">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-1.5 w-full" />
                    <Skeleton className="h-3 w-64" />
                  </div>
                ))}
              </div>
            ) : alles.length === 0 ? (
              <p className="text-sm text-muted">
                Nog geen annotaties. Vraag Lex in de werkplek om een artikel te annoteren.
              </p>
            ) : getoond.length === 0 ? (
              <p className="rounded-kaart border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
                {term.trim() ? "Geen annotatie die hierop past." : legeWeergave(weergave)}
              </p>
            ) : weergave === "te-beoordelen" ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {sorteerTeBeoordelen(getoond).map((d) => (
                  <AnnotatieKaart key={d.slug} doc={d} onVerwijder={() => verwijder(d)} />
                ))}
              </div>
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
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {regeling.documenten.map((d) => (
                        <AnnotatieKaart key={d.slug} doc={d} onVerwijder={() => verwijder(d)} />
                      ))}
                    </div>
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
