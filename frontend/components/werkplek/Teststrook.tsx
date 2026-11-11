"use client";

import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { useSession } from "next-auth/react";

import { IcoonKnop } from "@/components/ui/Button";
import { Kruis } from "@/components/ui/Icoon";
import { bewaarWeggeklikt, leesWeggeklikt, strookWeggeklikt, TESTSTROOK_SLEUTEL } from "@/lib/teststrook";

// Eén tab volgt een wegklik in een andere via het `storage`-event; in dezelfde tab via dit eigen event.
const WEGGEKLIKT = "wa-teststrook-weggeklikt";

function abonneer(melding: () => void): () => void {
  const opOpslag = (e: StorageEvent) => {
    if (e.key === null || e.key === TESTSTROOK_SLEUTEL) melding();
  };
  window.addEventListener("storage", opOpslag);
  window.addEventListener(WEGGEKLIKT, melding);
  return () => {
    window.removeEventListener("storage", opOpslag);
    window.removeEventListener(WEGGEKLIKT, melding);
  };
}

/** `undefined` op de server en tijdens de hydratatie: dan is nog niet bekend of hij weg moet. */
const opDeServer = (): string | null | undefined => undefined;

/** De strook "Testomgeving – proof of concept" bovenaan de schil, met een kruisje om hem weg te klikken
 *  voor de rest van deze login (zie `lib/teststrook.ts`). De voorwaarden blijven daarna bereikbaar via
 *  het gebruikersmenu.
 *
 *  Pas na de hydratatie zichtbaar: de server kent `localStorage` niet, en wie hem al wegklikte zou hem
 *  anders bij elke pagina even zien opflitsen. Geen Escape: het is geen dialog of laag, en Escape pelt
 *  in de werkplek al panelen en selecties af. */
export function Teststrook() {
  const { data: session } = useSession();
  const sleutel = session?.user?.loginSleutel;
  const opgeslagen = useSyncExternalStore<string | null | undefined>(abonneer, leesWeggeklikt, opDeServer);
  // Lukt bewaren niet (geblokkeerde opslag), dan geldt het wegklikken alleen voor deze pagina.
  const [nuWeg, setNuWeg] = useState(false);

  if (opgeslagen === undefined || nuWeg || strookWeggeklikt(opgeslagen, sleutel)) return null;

  function verberg() {
    if (sleutel) {
      bewaarWeggeklikt(sleutel);
      window.dispatchEvent(new Event(WEGGEKLIKT));
    }
    setNuWeg(true);
  }

  return (
    <div data-teststrook className="flex shrink-0 items-center bg-waarschuwing/10 text-ink">
      {/* De klik opent de voorwaarden als dialog (intercepting route), zodat je je gesprek niet verlaat. */}
      <Link
        href="/disclaimer"
        className="focus-ring block min-w-0 flex-1 py-1 pl-8 text-center text-[0.7rem] transition-colors hover:bg-waarschuwing/20"
      >
        <span className="font-semibold">Testomgeving – proof of concept.</span>{" "}
        Analyses kunnen verloren gaan. <span className="underline">Lees de voorwaarden</span>
      </Link>
      <IcoonKnop
        aria-label="Melding testomgeving verbergen"
        title="Melding testomgeving verbergen"
        onClick={verberg}
        className="mx-1 border-transparent bg-transparent"
      >
        <Kruis className="h-3 w-3" />
      </IcoonKnop>
    </div>
  );
}
