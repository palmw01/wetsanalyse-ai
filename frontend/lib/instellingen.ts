/** Tabdefinities van het instellingenvenster + de pure helpers.
 *
 *  Het venster is altijd een pop-up over de pagina waar je bent, net als in Slack: het hangt aan de parameter
 *  `?instellingen=<tab>`, niet aan een eigen pagina. Een oude link naar `/instellingen/…` stuurt door naar de werkplek
 *  met het venster open.
 *
 *  Bewust een eigen module **zonder** `"use client"`: de doorverwijzing (een server component) gebruikt `tabUitPad`.
 *  Stond die in een client-bestand, dan faalt de server-aanroep met "Attempted to call tabUitPad() from the server but
 *  tabUitPad is on the client". */

/** De groepen van de tabkolom, in hun volgorde, naar het voorbeeld van Claude (plan instellingen-aanpassingen): wat van
 *  jou is, wat Lex gebruikt (*Aanpassingen*), en het beheer. */
export const INSTELLINGEN_GROEPEN = [
  { key: "persoonlijk", label: "Persoonlijk" },
  { key: "aanpassingen", label: "Aanpassingen" },
  { key: "beheer", label: "Beheer" },
] as const;

export type GroepKey = (typeof INSTELLINGEN_GROEPEN)[number]["key"];

interface TabDefinitie {
  key: string;
  /** Het pad onder `/instellingen/` van een oude link. Een tab alleen voor beheerders staat onder `beheer/`: daar zit de
   *  rolgate van `auth.config.ts`. */
  pad: string;
  label: string;
  groep: GroepKey;
  alleenBeheerder: boolean;
  /** Waar het zoekveld van de tabkolom ook op vindt, naast het label. */
  trefwoorden: readonly string[];
  /** Oude sleutels en paden van deze tab: een bladwijzer of link blijft werken. */
  vroeger?: readonly string[];
}

export const INSTELLINGEN_TABS = [
  { key: "account", pad: "account", label: "Account", groep: "persoonlijk", alleenBeheerder: false,
    trefwoorden: ["wachtwoord", "e-mail", "naam"] },
  { key: "beveiliging", pad: "beveiliging", label: "Beveiliging", groep: "persoonlijk", alleenBeheerder: false,
    trefwoorden: ["2fa", "tweestapsverificatie", "authenticator", "herstelcodes"] },
  { key: "verbruik", pad: "verbruik", label: "Verbruik", groep: "persoonlijk", alleenBeheerder: false,
    trefwoorden: ["tokens", "budget", "tegoed"] },
  { key: "gesprekken", pad: "gesprekken", label: "Gesprekken", groep: "persoonlijk", alleenBeheerder: false,
    trefwoorden: ["archief", "opruimen", "verwijderen"] },
  { key: "berichten", pad: "berichten", label: "Berichten", groep: "persoonlijk", alleenBeheerder: false,
    trefwoorden: ["nieuws", "updates", "meldingen"] },
  { key: "rondleiding", pad: "rondleiding", label: "Rondleiding", groep: "persoonlijk", alleenBeheerder: false,
    trefwoorden: ["uitleg", "tour", "help"] },
  { key: "methodes", pad: "aanpassingen/methodes", label: "Methodes", groep: "aanpassingen", alleenBeheerder: false,
    trefwoorden: ["skills", "skill", "methode", "jas", "jrm", "wetsanalyse", "wetsuitvoering", "werkwijze", "concept"] },
  { key: "agents", pad: "aanpassingen/agents", label: "Agents", groep: "aanpassingen", alleenBeheerder: false,
    trefwoorden: ["subagents", "agentprofielen", "profiel", "specialist", "werkwijze", "concept"] },
  // Voor iedereen te lezen; aan- en uitzetten blijft beheer (de BFF houdt `/api/admin/connectors` dicht).
  { key: "connectors", pad: "aanpassingen/connectors", label: "Connectors", groep: "aanpassingen", alleenBeheerder: false,
    trefwoorden: ["bronnen", "kamerstukken", "rechtspraak", "bekendmakingen", "mcp"], vroeger: ["beheer/connectors"] },
  { key: "modellen", pad: "beheer/modelprofielen", label: "Modellen", groep: "aanpassingen", alleenBeheerder: true,
    trefwoorden: ["modelprofielen", "model", "api-sleutel", "endpoint", "llm"], vroeger: ["modelprofielen"] },
  { key: "gebruikers", pad: "beheer/gebruikers", label: "Gebruikers", groep: "beheer", alleenBeheerder: true,
    trefwoorden: ["accounts", "rollen", "analist", "beheerder", "budget"] },
  { key: "registraties", pad: "beheer/registraties", label: "Aanvragen", groep: "beheer", alleenBeheerder: true,
    trefwoorden: ["registraties", "zelfregistratie", "goedkeuren"] },
  { key: "api-tokens", pad: "beheer/api-tokens", label: "API-tokens", groep: "beheer", alleenBeheerder: true,
    trefwoorden: ["tokens", "mcp", "toegang"] },
  { key: "berichtenbeheer", pad: "beheer/berichten", label: "Berichten beheren", groep: "beheer", alleenBeheerder: true,
    trefwoorden: ["publiceren", "nieuws", "updates"] },
  { key: "feedback", pad: "beheer/feedback", label: "Feedback", groep: "beheer", alleenBeheerder: true,
    trefwoorden: ["meldingen", "verbeteringen", "fouten"] },
] as const satisfies readonly TabDefinitie[];

export type TabKey = (typeof INSTELLINGEN_TABS)[number]["key"];

/** De tab bij een sleutel of pad, ook een oude. */
function vind(waarde: string): (typeof INSTELLINGEN_TABS)[number] | undefined {
  return INSTELLINGEN_TABS.find((t: TabDefinitie) => t.key === waarde || t.pad === waarde || (t.vroeger ?? []).includes(waarde));
}

/** Pad-segmenten (`["beheer","gebruikers"]`) → tabsleutel. Onbekend of leeg → `account`. */
export function tabUitPad(segmenten: string[] | undefined): TabKey {
  return vind((segmenten ?? []).join("/"))?.key ?? "account";
}

/** De parameter waarmee het venster openstaat. */
export const INSTELLINGEN_PARAM = "instellingen";

/** De waarde van `?instellingen=` → tabsleutel; zonder parameter `null` (het venster is dicht). Een onbekende waarde
 *  opent op `account`, zodat een verouderde link het venster niet stil dicht laat. */
export function tabUitParam(waarde: string | null | undefined): TabKey | null {
  if (waarde == null) return null;
  return vind(waarde)?.key ?? "account";
}

/** Waar een oude link naar `/instellingen/…`, `/account` of `/beheer` heen gaat: de werkplek met het venster open. */
export function instellingenOpWerkplek(key: TabKey): string {
  return `/workbench?${INSTELLINGEN_PARAM}=${key}`;
}

/** Is deze tab alleen voor beheerders? Het venster toont hem dan alleen aan een beheerder; de BFF houdt het beheer
 *  hoe dan ook dicht. */
export function isAdminTab(key: TabKey): boolean {
  return INSTELLINGEN_TABS.find((t) => t.key === key)?.alleenBeheerder ?? false;
}

/** De tabs die bij een zoekterm horen: elk woord staat in het label of een trefwoord. Zonder zoekterm: alle. */
export function tabsBijZoekterm<T extends { label: string; trefwoorden: readonly string[] }>(tabs: readonly T[], term: string): T[] {
  const woorden = term.toLowerCase().split(/\s+/).filter(Boolean);
  if (woorden.length === 0) return [...tabs];
  return tabs.filter((t) => {
    const tekst = [t.label, ...t.trefwoorden].join(" ").toLowerCase();
    return woorden.every((w) => tekst.includes(w));
  });
}
