"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Dialog, type DialogVariant } from "@/components/ui/Dialog";
import { JAS_KLASSEN } from "@/lib/jas";
import { LIFECYCLE_LABEL } from "@/lib/annotatie";
import type { Lifecycle } from "@/lib/types";
import { NodeReviewDetails } from "./NodeReviewDetails";
import { haalNodeWeergave, nodeRequest, nodeError, nodeLink, segmentAnker, verwachteRevisies,
  elementVergrendeld, type NodeDoel, type NodeElement, type NodeAnker, type NodeWeergave } from "@/lib/annotatieNode";

export function NodeAnnotatiePaneel({ doel, onSluit, variant, onVraag }: {
  doel: NodeDoel; onSluit?: () => void; variant?: DialogVariant;
  onVraag?: (element: NodeElement, view: NodeWeergave) => void;
}) {
  const { data: sessie } = useSession();
  const [view, setView] = useState<NodeWeergave>();
  const [fout, setFout] = useState("");
  const [melding, setMelding] = useState("");
  const [bezig, setBezig] = useState(false);
  const [actief, setActief] = useState<string>();
  const [selectie, setSelectie] = useState<NodeAnker[]>([]);
  const [klasse, setKlasse] = useState("");
  const [toelichting, setToelichting] = useState("");
  const [reden, setReden] = useState("");
  const [filter, setFilter] = useState("alles");
  const tekstRef = useRef<HTMLDivElement>(null);
  const laad = useCallback(async () => {
    setFout("");
    try { setView(await haalNodeWeergave(doel)); }
    catch (e) { setFout((e as Error).message); }
  }, [doel]);
  useEffect(() => {
    // Een externe API-request initialiseren; dezelfde laadactie dient ook de retryknop.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void laad();
  }, [laad]);
  async function wijzig(path: string, body: unknown, method = "POST") {
    setBezig(true); setFout("");
    try {
      await nodeRequest(path, body, method);
      await laad(); setSelectie([]); setMelding("Wijziging opgeslagen.");
    } catch (e) { setFout((e as Error).message); }
    finally { setBezig(false); }
  }
  function selecteer() {
    const selection = window.getSelection();
    if (!view || !selection?.rangeCount || selection.isCollapsed || !tekstRef.current) return;
    const range = selection.getRangeAt(0);
    if (!tekstRef.current.contains(range.startContainer) || !tekstRef.current.contains(range.endContainer)) return;
    const ankers: NodeAnker[] = [];
    for (const root of tekstRef.current.querySelectorAll<HTMLElement>("[data-bron]")) {
      if (!range.intersectsNode(root)) continue;
      const segment = view.segmenten.find((s) => s.bron_iri === root.dataset.bron)!;
      const offset = (container: Node, position: number, fallback: number) => {
        if (!root.contains(container)) return fallback;
        const prefix = document.createRange(); prefix.selectNodeContents(root); prefix.setEnd(container, position);
        return prefix.toString().length;
      };
      const start = offset(range.startContainer, range.startOffset, 0);
      const eind = offset(range.endContainer, range.endOffset, segment.tekst.length);
      if (eind > start) ankers.push(segmentAnker(segment, start, eind));
    }
    setSelectie(ankers);
  }
  const selected = view?.elementen.find((e) => e.id === actief);
  async function beslis(el: NodeElement, type: string, wijziging?: unknown) {
    if (!view) return;
    await wijzig(`elementen/${encodeURIComponent(el.id)}/beslissing`, {
      type, snapshot_id: view.snapshot_id, verwachte_revisies: verwachteRevisies(view),
      ...(reden ? { comment: reden, review_reason: reden } : {}),
      ...(wijziging ? { wijziging, review_reason: reden || (typeof wijziging === "object" && "klasse" in wijziging ? "verkeerde_klasse" : "tekst") } : {}),
    });
  }
  async function exporteer(formaat: string) {
    if (!view) return;
    setBezig(true); setFout("");
    try {
      const response = await fetch("/api/annotatie/v2/weergave/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bron_iri: view.doel.bron_iri, snapshot_id: view.snapshot_id, formaat }),
      });
      if (!response.ok) throw await nodeError(response);
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a"); a.href = url; a.download = `annotatie.${formaat}`;
      a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setFout((e as Error).message); }
    finally { setBezig(false); }
  }
  const button = "rounded border border-line px-2 py-1 text-sm disabled:opacity-40";
  const inhoud = <div className="min-w-0 space-y-4 overflow-y-auto bg-paper p-5">
    <div className="flex flex-wrap items-center gap-2">
      <h2 className="min-w-0 flex-1 text-lg font-medium">{view?.doel.label || doel.label || "Annotatie"}</h2>
      {onSluit && <button className={button} onClick={onSluit}>Sluiten</button>}
    </div>
    <p aria-live="polite" className="text-sm">{melding}</p>
    {fout && <div role="alert" className="rounded border border-red-300 p-3">{fout}{" "}
      <button className={button} onClick={() => void laad()}>Opnieuw laden</button></div>}
    {!view && !fout && <p>Annotatie laden…</p>}
    {view && <>
      {doel.snapshot_id && doel.snapshot_id !== view.snapshot_id && <p role="status" className="rounded border border-line p-3 text-sm">De brontekst is gewijzigd sinds dit verzoek. Je ziet de huidige versie; eerdere markeringen blijven herkenbaar als historie.</p>}
      <div className="flex flex-wrap gap-2 text-sm">
        <Link className="underline" href={nodeLink({ ...view.doel, snapshot_id: view.snapshot_id })}>Deelbare annotatie</Link>
        <span>{view.elementen.filter((e) => !e.verouderd).length} elementen</span>
        {["pdf", "csv", "json"].map((f) => <button className={button} key={f} disabled={bezig} onClick={() => void exporteer(f)}>Export {f.toUpperCase()}</button>)}
      </div>
      <div ref={tekstRef} className="space-y-3 rounded border border-line bg-white p-4" onMouseUp={selecteer} onKeyUp={selecteer} onTouchEnd={selecteer}>
        {view.segmenten.map((s) => {
          const chars = Array.from(s.tekst);
          const anchors = selected && !selected.verouderd ? selected.ankers.filter((a) => a.bron_iri === s.bron_iri && a.bron_hash === s.bron_hash) : [];
          const boundaries = [...new Set([0, chars.length, ...anchors.flatMap((a) => [a.start, a.eind])])].sort((a, b) => a - b);
          return <section key={s.bron_iri}>
            <p className="mb-1 select-none text-xs font-medium text-muted">{s.label}</p>
            <div data-bron={s.bron_iri} className="whitespace-pre-wrap leading-7">{boundaries.slice(0, -1).map((start, i) => {
              const end = boundaries[i + 1], value = chars.slice(start, end).join("");
              return anchors.some((a) => a.start <= start && a.eind >= end)
                ? <mark key={start}>{value}</mark> : <span key={start}>{value}</span>;
            })}</div>
          </section>;
        })}
      </div>
      {selectie.length > 0 && <div className="space-y-2 rounded border border-line p-3">
        <p className="text-sm">Geselecteerd: {selectie.map((a) => a.tekst).join(" … ")}</p>
        <label className="block text-sm">JAS-klasse<select className="ml-2 rounded border p-1" value={klasse} onChange={(e) => setKlasse(e.target.value)}>
          <option value="">Kies een klasse</option>{JAS_KLASSEN.map((k) => <option key={k}>{k}</option>)}
        </select></label>
        <label className="block text-sm">Toelichting<input className="ml-2 rounded border p-1" value={toelichting} onChange={(e) => setToelichting(e.target.value)} /></label>
        <button className={button} disabled={bezig || !klasse.trim()} onClick={() => void wijzig("elementen", {
          doel: { bron_iri: view.doel.bron_iri }, snapshot_id: view.snapshot_id,
          verwachte_revisies: verwachteRevisies(view), element: { klasse, toelichting,
            tekst: selectie.map((a) => a.tekst).join(" "), ankers: selectie },
        })}>Markering toevoegen</button>{" "}
        {selected && <button className={button} disabled={bezig || elementVergrendeld(view, selected)} onClick={() => void beslis(selected, "edit", {
          tekst: selectie.map((a) => a.tekst).join(" "), ankers: selectie,
        })}>Gekozen markering aanpassen</button>}{" "}
        <button className={button} onClick={() => setSelectie([])}>Selectie sluiten</button>
      </div>}
      <div className="space-y-2">
        <h3 className="font-medium">Beoordelen</h3>
        <label className="block text-sm">Weergave<select aria-label="Reviewfilter" className="ml-2 rounded border p-1" value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="alles">Actuele markeringen</option><option value="open">Te beoordelen</option>
          <option value="aandacht">Met aandachtspunt</option><option value="historie">Oudere bronversies</option>
        </select></label>
        <label className="block text-sm">Reden of toelichting bij beslissing<input className="mt-1 block w-full rounded border p-2" value={reden} onChange={(e) => setReden(e.target.value)} /></label>
        {view.elementen.filter((e) => filter === "historie" ? e.verouderd : !e.verouderd
          && (filter !== "aandacht" || ["geel", "rood"].includes(e.aandacht || ""))
          && (filter !== "open" || !["human_approved", "edited", "rejected", "published"].includes(e.lifecycle))).map((e) => <article key={e.id} className="rounded border border-line p-3">
          <button className="text-left font-medium" onClick={() => setActief(actief === e.id ? undefined : e.id)}>{e.klasse}: {e.tekst}</button>
          <p className="text-sm text-muted">{e.toelichting}</p>
          <p className="text-xs text-muted">{e.verouderd ? "Historie · oudere brontekst" : LIFECYCLE_LABEL[e.lifecycle as Lifecycle] || e.lifecycle}</p>
          <NodeReviewDetails key={`${e.id}:${view.lagen.find((l) => l.bron_iri === e.eigenaar_iri)?.revisie}`}
            element={e} disabled={bezig || elementVergrendeld(view, e)} onEdit={(value) => beslis(e, "edit", value)} />
          {onVraag && <button className={`${button} mt-2`} onClick={() => onVraag(e, view)}>Vraag Lex</button>}
          {!e.verouderd && <div className="mt-2 flex flex-wrap gap-2">
            <button className={button} disabled={bezig || elementVergrendeld(view, e)} onClick={() => void beslis(e, "approve")}>Akkoord</button>
            <button className={button} disabled={bezig || elementVergrendeld(view, e) || !reden.trim()} onClick={() => void beslis(e, "reject")}>Verwerpen</button>
            <button className={button} disabled={bezig || !reden.trim() || view.lagen.some((l) => l.bron_iri === e.eigenaar_iri && l.status === "geaccordeerd")} onClick={() => void beslis(e, "comment")}>Toelichten</button>
            {e.herkomst === "mens" && e.aangemaakt_door === sessie?.user?.userid && !e.beslissingen?.length && <BevestigKnop
              className={button} bevestigTekst="Markering wissen?" disabled={bezig || elementVergrendeld(view, e)}
              onBevestig={() => wijzig(`elementen/${encodeURIComponent(e.id)}?verwachte_revisie=${view.lagen.find((l) => l.bron_iri === e.eigenaar_iri)?.revisie}`, {}, "DELETE")}>Wissen</BevestigKnop>}
            {["human_approved", "rejected"].includes(e.lifecycle) && (e.herkomst !== "mens" || !!e.beslissingen?.length) && <button className={button}
              disabled={bezig || view.lagen.some((l) => l.bron_iri === e.eigenaar_iri && l.status === "geaccordeerd")}
              onClick={() => void beslis(e, "heropen")}>Beoordeling heropenen</button>}
          </div>}
        </article>)}
      </div>
      {view.verwijzingen.length > 0 && <div className="rounded border border-line p-3">
        <h3 className="font-medium">Overspant meerdere bepalingen</h3>
        <p className="text-sm text-muted">Deze gerelateerde annotaties zijn hier gedeeltelijk zichtbaar en tellen niet mee in de review.</p>
        {view.verwijzingen.map((r) => <p key={r.id} className="text-sm"><Link className="underline" href={nodeLink({ bron_iri: r.eigenaar_iri })}>{r.klasse} · {r.label}</Link></p>)}
      </div>}
      <div className="space-y-2"><h3 className="font-medium">Voortgang per bepaling</h3>
        {view.lagen.map((l) => <div className="flex flex-wrap items-center gap-2 text-sm" key={l.id}>
          <span>{view.segmenten.find((s) => s.bron_iri === l.bron_iri)?.label || view.doel.label}</span>
          <span>{l.status === "geaccordeerd" ? "Afgerond" : "In review"}</span>
          <button className={button} disabled={bezig} onClick={() => void wijzig(`lagen/${encodeURIComponent(l.id)}/status`, {
            status: l.status === "geaccordeerd" ? "in_review" : "geaccordeerd", verwachte_revisie: l.revisie,
          })}>{l.status === "geaccordeerd" ? "Heropenen" : "Afronden"}</button>
        </div>)}
      </div>
    </>}
  </div>;
  return onSluit ? <Dialog label={`Annotatie: ${doel.label || "bepaling"}`} variant={variant} onSluit={onSluit}>{inhoud}</Dialog> : inhoud;
}
