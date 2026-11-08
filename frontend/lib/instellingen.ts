/** Tabdefinities van het instellingenvenster + de pure helpers.
 *
 *  Het venster is altijd een pop-up over de pagina waar je bent, net als in Slack: het hangt aan de parameter
 *  `?instellingen=<tab>`, niet aan een eigen pagina. Een oude link naar `/instellingen/…` stuurt door naar de werkplek
 *  met het venster open.
 *
 *  Bewust een eigen module **zonder** `"use client"`: de doorverwijzing (een server component) gebruikt `tabUitPad`.
 *  Stond die in een client-bestand, dan faalt de server-aanroep met "Attempted to call tabUitPad() from the server but
 *  tabUitPad is on the client". */

export const INSTELLINGEN_TABS = [
  { key: "account", pad: "account", label: "Account", admin: false },
  { key: "beveiliging", pad: "beveiliging", label: "Beveiliging", admin: false },
  { key: "verbruik", pad: "verbruik", label: "Verbruik", admin: false },
  { key: "berichten", pad: "berichten", label: "Berichten", admin: false },
  { key: "rondleiding", pad: "rondleiding", label: "Rondleiding", admin: false },
  { key: "modelprofielen", pad: "beheer/modelprofielen", label: "Modelprofielen", admin: true },
  { key: "gebruikers", pad: "beheer/gebruikers", label: "Gebruikers", admin: true },
  { key: "registraties", pad: "beheer/registraties", label: "Aanvragen", admin: true },
  { key: "api-tokens", pad: "beheer/api-tokens", label: "API-tokens", admin: true },
  { key: "connectors", pad: "beheer/connectors", label: "Connectors", admin: true },
  { key: "berichtenbeheer", pad: "beheer/berichten", label: "Berichten beheren", admin: true },
  { key: "feedback", pad: "beheer/feedback", label: "Feedback", admin: true },
] as const;

export type TabKey = (typeof INSTELLINGEN_TABS)[number]["key"];

/** Pad-segmenten (`["beheer","gebruikers"]`) → tabsleutel. Onbekend of leeg → `account`. */
export function tabUitPad(segmenten: string[] | undefined): TabKey {
  const pad = (segmenten ?? []).join("/");
  return INSTELLINGEN_TABS.find((t) => t.pad === pad)?.key ?? "account";
}

/** De parameter waarmee het venster openstaat. */
export const INSTELLINGEN_PARAM = "instellingen";

/** De waarde van `?instellingen=` → tabsleutel; zonder parameter `null` (het venster is dicht). Een onbekende waarde
 *  opent op `account`, zodat een verouderde link het venster niet stil dicht laat. */
export function tabUitParam(waarde: string | null | undefined): TabKey | null {
  if (waarde == null) return null;
  return INSTELLINGEN_TABS.find((t) => t.key === waarde || t.pad === waarde)?.key ?? "account";
}

/** Waar een oude link naar `/instellingen/…`, `/account` of `/beheer` heen gaat: de werkplek met het venster open. */
export function instellingenOpWerkplek(key: TabKey): string {
  return `/workbench?${INSTELLINGEN_PARAM}=${key}`;
}

/** Is deze tab alleen voor beheerders? Het venster toont hem dan alleen aan een beheerder; de BFF houdt het beheer
 *  hoe dan ook dicht. */
export function isAdminTab(key: TabKey): boolean {
  return INSTELLINGEN_TABS.find((t) => t.key === key)?.admin ?? false;
}
