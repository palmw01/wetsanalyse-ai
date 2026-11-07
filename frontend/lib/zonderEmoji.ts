// Het vangnet uit de schrijfrichtlijn (docs/schrijfrichtlijn-lex.md): emoji uit modeltekst vóór weergave. De afspraak
// staat in de prompt (SCHRIJFWIJZE); dit vangt wat het model toch schrijft. Het systeemfont tekent emoji in eigen
// kleuren, buiten de huisstijl, en in een juridisch antwoord dragen ze niets.
//
// Alleen wat als emoji getekend wordt: een teken dat standaard als emoji verschijnt, of een pictogram met de
// emoji-selector (U+FE0F), met huidskleur en ZWJ-reeksen erbij. Gewone symbolen blijven staan: ©, ®, ™, § en pijlen als
// "→" of "↔" zijn tekst, en kunnen in een wet of een uitleg staan.
const EMOJI = /(?:\p{Emoji_Presentation}|\p{Extended_Pictographic}️)[\u{1F3FB}-\u{1F3FF}]?(?:‍(?:\p{Emoji_Presentation}|\p{Extended_Pictographic}️?)[\u{1F3FB}-\u{1F3FF}]?)*️? ?/gu;

export function zonderEmoji(tekst: string): string {
  return tekst.replace(EMOJI, "");
}
