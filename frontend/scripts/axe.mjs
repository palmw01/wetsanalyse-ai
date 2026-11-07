/** De toegankelijkheidstoets voor de browserscripts: axe-core op het scherm zoals het er op dat moment staat.
 *
 * frontend/CLAUDE.md belooft WCAG 2.2 AA; dit meet het deel dat een machine kan zien (contrast, namen, rollen,
 * labels, landmarks). Toetsenbord, focusvolgorde en schermlezer-aankondigingen meet axe niet – die bewaken de
 * scripts zelf met hun stappen.
 *
 * Gebruik: `await toetsToegankelijkheid(page, "werkplek")` nadat het scherm geladen is. Elke overtreding faalt,
 * ongeacht de ernst: een drempel op `impact` laat een contrastfout ("serious") net zo goed door als niets meten.
 *
 * Een uitzondering hoort hieronder, met regel en reden, en geldt voor alle schermen. Geen uitzonderingen per
 * script: dan ziet niemand meer wat er bewust openstaat.
 */
import { AxeBuilder } from "@axe-core/playwright";

export const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"];

/** Regel-id → reden. Leeg is de bedoeling. */
export const UITZONDERINGEN = {};

/** Delen van de pagina die niet van de app zijn. */
const BUITEN_DE_APP = [
  // De ontwikkelindicator en foutoverlay van `next dev`: bestaan niet in een productiebuild.
  "nextjs-portal",
];

export async function toetsToegankelijkheid(page, scherm, { binnen } = {}) {
  // Eerst de inkomende animaties (`animate-rise`: opacity 0 → 1) laten uitlopen: midden in de overgang meet
  // axe een mengkleur en meldt een contrastfout die de gebruiker nooit ziet. Oneindige animaties (spinners) niet.
  await page.evaluate(() => Promise.race([
    Promise.all(document.getAnimations()
      .filter((a) => a.effect?.getTiming().iterations !== Infinity)
      .map((a) => a.finished.catch(() => null))),
    new Promise((klaar) => setTimeout(klaar, 3000)),
  ]));
  let bouwer = new AxeBuilder({ page }).withTags(WCAG_TAGS).disableRules(Object.keys(UITZONDERINGEN));
  if (binnen) bouwer = bouwer.include(binnen);
  for (const sel of BUITEN_DE_APP) bouwer = bouwer.exclude(sel);
  const { violations } = await bouwer.analyze();
  if (violations.length === 0) return;
  const regels = violations.map((v) => {
    const plekken = v.nodes.slice(0, 5).map((n) => `      ${n.target.join(" ")}\n        ${n.failureSummary?.split("\n").slice(1).join(" ").trim()}`);
    const meer = v.nodes.length > 5 ? `\n      … en nog ${v.nodes.length - 5}` : "";
    return `  ${v.id} (${v.impact}, ${v.nodes.length}×): ${v.help}\n${plekken.join("\n")}${meer}`;
  });
  throw new Error(`Toegankelijkheid – ${scherm}: ${violations.length} WCAG-regel(s) overtreden\n${regels.join("\n")}`);
}
