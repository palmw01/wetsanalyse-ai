"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AccountClient } from "@/components/account/AccountClient";
import { GesprekkenPanel } from "@/components/account/GesprekkenPanel";
import { PasswordPanel } from "@/components/account/PasswordPanel";
import { RondleidingPanel } from "@/components/account/RondleidingPanel";
import { VerbruikPanel } from "@/components/account/VerbruikPanel";
import { ApiTokensPanel } from "@/components/admin/ApiTokensPanel";
import { BerichtenBeheerPanel } from "@/components/admin/BerichtenBeheerPanel";
import { ConnectorsPanel } from "@/components/admin/ConnectorsPanel";
import { FeedbackLijstClient } from "@/components/admin/FeedbackLijstClient";
import { BerichtenArchiefClient } from "@/components/berichten/BerichtenArchiefClient";
import { ProfielenPanel } from "@/components/admin/ProfielenPanel";
import { RegistratiesPanel } from "@/components/admin/RegistratiesPanel";
import { UsersPanel } from "@/components/admin/UsersPanel";
import { Button } from "@/components/ui/Button";
import { Melding } from "@/components/ui/Melding";
import { Tabs, type TabDef } from "@/components/ui/Tabs";
import { getAccount, getOngelezenFeedbackAantal, listRegistraties } from "@/lib/api";
import { INSTELLINGEN_GROEPEN, INSTELLINGEN_TABS, tabsBijZoekterm, type TabKey } from "@/lib/instellingen";
import { kiesInstellingenTab } from "@/lib/instellingenVenster";

const PANEEL: Record<TabKey, React.ReactNode> = {
  account: <PasswordPanel />,
  beveiliging: <AccountClient />,
  verbruik: <VerbruikPanel />,
  gesprekken: <GesprekkenPanel />,
  rondleiding: <RondleidingPanel />,
  modellen: <ProfielenPanel />,
  gebruikers: <UsersPanel />,
  registraties: <RegistratiesPanel />,
  "api-tokens": <ApiTokensPanel />,
  connectors: <ConnectorsPanel />,
  berichten: <BerichtenArchiefClient />,
  berichtenbeheer: <BerichtenBeheerPanel />,
  feedback: <FeedbackLijstClient />,
};

/** Staat op de beheertabs van een beheerder zonder 2FA, in plaats van een paneel vol 403's. */
function BeheerVraagt2fa({ onNaarBeveiliging }: { onNaarBeveiliging: () => void }) {
  return (
    <Melding type="waarschuwing" titel="Koppel eerst tweestapsverificatie">
      <p className="mb-2 text-sm">
        Het beheer gaat pas open als er een authenticator-app aan je account hangt. De rest van de app werkt gewoon.
      </p>
      <Button size="sm" variant="secondary" onClick={onNaarBeveiliging}>Naar Beveiliging</Button>
    </Melding>
  );
}

interface Props {
  actief: TabKey;
  isBeheerder: boolean;
}

/** De inhoud van het instellingenvenster: tabkolom links met een zoekveld en de groepen (*Persoonlijk*, *Aanpassingen*,
 *  *Beheer*), paneel rechts. De actieve tab komt uit `?instellingen=` (`InstellingenVenster`). */
export function InstellingenInhoud({ actief, isBeheerder }: Props) {
  const [ongelezenFeedback, setOngelezenFeedback] = useState(0);
  const [openAanvragen, setOpenAanvragen] = useState(0);
  const [tfaNodig, setTfaNodig] = useState(false);
  const [zoekterm, setZoekterm] = useState("");
  // De volgorde van de groepen, en daarbinnen die van `INSTELLINGEN_TABS`.
  const zichtbaar = useMemo(() => INSTELLINGEN_GROEPEN.flatMap((g) =>
    INSTELLINGEN_TABS.filter((t) => t.groep === g.key && (!t.alleenBeheerder || isBeheerder))), [isBeheerder]);
  const gevonden = useMemo(() => new Set<string>(tabsBijZoekterm(zichtbaar, zoekterm).map((t) => t.key)), [zichtbaar, zoekterm]);

  // Opnieuw bij elke tabwissel: wie net gekoppeld heeft, loopt zo meteen door naar het beheer. Stil
  // falend: de melding is uitleg, de BFF houdt het beheer hoe dan ook dicht.
  useEffect(() => {
    if (!isBeheerder) return;
    let weg = false;
    getAccount()
      .then((a) => { if (!weg) setTfaNodig(a.tfa_nodig); })
      .catch(() => {});
    return () => { weg = true; };
  }, [actief, isBeheerder]);

  // Ongelezen-teller voor de feedbacktab. Alleen voor beheerders (het endpoint eist die rol) en
  // stil falend: een hapering mag het venster niet blokkeren, de badge is een hint.
  const laadFeedbackTeller = useCallback(async () => {
    if (!isBeheerder) return;
    try {
      setOngelezenFeedback(await getOngelezenFeedbackAantal());
    } catch {
      /* badge blijft staan zoals hij was */
    }
  }, [isBeheerder]);

  // Openstaande aanvragen voor de badge op de aanvragen-tab. Zelfde vorm als hierboven: alleen voor
  // beheerders en stil falend – de badge is een hint, geen blokkade.
  const laadAanvraagTeller = useCallback(async () => {
    if (!isBeheerder) return;
    try {
      setOpenAanvragen((await listRegistraties("aangevraagd")).length);
    } catch {
      /* badge blijft staan zoals hij was */
    }
  }, [isBeheerder]);

  // Bij het openen, en opnieuw zodra je de aanvragen-tab verlaat: daar zijn ze net beoordeeld.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (actief !== "registraties") void laadAanvraagTeller();
  }, [actief, laadAanvraagTeller]);

  // Bij het openen, en opnieuw zodra je de feedbacktab verlaat – dat paneel markeert bij openen als
  // gezien, dus de teller die we bij het laden ophaalden klopt daarna niet meer.
  useEffect(() => {
    // De setState zit ín de async callback, dus pas ná het await – geen synchrone cascading
    // render. De regel kan daar niet doorheen kijken.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (actief !== "feedback") void laadFeedbackTeller();
  }, [actief, laadFeedbackTeller]);

  // Een tab wisselt met de History API, ook vanuit de melding: geen navigatie, dus de pagina eronder blijft staan.
  function kiesTab(key: TabKey) {
    kiesInstellingenTab(key);
  }

  // De kop van een groep staat boven zijn eerste tab in de kolom, dus na het zoeken boven de eerste die overbleef.
  const eersteVanGroep = new Set(INSTELLINGEN_GROEPEN.map((g) => zichtbaar.find((t) => t.groep === g.key && gevonden.has(t.key))?.key));
  const tabs: TabDef[] = zichtbaar.map((t) => ({
    key: t.key,
    label: t.label,
    groep: eersteVanGroep.has(t.key) ? INSTELLINGEN_GROEPEN.find((g) => g.key === t.groep)?.label : undefined,
    content: t.alleenBeheerder && tfaNodig ? <BeheerVraagt2fa onNaarBeveiliging={() => kiesTab("beveiliging")} /> : PANEEL[t.key],
    badge:
      t.key === "feedback"
        ? ongelezenFeedback
        : t.key === "registraties"
          ? openAanvragen
          : undefined,
  }));

  return (
    <Tabs
      tabs={tabs}
      active={actief}
      label="Instellingen"
      orientation="vertical"
      lazy
      onChange={(key) => kiesTab(key as TabKey)}
      verborgen={new Set(zichtbaar.filter((t) => !gevonden.has(t.key)).map((t) => t.key))}
      zoek={
        <input
          type="search"
          value={zoekterm}
          onChange={(e) => setZoekterm(e.target.value)}
          // Escape wist eerst het veld; pas een leeg veld laat Escape door naar het venster, dat dan sluit.
          onKeyDown={(e) => { if (e.key === "Escape" && zoekterm) { e.stopPropagation(); setZoekterm(""); } }}
          aria-label="Zoek in instellingen"
          placeholder="Zoek in instellingen"
          maxLength={100}
          className="w-full rounded-field border border-line bg-paper px-2.5 py-1.5 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-lint focus:ring-2 focus:ring-lint/20 coarse:min-h-[44px]"
        />
      }
    />
  );
}
