import { WerkplekVenster } from "@/components/werkplek/WerkplekVenster";

/** Wat het `children`-slot toont zodra de router de vorige entry niet meer kan hergebruiken.
 *
 *  De root-layout heeft twee slots: `children` (de pagina) en `modal` (de intercepting routes onder
 *  `app/@modal/**`). Staat er een dialog open – je bent vanuit de werkplek naar `/instellingen/…`
 *  genavigeerd – dan blijft de werkplek in de children-branch staan zolang de router die entry kan
 *  hergebruiken. Verloopt hij (de client-router-cache houdt dynamische pagina's niet vast) en volgt
 *  er een navigatie, bijvoorbeeld een tabwissel in de dialog, dan moet de branch opnieuw worden
 *  opgelost. Zonder deze `default` is er dan niets om te renderen: het slot blijft leeg, de dialog
 *  blijft staan en je kijkt door de half-transparante backdrop naar het kale witte document.
 *
 *  Vandaar de werkplek als terugval, en niet `null` zoals in `app/@modal/default.tsx`: de werkplek
 *  ís de app – `app/page.tsx` leidt er ook naartoe. Opende je de dialog vanaf een andere pagina, dan
 *  staat hier de werkplek in plaats van die pagina; bij het sluiten brengt `router.back()` je alsnog
 *  terug naar de echte URL, mét querystring. */
export default function RootDefault() {
  return <WerkplekVenster />;
}
