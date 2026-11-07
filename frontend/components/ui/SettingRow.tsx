import type { ReactNode } from "react";

// De panelen van de instellingen staan naast de tabkolom, dus wat een rij aan ruimte heeft zegt de breedte van het
// venster niet: op 640 px is de kolom 325 px breed en staat het eerste breakpoint al aan. Daarom breekt alles hier op
// de ruimte die er echt is, met `flex-wrap` en een basisbreedte. De hoge groeifactor geeft de rest van een volle regel
// aan het label of het veld; staat iets alleen op een regel, dan vult het die.

/** Eén instelling: label (met eventueel een toelichting) links, de bediening rechts.
 *
 *  De vorm van een instellingenscherm, niet die van een formulier: geen kaders per veld, alleen een
 *  dunne scheidingslijn tussen de rijen (zet `divide-y divide-line` op de omhullende lijst). Past het
 *  niet naast elkaar, dan zakt de bediening onder het label. Een invoerveld krijgt `veld`: zo breed als
 *  naast het label past, en de volle breedte als het eronder staat. */
export function SettingRow({
  label,
  omschrijving,
  htmlFor,
  veld = false,
  children,
}: {
  label: ReactNode;
  omschrijving?: ReactNode;
  /** Maakt het label klikbaar voor het veld ernaast. */
  htmlFor?: string;
  /** De bediening is een invoerveld en geen korte waarde. */
  veld?: boolean;
  children?: ReactNode;
}) {
  const Label = htmlFor ? "label" : "span";
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3.5">
      <div className="min-w-0 flex-[999_1_9rem]">
        <Label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
          {label}
        </Label>
        {omschrijving && <p className="mt-0.5 text-[0.8125rem] leading-snug text-muted">{omschrijving}</p>}
      </div>
      {children && (
        <div className={`flex min-w-0 max-w-full items-center gap-2 ${veld ? "flex-[1_1_16rem]" : "flex-wrap"}`}>{children}</div>
      )}
    </div>
  );
}

/** Velden en hun knoppen op één regel, zolang dat past: de velden delen de ruimte, en wat niet past zakt naar de
 *  volgende regel en vult die. Geef de velden geen eigen breedte; de rij regelt het. */
export function FormRij({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`flex flex-wrap items-end gap-3 [&>*]:min-w-0 [&>*]:flex-[999_1_12rem] [&>button]:flex-[1_0_auto] ${className}`}>
      {children}
    </div>
  );
}

/** Twee knoppen in een `FormRij` die bij elkaar horen: ze zakken samen naar de volgende regel. */
export function FormKnoppen({ children }: { children: ReactNode }) {
  return <div className="flex !flex-[1_0_auto] flex-wrap gap-3 [&>*]:flex-1">{children}</div>;
}

/** Een formulier in twee kolommen, of één als er voor twee geen ruimte is. */
export function FormRaster({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-[repeat(auto-fit,minmax(min(13rem,100%),1fr))] gap-5">{children}</div>;
}

/** Lijst van instellingen met scheidingslijnen ertussen. */
export function SettingList({ children }: { children: ReactNode }) {
  return <div className="divide-y divide-line">{children}</div>;
}

/** Kop boven een groep instellingen (de tabnaam, zoals "Algemeen" in het voorbeeld). */
export function SettingGroup({
  titel,
  omschrijving,
  count,
  acties,
  children,
}: {
  titel: string;
  omschrijving?: string;
  /** Aantal items, voor lijstgroepen (gebruikers, tokens, profielen). */
  count?: number;
  /** De hoofdknop van de groep (*Nieuw profiel*), rechts in de kop. */
  acties?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="mb-6 last:mb-0">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="flex items-baseline gap-2 font-display text-base font-semibold text-lint">
            {titel}
            {count !== undefined && <span className="font-mono text-xs font-normal text-faint">{count}</span>}
          </h3>
          {omschrijving && <p className="mt-1 text-[0.8125rem] leading-snug text-muted">{omschrijving}</p>}
        </div>
        {acties && <div className="flex shrink-0 items-center gap-2">{acties}</div>}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}
