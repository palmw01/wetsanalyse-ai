"use client";

import { useLayoutEffect, useRef } from "react";

import { inputBase } from "@/components/ui/Field";

/** Een tekstvak dat meegroeit met zijn inhoud (spoor I3): geen uitrekgreep en geen eigen scrollbalk, dus alles
 *  wat er staat is te zien. De hoogte volgt de tekst bij elke wijziging en bij een andere breedte. */
export function AutoTextarea({ className = "", rows = 2, ...props }: React.ComponentProps<"textarea">) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const pas = () => {
      el.style.height = "auto";
      // De rand telt mee in de hoogte, niet in `scrollHeight`.
      el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`;
    };
    pas();
    if (typeof ResizeObserver === "undefined") return;
    let breedte = el.clientWidth;
    const waarnemer = new ResizeObserver(() => {
      if (el.clientWidth !== breedte) { breedte = el.clientWidth; pas(); }
    });
    waarnemer.observe(el);
    return () => waarnemer.disconnect();
  }, [props.value]);
  return (
    <textarea ref={ref} rows={rows} data-meegroeiend {...props}
      className={`${inputBase} resize-none overflow-hidden ${className}`} />
  );
}
