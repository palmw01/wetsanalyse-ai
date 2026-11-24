"use client";

/** De bediening van een tekening die je verschuift en zoomt (een SVG met een `viewBox`), op één manier voor elke plek:
 *  het muiswiel zoomt rond de cursor, slepen verschuift, twee vingers knijpen en verschuiven tegelijk, en een klik zonder
 *  slepen blijft een klik. Dat is de bediening van de graaf (sigma), voor tekeningen die niet in sigma staan, zoals het
 *  2c-diagram. Melding gebruiker 24 nov 2026: op mobiel zoomde de graaf met twee vingers, het diagram niet.
 *
 *  De rekenkern is puur (`zoomRond`, `knijp`, `naarTekening`; `useBeeld.test.ts`); de hook houdt de wijzers bij. */
import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent,
  type RefObject } from "react";

/** Wat in beeld is, in de eenheden van de tekening (de `viewBox`). */
export interface Beeld { x: number; y: number; b: number; h: number }

/** Hoe ver je in- en uitzoomt tegenover de hele tekening: hoogstens 6× in, iets verder uit dan alles. */
export const ZOOM_IN = 6;
export const ZOOM_UIT = 1.2;
/** Zo veel pixels beweegt een wijzer voordat het slepen is in plaats van klikken. */
const DREMPEL = 4;

interface Vak { left: number; top: number; width: number; height: number }

/** De schaal (pixels per eenheid) en de rand waarmee de tekening in het venster staat (`xMidYMid meet`). */
export function maat(beeld: Beeld, vak: Vak): { s: number; ox: number; oy: number } {
  const s = Math.min(vak.width / beeld.b, vak.height / beeld.h) || 1;
  return { s, ox: (vak.width - beeld.b * s) / 2, oy: (vak.height - beeld.h * s) / 2 };
}

/** Het punt in de tekening onder een punt op het scherm. */
export function naarTekening(beeld: Beeld, vak: Vak, clientX: number, clientY: number): { x: number; y: number } {
  const { s, ox, oy } = maat(beeld, vak);
  return { x: beeld.x + (clientX - vak.left - ox) / s, y: beeld.y + (clientY - vak.top - oy) / s };
}

/** De breedte begrensd tegenover de hele tekening. */
function begrens(b: number, alles: Beeld): number {
  return Math.min(alles.b * ZOOM_UIT, Math.max(alles.b / ZOOM_IN, b));
}

/** Zoom met `factor` (< 1: inzoomen) rond een punt in de tekening, dat op zijn plek blijft; zonder punt rond het midden. */
export function zoomRond(v: Beeld, factor: number, alles: Beeld, rond?: { x: number; y: number }): Beeld {
  const b = begrens(v.b * factor, alles);
  const f = b / v.b;
  const c = rond ?? { x: v.x + v.b / 2, y: v.y + v.h / 2 };
  return { x: c.x - (c.x - v.x) * f, y: c.y - (c.y - v.y) * f, b, h: v.h * f };
}

/** Knijpen met twee vingers: het punt van de tekening dat bij het begin onder het midden van de vingers lag, blijft onder
 *  het midden van nu; de afstand tussen de vingers bepaalt de zoom. Zo verschuift en zoomt één gebaar tegelijk. */
export function knijp(start: Beeld, vak: Vak, alles: Beeld,
  van: { midden: { x: number; y: number }; afstand: number },
  nu: { midden: { x: number; y: number }; afstand: number }): Beeld {
  const anker = naarTekening(start, vak, van.midden.x, van.midden.y);
  const b = begrens(start.b * (van.afstand / Math.max(nu.afstand, 1)), alles);
  const f = b / start.b;
  const h = start.h * f;
  // De rand (ox, oy) verandert niet bij zoomen: breedte × schaal blijft gelijk.
  const { s, ox, oy } = maat(start, vak);
  const s2 = s / f;
  return { x: anker.x - (nu.midden.x - vak.left - ox) / s2, y: anker.y - (nu.midden.y - vak.top - oy) / s2, b, h };
}

type Punt = { x: number; y: number };
const midden = (a: Punt, b: Punt): Punt => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
const afstand = (a: Punt, b: Punt): number => Math.hypot(a.x - b.x, a.y - b.y);

/** De bediening van één tekening. `alles` is de hele tekening; verandert die (een nieuwe tekening), dan staat weer alles
 *  in beeld. Geeft het beeld voor de `viewBox`, de handlers voor het element, en `zoom`/`pasIn` voor de knoppen
 *  (`GraafBeeld`). Het element krijgt `touch-none`: de gebaren zijn van de tekening, niet van de pagina. */
export function useBeeld(tekening: Beeld, element: RefObject<Element | null>) {
  const sleutel = `${tekening.x}:${tekening.y}:${tekening.b}x${tekening.h}`;
  // Op de maten, niet op het object: een tekening is elke render een nieuw object.
  const alles = useMemo(() => tekening, [sleutel]); // eslint-disable-line react-hooks/exhaustive-deps
  const [beeld, setBeeld] = useState<Beeld>(alles);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setBeeld(alles), [alles]);
  const huidig = useRef(beeld);
  useEffect(() => { huidig.current = beeld; }, [beeld]);
  const wijzers = useRef(new Map<number, Punt>());
  /** Het begin van het gebaar: het beeld en de wijzers toen; `bewogen` zodra het slepen of knijpen is. */
  const gebaar = useRef<{ beeld: Beeld; vak: Vak; punten: Map<number, Punt>; bewogen: boolean } | null>(null);
  const [sleept, setSleept] = useState(false);

  const vak = (): Vak => element.current?.getBoundingClientRect() ?? { left: 0, top: 0, width: 1, height: 1 };
  const zoom = useCallback((factor: number, rond?: Punt) => setBeeld((v) => zoomRond(v, factor, alles, rond)),
    [alles]);
  const pasIn = useCallback(() => setBeeld(alles), [alles]);

  // Het muiswiel zoomt rond de cursor. Een eigen luisteraar, niet `onWheel`: React registreert die passief, en dan scrolt
  // de pagina mee.
  useEffect(() => {
    const el = element.current;
    if (!el) return;
    const wiel = (e: Event) => {
      const w = e as WheelEvent;
      w.preventDefault();
      setBeeld((v) => zoomRond(v, Math.exp(w.deltaY * 0.0015), alles, naarTekening(v, el.getBoundingClientRect(), w.clientX, w.clientY)));
    };
    el.addEventListener("wheel", wiel, { passive: false });
    return () => el.removeEventListener("wheel", wiel);
  }, [element, alles]);

  /** Een nieuw begin bij elke wijziging van het aantal wijzers, zodat het beeld niet springt. */
  const herbegin = (bewogen: boolean) => {
    gebaar.current = wijzers.current.size
      ? { beeld: huidig.current, vak: vak(), punten: new Map(wijzers.current), bewogen }
      : null;
  };

  const onPointerDown = (e: ReactPointerEvent) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    wijzers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    // Een eerste wijzer begint een nieuw gebaar (een oud, na knijpen zonder klik, vervalt); een tweede vinger is altijd
    // een gebaar: geen klik meer na afloop.
    herbegin(wijzers.current.size > 1);
    if (wijzers.current.size > 1) {
      setSleept(true);
      for (const id of wijzers.current.keys()) element.current?.setPointerCapture?.(id);
    }
  };
  const onPointerMove = (e: ReactPointerEvent) => {
    const g = gebaar.current;
    if (!g || !wijzers.current.has(e.pointerId)) return;
    wijzers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const [a, b] = [...wijzers.current.keys()];
    if (b !== undefined) {
      const [a0, b0] = [g.punten.get(a), g.punten.get(b)];
      const [a1, b1] = [wijzers.current.get(a)!, wijzers.current.get(b)!];
      if (!a0 || !b0) return;
      setBeeld(knijp(g.beeld, g.vak, alles, { midden: midden(a0, b0), afstand: afstand(a0, b0) },
        { midden: midden(a1, b1), afstand: afstand(a1, b1) }));
      return;
    }
    const p0 = g.punten.get(a);
    if (!p0) return;
    const dx = e.clientX - p0.x, dy = e.clientY - p0.y;
    if (!g.bewogen && Math.abs(dx) + Math.abs(dy) < DREMPEL) return;
    if (!g.bewogen) { g.bewogen = true; setSleept(true); element.current?.setPointerCapture?.(e.pointerId); }
    const { s } = maat(g.beeld, g.vak);
    setBeeld({ ...g.beeld, x: g.beeld.x - dx / s, y: g.beeld.y - dy / s });
  };
  const onPointerEnd = (e: ReactPointerEvent) => {
    if (!wijzers.current.delete(e.pointerId)) return;
    if (element.current?.hasPointerCapture?.(e.pointerId)) element.current.releasePointerCapture(e.pointerId);
    const bewogen = !!gebaar.current?.bewogen;
    if (wijzers.current.size) herbegin(true);   // van knijpen naar slepen met de vinger die blijft
    else {
      setSleept(false);
      // De klik die volgt, ziet `bewogen` nog (`onClickCapture`); zonder bewegen is er geen gebaar meer.
      gebaar.current = bewogen ? { ...gebaar.current!, bewogen } : null;
    }
  };
  // Na echt slepen of knijpen is de klik die volgt geen keuze.
  const onClickCapture = (e: ReactMouseEvent) => {
    if (gebaar.current?.bewogen && !wijzers.current.size) { e.stopPropagation(); e.preventDefault(); }
    if (!wijzers.current.size) gebaar.current = null;
  };

  return {
    beeld, zoom, pasIn, sleept,
    handlers: { onPointerDown, onPointerMove, onPointerUp: onPointerEnd, onPointerCancel: onPointerEnd, onClickCapture },
  };
}
