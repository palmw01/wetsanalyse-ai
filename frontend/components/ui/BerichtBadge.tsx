import { StatusLabel } from "@/components/ui/Lijst";
import type { BerichtType } from "@/lib/types";

const TYPE_LABEL: Record<BerichtType, string> = {
  info:         "Informatie",
  update:       "Update",
  waarschuwing: "Waarschuwing",
  kritiek:      "Kritiek",
};

const TYPE_TOON: Record<BerichtType, "lint" | "groen" | "geel" | "rood"> = {
  info: "lint", update: "groen", waarschuwing: "geel", kritiek: "rood",
};

export function BerichtBadge({ type }: { type: BerichtType }) {
  return <StatusLabel toon={TYPE_TOON[type]}>{TYPE_LABEL[type]}</StatusLabel>;
}
