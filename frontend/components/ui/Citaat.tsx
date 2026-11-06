/** Letterlijke tekst uit de bron, ingesprongen zoals een citaat in een antwoord. Geen kaart: dit staat in de tekst. */
export function Citaat({ children }: { children: React.ReactNode }) {
  return <blockquote className="whitespace-pre-line border-l-2 border-line pl-3 text-ink">{children}</blockquote>;
}
