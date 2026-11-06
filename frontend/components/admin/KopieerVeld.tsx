"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

/** Een waarde die maar één keer te zien is (een tijdelijk wachtwoord). Kopiëren zegt of het lukte; lukt het niet (geen
 *  beveiligde origin, toestemming geweigerd), dan kun je de waarde zelf selecteren. */
export function KopieerVeld({ waarde, label }: { waarde: string; label: string }) {
  const [stand, setStand] = useState<"" | "gekopieerd" | "mislukt">("");

  async function kopieer() {
    try {
      await navigator.clipboard.writeText(waarde);
      setStand("gekopieerd");
    } catch {
      setStand("mislukt");
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {waarde.includes("\n") ? (
          <pre aria-label={label} className="w-full overflow-x-auto rounded-field border border-line bg-surface p-2 font-mono text-sm">{waarde}</pre>
        ) : (
          <Input readOnly value={waarde} aria-label={label} className="font-mono" onFocus={(e) => e.currentTarget.select()} />
        )}
        <Button size="sm" variant="secondary" onClick={() => void kopieer()}>
          {stand === "gekopieerd" ? "Gekopieerd" : "Kopiëren"}
        </Button>
      </div>
      {stand === "mislukt" && (
        <p role="alert" className="mt-1 text-xs text-fout">Kopiëren lukt niet in deze browser. Selecteer de waarde en kopieer die zelf.</p>
      )}
    </div>
  );
}
