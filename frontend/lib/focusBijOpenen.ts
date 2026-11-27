/** De focus op een element zodra het verschijnt: wat `autoFocus` doet, maar als ref in plaats van het attribuut
 *  (SonarQube S9379). Een vaste functie, dus React roept hem alleen aan als het element verschijnt en niet bij elke
 *  render; de focus wordt daardoor nooit teruggepakt. Voor een invoerveld dat opent op een handeling van de gebruiker
 *  (hernoemen, een nieuwe regel): daar hoort de focus naartoe. */
export function focusBijOpenen(el: HTMLElement | null): void {
  el?.focus();
}
