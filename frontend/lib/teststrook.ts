// De testomgeving-strook bovenaan de schil: wegklikbaar, en dan weg zolang deze login duurt.
//
// Gebonden aan de login in plaats van aan een vlag die bij uitloggen gewist moet worden: de sleutel is
// `<userid>:<loginAt>` uit het JWT (session-callback in `auth.config.ts`). Een nieuwe login geeft een
// nieuwe `loginAt`, een ander account een andere `userid` – in beide gevallen klopt de bewaarde sleutel
// niet meer en komt de strook vanzelf terug. Een verlopen sessie of een uitlogpad dat niets opruimt
// (`PasswordPanel`) kan hem dus niet laten wegblijven. In `localStorage`, zodat een herlaad en een
// tweede tab hem ook kwijt zijn; `sessionStorage` geldt per tab.

export const TESTSTROOK_SLEUTEL = "wa-teststrook-weg";

/** De sleutel van deze login, of `undefined` als het JWT er niet genoeg voor draagt. */
export function loginSleutel(userid: unknown, loginAt: unknown): string | undefined {
  if (typeof userid !== "string" || !userid) return undefined;
  if (typeof loginAt !== "number" || !Number.isFinite(loginAt)) return undefined;
  return `${userid}:${loginAt}`;
}

/** Klikte deze login de strook al weg? Zonder sleutel nooit: dan blijft hij staan. */
export function strookWeggeklikt(opgeslagen: string | null | undefined, sleutel: string | undefined): boolean {
  return !!sleutel && opgeslagen === sleutel;
}

/** De bewaarde sleutel; `null` als er niets staat of de opslag geblokkeerd is. */
export function leesWeggeklikt(opslag: Pick<Storage, "getItem"> | undefined = browserOpslag()): string | null {
  try {
    return opslag?.getItem(TESTSTROOK_SLEUTEL) ?? null;
  } catch {
    return null;
  }
}

/** Bewaar dat deze login de strook wegklikte. Mislukt het, dan geldt het alleen voor deze pagina. */
export function bewaarWeggeklikt(sleutel: string, opslag: Pick<Storage, "setItem"> | undefined = browserOpslag()): void {
  try {
    opslag?.setItem(TESTSTROOK_SLEUTEL, sleutel);
  } catch {
    // privévenster of geblokkeerde site-data: dan maar alleen in de toestand van de pagina
  }
}

function browserOpslag(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}
