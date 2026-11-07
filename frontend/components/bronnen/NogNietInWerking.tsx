import { Melding } from "@/components/ui/Melding";

/** Bij tekst die al in de regeling staat maar nog niet geldt. Dezelfde zin overal: in het antwoord, bij de bepaling en
 *  op de annotatie. */
export function NogNietInWerking() {
  return <Melding type="waarschuwing" compact>Deze bepaling is nog niet in werking getreden.</Melding>;
}
