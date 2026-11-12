import { StatusLabel } from "@/components/ui/Lijst";

/** Een technische waarde als label (een pad, een id, een provider of scope): de pil van `StatusLabel`, in monospace.
 *  Zo'n waarde heeft geen spaties en is vaak
 *  breder dan een telefoon: hij breekt daarom binnen zijn eigen breedte af in plaats van over de rand te lopen
 *  (`frontend/scripts/test-werkwijze-breedte.mjs`). Gebruik dit voor elk pad of id als label; bouw geen eigen code-pil. */
export function Tag({ children }: { children: React.ReactNode }) {
  return (
    <StatusLabel rekbaar data-tag className="max-w-full whitespace-normal font-mono font-normal [overflow-wrap:anywhere]">{children}</StatusLabel>
  );
}
