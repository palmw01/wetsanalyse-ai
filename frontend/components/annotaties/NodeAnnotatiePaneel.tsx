"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { Melding } from "@/components/ui/Melding";
import { Skeleton } from "@/components/ui/Skeleton";
import { ArtefactInhoud } from "@/components/werkplek/ArtefactInhoud";
import { foutTekst, type ExportFormaat } from "@/lib/api";
import {
  haalNodeWeergave, nodeError, nodeLink, nodeRequest, verwachteRevisies,
  type NodeDoel, type NodeElement, type NodeWeergave,
} from "@/lib/annotatieNode";
import {
  beslissingNaarNode, documentVanNode, nodeAnkersUitSelectie, nodeBronVan, tekstVanAnkers,
} from "@/lib/annotatieNodeAdapter";
import type { Anker, BeslissingInvoer } from "@/lib/types";

/** Een annotatie op een bronnode (contract 2), in het vertrouwde annotatiepaneel.
 *
 *  Dit component bezit alleen de v2-kant: de weergave ophalen, de handelingen naar
 *  `/api/annotatie/v2/**` sturen en daarna opnieuw laden. Wat je ziet – wettekst, reviewkaarten,
 *  selectiepopover, sneltoetsen, export en afronden – is `ArtefactInhoud`, dezelfde inhoud als bij
 *  een artikeldocument. De vertaling tussen beide staat in `lib/annotatieNodeAdapter.ts`.
 *
 *  Met `onSluit` staat hij in dezelfde `Dialog`-schil als `ArtefactPaneel` (werkplek); zonder is
 *  het de kale inhoud voor een eigen pagina. */
export function NodeAnnotatiePaneel({ doel, onSluit, variant = "side", onVraag }: {
  doel: NodeDoel; onSluit?: () => void; variant?: DialogVariant;
  onVraag?: (element: NodeElement, view: NodeWeergave) => void;
}) {
  const [view, setView] = useState<NodeWeergave>();
  const [laadFout, setLaadFout] = useState("");
  const [actiefId, setActiefId] = useState<string>();
  const [melding, setMelding] = useState("");

  const laad = useCallback(async () => {
    setLaadFout("");
    try { setView(await haalNodeWeergave(doel)); }
    catch (e) { setLaadFout(foutTekst(e, "De annotatie is niet geladen.")); }
  }, [doel]);
  useEffect(() => {
    // Een externe API-request initialiseren; dezelfde laadactie dient ook de retryknop.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);

  const nb = useMemo(() => (view ? nodeBronVan(view) : undefined), [view]);
  const doc = useMemo(() => (view && nb ? documentVanNode(view, nb) : undefined), [view, nb]);

  /** Elke mutatie: versturen, daarna altijd opnieuw laden – ook na een fout, want een 412 betekent
   *  juist dat de stand in beeld niet meer klopt. De fout gaat dóór naar `ArtefactInhoud`, die hem
   *  bij de kaart toont. */
  async function muteer(pad: string, body: unknown, method = "POST") {
    try {
      return await nodeRequest<Record<string, unknown>>(pad, body, method);
    } finally {
      await laad();
    }
  }

  async function beslissing(elementId: string, req: BeslissingInvoer) {
    if (!view || !nb || !doc) return;
    const huidig = doc.elementen.find((e) => e.id === elementId);
    await muteer(`elementen/${encodeURIComponent(elementId)}/beslissing`, {
      ...beslissingNaarNode(req, nb, huidig),
      snapshot_id: view.snapshot_id, verwachte_revisies: verwachteRevisies(view),
    });
    setMelding("Wijziging opgeslagen.");
  }

  async function eigenMarkering(invoer: { klasse: string; toelichting: string; anker: Anker }) {
    if (!view || !nb) return;
    const ankers = nodeAnkersUitSelectie(nb, invoer.anker.start, invoer.anker.eind);
    if (!ankers.length) throw new Error("Deze selectie bevat geen wettekst om te markeren.");
    const uit = await muteer("elementen", {
      doel: { bron_iri: view.doel.bron_iri }, snapshot_id: view.snapshot_id,
      verwachte_revisies: verwachteRevisies(view),
      element: { klasse: invoer.klasse, toelichting: invoer.toelichting, tekst: tekstVanAnkers(ankers), ankers },
    });
    const nieuw = (uit?.element as { id?: string } | undefined)?.id;
    if (nieuw) setActiefId(nieuw);
    setMelding(`Gemarkeerd als ${invoer.klasse}.`);
  }

  async function wisEigenMarkering(elementId: string) {
    if (!view) return;
    const el = view.elementen.find((e) => e.id === elementId);
    const revisie = view.lagen.find((l) => l.bron_iri === el?.eigenaar_iri)?.revisie ?? 0;
    await muteer(`elementen/${encodeURIComponent(elementId)}?verwachte_revisie=${revisie}`, {}, "DELETE");
    setActiefId((huidig) => (huidig === elementId ? undefined : huidig));
    setMelding("Markering gewist.");
  }

  /** Afronden geldt voor de bepaling in beeld, dus voor elke laag daarin. Eén voor één: de api
   *  toetst per laag of alles beoordeeld is, en een weigering noemt dan de laag waar het zit. */
  async function status(nieuw: "geaccordeerd" | "in_review") {
    if (!view) return;
    try {
      for (const laag of view.lagen.filter((l) => l.status !== nieuw)) {
        await nodeRequest(`lagen/${encodeURIComponent(laag.id)}/status`, { status: nieuw, verwachte_revisie: laag.revisie });
      }
    } finally {
      await laad();
    }
    setMelding(nieuw === "geaccordeerd" ? "Annotatie afgerond." : "Annotatie heropend.");
  }

  /** De bepaling in beeld, met alles eronder: één handeling, één transactie in de api. Daarna
   *  opnieuw laden – het paneel toont dan dat de annotatie verwijderd is, en een 412 (iemand wijzigde
   *  intussen iets) laat de actuele stand zien in plaats van blind te verwijderen. */
  async function verwijder() {
    if (!view) return;
    const uit = await muteer("weergave/verwijder", {
      bron_iri: view.doel.bron_iri, snapshot_id: view.snapshot_id, verwachte_revisies: verwachteRevisies(view),
    }) as { graaf?: string } | undefined;
    setActiefId(undefined);
    setMelding(uit?.graaf === "volgt"
      ? "Annotatie verwijderd. De kennisgraaf volgt binnen een minuut."
      : "Annotatie verwijderd.");
  }

  async function exporteer(formaat: ExportFormaat) {
    if (!view) return;
    const response = await fetch("/api/annotatie/v2/weergave/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bron_iri: view.doel.bron_iri, snapshot_id: view.snapshot_id, formaat }),
    });
    if (!response.ok) throw await nodeError(response);
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `annotatie.${formaat}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const inhoud = !view || !nb || !doc ? (
    <LaadStand fout={laadFout} onOpnieuw={() => void laad()} onSluit={onSluit} />
  ) : (
    <>
      <p className="sr-only" aria-live="polite">{melding}</p>
      <ArtefactInhoud
        doc={doc}
        info={nb.info}
        actiefId={actiefId}
        onKies={(id) => setActiefId((huidig) => (id && id === huidig ? undefined : id))}
        onBeslissing={beslissing}
        onEigenMarkering={eigenMarkering}
        onWisEigenMarkering={wisEigenMarkering}
        onVraag={onVraag ? (el) => {
          const node = view.elementen.find((e) => e.id === el.id);
          if (node) onVraag(node, view);
        } : undefined}
        onStatus={view.lagen.length ? status : undefined}
        onVerwijder={view.lagen.length ? verwijder : undefined}
        onSluiten={onSluit}
        onExport={exporteer}
        extra={<NodeExtra view={view} doel={doel} />}
      />
    </>
  );

  if (!onSluit) return inhoud;
  // `onEscape` is een no-op om dezelfde reden als in `ArtefactPaneel`: de inhoud pelt Escape zelf
  // laag voor laag af.
  return (
    <Dialog label={`Annotatie: ${view?.doel.label || doel.label || "bepaling"}`} variant={variant}
      onSluit={onSluit} onEscape={view ? () => {} : undefined}>
      {inhoud}
    </Dialog>
  );
}

/** Wat alleen een bronnode-annotatie kent: een gewijzigde bronstand, markeringen die over deze
 *  bepaling heen lopen, en de voortgang per laag als de bepaling er meer dan één draagt. */
function NodeExtra({ view, doel }: { view: NodeWeergave; doel: NodeDoel }) {
  const labelVan = (iri: string) => view.segmenten.find((s) => s.bron_iri === iri)?.label || view.doel.label || iri;
  return (
    <>
      {view.verwijderd && (
        <Melding type="uitleg" compact>
          Deze annotatie is verwijderd op {new Date(view.verwijderd.op).toLocaleString("nl-NL", {
            dateStyle: "long", timeStyle: "short" })}. Vraag Lex om de bepaling opnieuw te annoteren, of markeer zelf.
        </Melding>
      )}
      {doel.snapshot_id && doel.snapshot_id !== view.snapshot_id && (
        <Melding type="uitleg" compact>
          De wettekst is gewijzigd sinds deze annotatie werd gemaakt. Je ziet de huidige versie;
          markeringen bij de oude tekst staan onder Historie.
        </Melding>
      )}
      {view.verwijzingen.length > 0 && (
        <section className="rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm">
          <h3 className="text-xs font-medium text-muted">Overspant meerdere bepalingen ({view.verwijzingen.length})</h3>
          <p className="mt-1 text-xs text-faint">
            Deze markeringen raken deze bepaling, maar horen bij een ruimere selectie. Je beoordeelt ze daar.
          </p>
          <ul className="mt-2 space-y-1">
            {view.verwijzingen.map((r) => (
              <li key={r.id} className="text-xs">
                <Link href={nodeLink({ bron_iri: r.eigenaar_iri })} className="focus-ring rounded font-medium text-lint underline underline-offset-2 hover:no-underline">
                  {r.klasse}
                </Link>
                <span className="text-muted"> · {labelVan(r.eigenaar_iri)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {view.lagen.length > 1 && (
        <section className="rounded-kaart border border-line bg-surface/60 px-3 py-2 text-sm">
          <h3 className="text-xs font-medium text-muted">Voortgang per bepaling</h3>
          <ul className="mt-2 space-y-1">
            {view.lagen.map((l) => (
              <li key={l.id} className="flex items-baseline justify-between gap-3 text-xs">
                <span className="min-w-0 truncate text-ink">{labelVan(l.bron_iri)}</span>
                <span className="shrink-0 text-muted">{l.status === "geaccordeerd" ? "Afgerond" : "In review"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

/** Laden of niet geladen – met het kruisje op dezelfde plek als in het geladen paneel, anders zit je
 *  op een smal scherm vast achter een paneel dat niet opent. */
function LaadStand({ fout, onOpnieuw, onSluit }: { fout: string; onOpnieuw: () => void; onSluit?: () => void }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-start gap-3 border-b border-line px-5 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
        <p className="min-w-0 flex-1 truncate text-[0.65rem] font-semibold uppercase tracking-wide text-faint">Annotatie · JAS</p>
        {onSluit && (
          <button type="button" onClick={onSluit} aria-label="Sluiten"
            className="focus-ring -mr-1 shrink-0 rounded-kaart p-1.5 text-muted transition-colors hover:bg-surface hover:text-ink">
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>
      <div className="space-y-3 p-5">
        {fout ? (
          <Melding type="fout" titel="Niet geladen">
            {fout}{" "}
            <button type="button" onClick={onOpnieuw} className="underline">Opnieuw proberen</button>
          </Melding>
        ) : (
          <>
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-4 w-40" />
          </>
        )}
      </div>
    </div>
  );
}
