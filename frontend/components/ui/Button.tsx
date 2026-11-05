import Link from "next/link";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "xs" | "sm" | "md";

// Rijkshuisstijl: primaire knop in lintblauw. De tweede keuze heeft de vorm van *Nieuw gesprek* (spoor K): wit, een
// lichte rand en een zachte schaduw die bij hover dieper wordt.
const variants: Record<Variant, string> = {
  primary: "bg-accent text-paper hover:bg-accent-soft border-transparent",
  secondary: "bg-paper text-lint hover:border-lint/40 border-line",
  ghost: "bg-transparent text-muted hover:bg-surface hover:text-lint border-transparent",
  danger: "bg-transparent text-fout hover:bg-fout/10 border-fout/40",
};

// Min. hoogte 48px voor primaire/secundaire knoppen (md); sm is compact voor inline-acties.
// Compact met een muis, ruim op touch: de 48px-eis uit de Rijkshuisstijl gaat over
// aanraakbediening. Met een fijne pointer oogt dat log, terwijl 40px daar ruim volstaat.
// xs is de rijactie (spoor I4): klein in een rij of lijst, met het klikdoel van WCAG 2.5.8 (24px) en 44px op touch.
const sizes: Record<Size, string> = {
  xs: "min-h-[24px] coarse:min-h-[44px] px-2.5 py-0.5 text-[11px]",
  sm: "min-h-[32px] coarse:min-h-[44px] px-3 py-1.5 text-sm",
  md: "min-h-[40px] coarse:min-h-[48px] px-4 py-2 text-sm",
};

// De vorm (besluit gebruiker 5 nov 2026, het stijlblad): **een pil is een label, een afgeronde rechthoek is een knop.**
// Elke maat is de rechthoek van *Nieuw gesprek*: `rounded-kaart` (md, 40px), `rounded-knop` (sm, 32px) en
// `rounded-knop-xs` (xs, 24px, een rijactie – tot 5 nov 2026 een pil, en dus niet van een label te onderscheiden). Met een
// vlak (primair, tweede keuze) een zachte schaduw die bij hover dieper wordt; een rijactie krijgt die pas bij hover.
// `app/knoppen.test.ts` legt het vast.
const vorm: Record<Size, string> = { xs: "rounded-knop-xs", sm: "rounded-knop", md: "rounded-kaart" };
const SCHADUW = "shadow-zacht hover:shadow-kaart";
const metSchaduw = (variant: Variant, size: Size) =>
  variant === "primary" || variant === "secondary" ? ` ${size === "xs" ? "hover:shadow-zacht" : SCHADUW}` : "";

const base =
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap border font-medium transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint";

/** De klassen van een knop, voor een element dat geen `Button` kan zijn (een `BevestigKnop`, een link). */
export function knopKlasse(variant: Variant = "primary", size: Size = "md"): string {
  return `${base} ${vorm[size]} ${sizes[size]} ${variants[variant]}${metSchaduw(variant, size)}`;
}

/** Een rijactie in een lijst (`size="xs"`), rustig: lijn en lintblauwe tekst. Wat de losse `KNOP`-constanten
 *  in de werkgebiedcomponenten waren; de kleur zet de aanroeper erbij als die iets betekent. */
export const KNOP_XS = `${base} ${vorm.xs} ${sizes.xs} bg-paper hover:shadow-zacht`;

/** Een knop met alleen een icoon (⋯, ✕, ‹ ›): een vierkant met de vorm, rand en hover van een knop. `xs` in een rij,
 *  `sm` in een kop naast knoppen van 32px. Een `aria-label` is verplicht: er staat geen tekst op. */
export function icoonKnopKlasse(size: "xs" | "sm" = "xs"): string {
  const maat = size === "xs" ? "h-6 w-6 rounded-knop-xs" : "h-8 w-8 rounded-knop";
  return `focus-ring inline-flex shrink-0 items-center justify-center border border-line bg-paper text-muted transition hover:border-lint/40 hover:text-lint hover:shadow-zacht aria-expanded:border-lint aria-expanded:text-lint disabled:cursor-not-allowed disabled:opacity-50 coarse:h-11 coarse:w-11 ${maat}`;
}

export function IcoonKnop({ size = "xs", className = "", ...props }: { size?: "xs" | "sm"; "aria-label": string }
  & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className={`${icoonKnopKlasse(size)} ${className}`} {...props} />;
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({ variant = "primary", size = "md", className = "", ...props }: ButtonProps) {
  return <button className={`${knopKlasse(variant, size)} ${className}`} {...props} />;
}

interface LinkButtonProps {
  href: string;
  variant?: Variant;
  size?: Size;
  className?: string;
  onClick?: () => void;
  children: React.ReactNode;
}

export function LinkButton({
  href,
  variant = "primary",
  size = "md",
  className = "",
  onClick,
  children,
}: LinkButtonProps) {
  return (
    <Link href={href} onClick={onClick} className={`${knopKlasse(variant, size)} ${className}`}>
      {children}
    </Link>
  );
}
