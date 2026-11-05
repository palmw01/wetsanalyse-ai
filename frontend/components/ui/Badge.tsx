import { StatusLabel } from "@/components/ui/Lijst";

/** Een technische waarde als label (provider, scope): de pil van `StatusLabel`, in monospace. */
export function Tag({ children }: { children: React.ReactNode }) {
  return (
    <StatusLabel className="font-mono font-normal">{children}</StatusLabel>
  );
}
