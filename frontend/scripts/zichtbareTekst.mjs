/**
 * De tekst van een element in het gesprek, zoals de jurist hem ziet (`innerText`), ook als de rij buiten beeld staat.
 *
 * Een rij in de thread heeft `content-visibility: auto` (`.thread-rij`, globals.css): buiten beeld slaat de browser
 * layout en paint over, en dan is `innerText` leeg. Of een rij in beeld staat, hangt af van scrollen en timing; zo faalde
 * `test-subagent.mjs` af en toe met een lege tekst. Eerst wachten tot het element er is, het in beeld scrollen en dan
 * lezen. `textContent` kan ook, maar verliest de witruimte tussen blokken waar een assert op leunt.
 */
export async function zichtbareTekst(locator) {
  await locator.waitFor();
  await locator.scrollIntoViewIfNeeded();
  return locator.innerText();
}
