import Link from "next/link";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "xs" | "sm" | "md";

// Rijkshuisstijl: primaire knop in lintblauw, secundaire als lintblauw-outline.
const variants: Record<Variant, string> = {
  primary: "bg-accent text-paper hover:bg-accent-soft border-transparent",
  secondary: "bg-paper text-lint hover:bg-surface border-lint",
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

// Elke knop is een pil (spoor I4, besluit 26 okt 2026). De enige uitzondering is *Nieuw gesprek* in de
// sidebar (`GesprekSidebar`), die zijn eigen klasse houdt; `app/knoppen.test.ts` legt beide vast.
const base =
  "rounded-full inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lint";

/** De klassen van een knop, voor een element dat geen `Button` kan zijn (een `BevestigKnop`, een link). */
export function knopKlasse(variant: Variant = "primary", size: Size = "md"): string {
  return `${base} ${sizes[size]} ${variants[variant]}`;
}

/** Een rijactie in een lijst (`size="xs"`), rustig: lijn en lintblauwe tekst. Wat de losse `KNOP`-constanten
 *  in de werkgebiedcomponenten waren; de kleur zet de aanroeper erbij als die iets betekent. */
export const KNOP_XS = `${base} ${sizes.xs}`;

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({ variant = "primary", size = "md", className = "", ...props }: ButtonProps) {
  return <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...props} />;
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
    <Link href={href} onClick={onClick} className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}>
      {children}
    </Link>
  );
}
