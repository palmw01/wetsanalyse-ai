"use client";

import { BEURT_TEKST, type HulpGroep, type HulpRegel } from "@/lib/commandos";
import { Lijst, LijstRij, Sectie } from "@/components/ui/Lijst";
import { Uitklap } from "@/components/ui/Uitklap";

/** Het overzicht van `/help` in het gesprek (`hulpOverzicht` in `lib/commandos.ts`): wat hier kan, en ingeklapt per andere
 *  context wat daar kan, met de reden. Een klik op een commando zet het in het invoerveld, net als Tab in het menu; er
 *  start niets. Een bericht van de werkplek, geen beurt van Lex. */
export function CommandoOverzicht({ groepen, onKies }: { groepen: HulpGroep[]; onKies: (aanvulling: string) => void }) {
  const [hier, ...elders] = groepen;
  const regels = (g: HulpGroep) => (
    <Lijst label={`Commando's: ${g.titel.toLowerCase()}`}>
      {g.regels.map((r) => <CommandoRegel key={`${r.naam}|${r.hulp}`} regel={r} onKies={onKies} />)}
    </Lijst>
  );
  return (
    <div className="space-y-3 rounded-kaart border border-line bg-surface px-4 py-3" data-commando-overzicht>
      <Sectie niveau={3} titel="Commando's hier" telling={hier.regels.length}
        toelichting="Typ / vooraan in het veld, of klik een commando aan om het in het veld te zetten.">
        {regels(hier)}
      </Sectie>
      {elders.map((g) => (
        <Uitklap key={g.sleutel} vorm="sectie" data-commando-groep={g.sleutel}
          samenvatting={<>{g.titel} <span className="font-normal tabular-nums text-muted">({g.regels.length})</span></>}>
          {g.reden && <p className="mt-1 text-xs text-muted">Niet in het menu hier: {g.reden}.</p>}
          {regels(g)}
        </Uitklap>
      ))}
    </div>
  );
}

function CommandoRegel({ regel, onKies }: { regel: HulpRegel; onKies: (aanvulling: string) => void }) {
  return (
    <LijstRij className="!py-2" data-commando={regel.label}
      titel={
        <span className="flex flex-wrap items-baseline gap-x-2">
          <button type="button" onClick={() => onKies(regel.aanvulling)} title={`Zet ${regel.label} in het veld`}
            className="focus-ring rounded font-mono text-meta text-lint hover:underline coarse:min-h-[44px]">
            {regel.label}
          </button>
          <span className="text-meta">{regel.hulp}</span>
        </span>
      }
      meta={[BEURT_TEKST[regel.beurt], regel.voorbeeld && (regel.beurt === "klaarzetten"
        ? `“${regel.voorbeeld}”` : <>bijvoorbeeld <span className="font-mono">{regel.voorbeeld}</span></>), regel.uit && `nu niet: ${regel.uit}`]
        .filter(Boolean).map((m, i) => <span key={i}>{i > 0 && " · "}{m}</span>)}
    />
  );
}
