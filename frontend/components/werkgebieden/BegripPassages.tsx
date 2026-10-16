"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BevestigKnop } from "@/components/ui/BevestigKnop";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Melding } from "@/components/ui/Melding";
import type { BegripMutatie } from "@/components/werkgebieden/BegripWerk";
import { Herbeoordeling } from "@/components/werkgebieden/Herbeoordeling";
import { foutTekst, haalInventaris, koppelElementen, ontkoppel, wijzigKoppeling } from "@/lib/api";
import { ACTUALITEIT_LABEL, BEOORDELING_LABEL, KOPPELROL_LABEL, sorteerKoppelingen } from "@/lib/begrippen";
import { jasStyle, klasseLabel } from "@/lib/jas";
import type { Begrip, GeraakteKoppeling, InventarisElement, KoppelBeoordeling, KoppelRol, Koppeling } from "@/lib/types";
import { annotatieHref, filterElementen } from "@/lib/werkgebied";

const KNOP =
  "focus-ring inline-flex min-h-[24px] items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50 coarse:min-h-[44px]";
const ROLLEN = Object.keys(KOPPELROL_LABEL) as KoppelRol[];

/** De bronpassages van het begrip, elk apart: de letterlijke tekst zoals die gekoppeld werd, waar
 *  hij staat, en hoe het er nu mee staat. Een samenvatting vervangt de passages nooit. */
export function BegripPassages({ id, begrip, primair, muteer, geraakt }: {
  id: string;
  begrip: Begrip;
  primair: Record<string, { begrip_id: string; naam: string }>;
  muteer: BegripMutatie;
  /** Herbeoordelen (fase F1): de passages die veranderden, op koppeling-id. */
  geraakt?: Map<string, GeraakteKoppeling>;
}) {
  const [kiezerOpen, setKiezerOpen] = useState(false);
  const passages = sorteerKoppelingen(begrip.koppelingen);

  return (
    <section className="space-y-3" aria-label="Bronpassages">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-display text-sm font-semibold text-lint">
          Bronpassages ({passages.length})
        </h3>
        <Button size="sm" variant="secondary" onClick={() => setKiezerOpen((v) => !v)} aria-expanded={kiezerOpen}>
          {kiezerOpen ? "Sluiten" : "Passages toevoegen"}
        </Button>
      </div>
      {kiezerOpen && (
        <ElementKiezer id={id} begrip={begrip} primair={primair} muteer={muteer} onKlaar={() => setKiezerOpen(false)} />
      )}
      {passages.length === 0 ? (
        <p className="text-sm text-muted">
          Nog geen passages. Een begrip krijgt zijn onderbouwing uit de annotaties: voeg de passages toe die
          het aanduiden of de definitie dragen.
        </p>
      ) : (
        <ul className="space-y-2" aria-label="Passages van dit begrip">
          {passages.map((k) => (
            <Passage key={k.id} id={id} begrip={begrip} koppeling={k} muteer={muteer} geraakt={geraakt?.get(k.id)} />
          ))}
        </ul>
      )}
    </section>
  );
}

function Passage({ id, begrip, koppeling: k, muteer, geraakt }: {
  id: string;
  begrip: Begrip;
  koppeling: Koppeling;
  muteer: BegripMutatie;
  geraakt?: GeraakteKoppeling;
}) {
  const beoordeel = (b: KoppelBeoordeling) =>
    muteer((r) => wijzigKoppeling(id, begrip.id, k.id, { verwachte_revisie: r, beoordeling: b }));
  // Elke passage heeft dezelfde knoppen; voor een schermlezer zegt de naam bij welke passage ze horen.
  const bij = `“${k.bewijs.tekst}”`;
  return (
    <li className={`rounded-kaart border bg-paper px-3 py-2 ${k.beoordeling === "afgewezen" ? "border-line opacity-70" : "border-line"}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${jasStyle(k.bewijs.klasse)}`}>
          {klasseLabel(k.bewijs.klasse)}
        </span>
        <span className="text-xs text-muted">{k.bewijs.vindplaats}</span>
      </div>
      <blockquote className="mt-1 text-sm text-ink">“{k.bewijs.tekst}”</blockquote>
      {k.vervangt && (
        <details className="mt-1 text-xs text-muted">
          <summary className="focus-ring cursor-pointer rounded">Vervangt een eerdere passage</summary>
          <p className="mt-0.5">
            Toen: “{k.vervangt.bewijs.tekst}” · {klasseLabel(k.vervangt.bewijs.klasse)} · {k.vervangt.bewijs.vindplaats}
          </p>
        </details>
      )}
      {(k.bevestigingen?.length ?? 0) > 0 && (
        <p className="mt-1 text-xs text-muted">
          Na een wijziging bevestigd door {k.bevestigingen!.at(-1)!.door}; de stand van het koppelen blijft bewaard.
        </p>
      )}
      {geraakt && <Herbeoordeling id={id} begrip={begrip} geraakt={geraakt} muteer={muteer} />}
      {!geraakt && (k.actualiteit !== "actueel" || !k.annotatie_beoordeeld) && (
        <p className="mt-1 text-xs text-aandacht-geel-tekst">
          {[k.actualiteit !== "actueel" && ACTUALITEIT_LABEL[k.actualiteit],
            k.actualiteit === "actueel" && !k.annotatie_beoordeeld && "annotatie nog niet door een jurist beoordeeld"]
            .filter(Boolean).join(" · ")}
        </p>
      )}
      <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <Select
          value={k.rol}
          aria-label={`Rol van “${k.bewijs.tekst}”`}
          className="sm:w-56"
          onChange={(e) => void muteer((r) => wijzigKoppeling(id, begrip.id, k.id, { verwachte_revisie: r, rol: e.target.value as KoppelRol }))}
        >
          {ROLLEN.map((r) => (
            <option key={r} value={r}>{KOPPELROL_LABEL[r]}</option>
          ))}
        </Select>
        {k.beoordeling === "open" ? (
          <div className="flex gap-1.5">
            <button type="button" aria-label={`Akkoord met ${bij}`} className={`${KNOP} border-lint text-lint hover:bg-surface`} onClick={() => void beoordeel("akkoord")}>
              Akkoord
            </button>
            <button type="button" aria-label={`Wijs ${bij} af`} className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`} onClick={() => void beoordeel("afgewezen")}>
              Afwijzen
            </button>
          </div>
        ) : (
          <span className="text-xs text-muted">
            {BEOORDELING_LABEL[k.beoordeling]}
            {k.beoordeeld_door && ` · ${k.beoordeeld_door}`}{" "}
            <button type="button" aria-label={`Beoordeling van ${bij} terugzetten`} className="focus-ring rounded underline hover:text-ink" onClick={() => void beoordeel("open")}>
              terugzetten
            </button>
          </span>
        )}
        <span className="flex gap-1.5 sm:ml-auto">
          <Link href={annotatieHref(k.bewijs.eigenaar_iri, k.element_id)} aria-label={`Bekijk ${bij} in de annotatie`} className={`${KNOP} border-line text-lint hover:bg-surface`}>
            Bekijk in de annotatie
          </Link>
          <BevestigKnop
            bevestigTekst="Losmaken?"
            ariaLabel={`Maak ${bij} los van dit begrip`}
            titel="Haalt de passage bij dit begrip weg; de annotatie blijft staan."
            onBevestig={async () => { await muteer((r) => ontkoppel(id, begrip.id, k.id, r)); }}
            className={`${KNOP} border-line text-muted hover:bg-surface hover:text-ink`}
            bevestigClassName="border-fout/40 text-fout"
          >
            Losmaken
          </BevestigKnop>
        </span>
      </div>
    </li>
  );
}

/** Passages toevoegen uit de inventaris van het werkgebied. Wat al bij dit begrip hoort staat er
 *  niet meer in; wat een ander begrip aanduidt, zegt dat erbij. */
function ElementKiezer({ id, begrip, primair, muteer, onKlaar }: {
  id: string;
  begrip: Begrip;
  primair: Record<string, { begrip_id: string; naam: string }>;
  muteer: BegripMutatie;
  onKlaar: () => void;
}) {
  const [elementen, setElementen] = useState<InventarisElement[] | null>(null);
  const [fout, setFout] = useState<string | null>(null);
  const [term, setTerm] = useState("");
  const [gekozen, setGekozen] = useState<Set<string>>(new Set());
  const [rol, setRol] = useState<KoppelRol>("duiding");
  const [bezig, setBezig] = useState(false);

  useEffect(() => {
    let levend = true;
    haalInventaris(id)
      .then((inv) => levend && setElementen(inv.elementen))
      .catch((e) => levend && setFout(foutTekst(e, "De inventaris kon niet worden geladen.")));
    return () => { levend = false; };
  }, [id]);

  const al = new Set(begrip.koppelingen.map((k) => k.element_id));
  const getoond = elementen
    ? filterElementen(elementen.filter((e) => !al.has(e.id)), { rol: "alle", klasse: "alle", term })
    : [];

  async function koppel() {
    setBezig(true);
    const gelukt = await muteer(
      (r) => koppelElementen(id, begrip.id, { verwachte_revisie: r, element_ids: [...gekozen], rol }),
      {
        gelukt: gekozen.size === 1 ? "1 passage toegevoegd." : `${gekozen.size} passages toegevoegd.`,
        opFout: (e) => { setFout(foutTekst(e)); return true; },
      },
    );
    setBezig(false);
    if (gelukt) onKlaar();
  }

  return (
    <div className="space-y-2 rounded-kaart border border-lint bg-paper p-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="search"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          aria-label="Zoeken in de inventaris"
          placeholder="Zoek in de passages van het werkgebied"
          className="w-full rounded-field border border-line bg-paper px-3 py-2 text-sm text-ink outline-none placeholder:text-faint focus:border-lint focus:ring-2 focus:ring-lint/20 coarse:min-h-[48px]"
        />
        <Select value={rol} onChange={(e) => setRol(e.target.value as KoppelRol)} aria-label="Rol van de nieuwe passages" className="sm:w-56">
          {ROLLEN.map((r) => (
            <option key={r} value={r}>{KOPPELROL_LABEL[r]}</option>
          ))}
        </Select>
      </div>
      {fout && <Melding type="fout" compact>{fout}</Melding>}
      {elementen === null && !fout ? (
        <p className="text-xs text-muted">De inventaris wordt opgehaald…</p>
      ) : getoond.length === 0 ? (
        <p className="text-xs text-muted">Geen passage die hierop past.</p>
      ) : (
        <ul className="max-h-72 space-y-1 overflow-y-auto" aria-label="Passages om toe te voegen">
          {getoond.map((e) => {
            const elders = primair[e.id] && primair[e.id].begrip_id !== begrip.id ? primair[e.id] : undefined;
            return (
              <li key={e.id}>
                <label className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 hover:bg-surface coarse:min-h-[44px]">
                  <input
                    type="checkbox"
                    checked={gekozen.has(e.id)}
                    onChange={() => setGekozen((oud) => {
                      const n = new Set(oud);
                      if (n.has(e.id)) n.delete(e.id);
                      else n.add(e.id);
                      return n;
                    })}
                    className="focus-ring mt-1 accent-lint"
                  />
                  <span className="min-w-0 text-sm">
                    <span className={`mr-1.5 inline-flex rounded-full border px-1.5 text-[10px] ${jasStyle(e.klasse)}`}>{klasseLabel(e.klasse)}</span>
                    <span className="text-ink">“{e.tekst}”</span>
                    {elders && <span className="block text-xs text-muted">duidt al “{elders.naam}” aan</span>}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
      <Button size="sm" disabled={bezig || gekozen.size === 0} onClick={() => void koppel()}>
        {bezig ? "Bezig…" : gekozen.size ? `Toevoegen (${gekozen.size})` : "Toevoegen"}
      </Button>
    </div>
  );
}
