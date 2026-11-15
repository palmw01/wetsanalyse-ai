"use client";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { FormRij } from "@/components/ui/SettingRow";
import { KOPIEER_MISLUKT, useKopieer } from "@/lib/kopieer";

/** Een waarde die maar één keer te zien is (een tijdelijk wachtwoord). Kopiëren zegt of het lukte; lukt het niet (geen
 *  beveiligde origin, toestemming geweigerd), dan kun je de waarde zelf selecteren. */
export function KopieerVeld({ waarde, label }: { waarde: string; label: string }) {
  const { stand, kopieer } = useKopieer(null);

  return (
    <div>
      <FormRij className="!items-center">
        {waarde.includes("\n") ? (
          <pre aria-label={label} className="w-full overflow-x-auto rounded-field border border-line bg-surface p-2 font-mono text-sm">{waarde}</pre>
        ) : (
          <Input readOnly value={waarde} aria-label={label} className="font-mono" onFocus={(e) => e.currentTarget.select()} />
        )}
        <Button size="sm" variant="secondary" onClick={() => void kopieer(waarde)}>
          {stand === "gekopieerd" ? "Gekopieerd" : "Kopiëren"}
        </Button>
      </FormRij>
      {stand === "mislukt" && (
        <p role="alert" className="mt-1 text-xs text-fout">{KOPIEER_MISLUKT}</p>
      )}
    </div>
  );
}
