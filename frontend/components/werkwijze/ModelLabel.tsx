import { StatusLabel } from "@/components/ui/Lijst";
import { MODEL_LABEL, type Model } from "@/lib/catalogus";

/** Of er een model aan te pas komt: een label zonder oordeel (lintblauw zegt wat het is), en grijs *hier uit* als deze
 *  omgeving het onderdeel niet aanbiedt. */
export function ModelLabel({ model, aan = true }: { model: Model; aan?: boolean }) {
  return (
    <>
      <StatusLabel toon={model === "geen" ? "neutraal" : "lint"} uitleg={MODEL_LABEL[model].uitleg} data-model={model}>
        {MODEL_LABEL[model].tekst}
      </StatusLabel>
      {!aan && <StatusLabel uitleg="Deze omgeving biedt het niet aan.">hier uit</StatusLabel>}
    </>
  );
}
