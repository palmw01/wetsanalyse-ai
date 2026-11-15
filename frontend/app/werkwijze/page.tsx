import { redirect } from "next/navigation";

import { aanpassingPad } from "@/lib/aanpassingen";

/** De werkwijze van Lex bestaat niet meer als pagina (plan instellingen-aanpassingen): methodes en agents staan onder
 *  Instellingen › Aanpassingen. Een oude link of bladwijzer opent daar Agents. */
export default function WerkwijzePagina() {
  redirect(aanpassingPad("agents"));
}
