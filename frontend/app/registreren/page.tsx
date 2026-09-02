import { AuthFrame } from "@/components/auth/AuthFrame";
import { RegistratieClient } from "@/components/auth/RegistratieClient";

export const metadata = { title: "Toegang aanvragen · Wetsanalyse" };

export default function RegistrerenPagina() {
  // Bewust geen setup-check zoals /setup: het aanvraagformulier blijft altijd open. Is er nog geen
  // enkel account, dan is er ook nog geen beheerder die kan goedkeuren – maar de aanvraag blijft
  // gewoon liggen tot de eerste beheerder er is.
  return (
    <AuthFrame
      titel="Toegang aanvragen"
      onderschrift="Vul je gegevens in. Een beheerder beoordeelt je aanvraag; daarna kun je inloggen met de gebruikersnaam die je hieronder krijgt en het wachtwoord dat je nu kiest."
    >
      <RegistratieClient />
    </AuthFrame>
  );
}
