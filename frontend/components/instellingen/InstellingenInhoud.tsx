"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AccountClient } from "@/components/account/AccountClient";
import { PasswordPanel } from "@/components/account/PasswordPanel";
import { VerbruikPanel } from "@/components/account/VerbruikPanel";
import { ApiTokensPanel } from "@/components/admin/ApiTokensPanel";
import { BerichtenBeheerPanel } from "@/components/admin/BerichtenBeheerPanel";
import { FeedbackLijstClient } from "@/components/admin/FeedbackLijstClient";
import { BerichtenArchiefClient } from "@/components/berichten/BerichtenArchiefClient";
import { ProfielenPanel } from "@/components/admin/ProfielenPanel";
import { RegistratiesPanel } from "@/components/admin/RegistratiesPanel";
import { UsersPanel } from "@/components/admin/UsersPanel";
import { Tabs, type TabDef } from "@/components/ui/Tabs";
import { getOngelezenFeedbackAantal, listRegistraties } from "@/lib/api";
import { INSTELLINGEN_TABS, padVanTab, type TabKey } from "@/lib/instellingen";

const PANEEL: Record<TabKey, React.ReactNode> = {
  account: <PasswordPanel />,
  beveiliging: <AccountClient />,
  verbruik: <VerbruikPanel />,
  modelprofielen: <ProfielenPanel />,
  gebruikers: <UsersPanel />,
  registraties: <RegistratiesPanel />,
  "api-tokens": <ApiTokensPanel />,
  berichten: <BerichtenArchiefClient />,
  berichtenbeheer: <BerichtenBeheerPanel />,
  feedback: <FeedbackLijstClient />,
};

interface Props {
  actief: TabKey;
  isBeheerder: boolean;
  /** In de dialog wisselen we van tab met `replace` (geen extra history-entry per tab, zodat de
   *  back-knop de dialog sluit i.p.v. door de tabs terug te lopen). Op de volle pagina `push`. */
  vervangHistorie?: boolean;
}

/** De inhoud van het instellingenvenster: tabkolom links, paneel rechts. Wordt gedeeld door de
 *  dialog (vanuit de werkplek) en de volledige pagina (directe link/refresh), zodat beide dezelfde
 *  panelen tonen. */
export function InstellingenInhoud({ actief, isBeheerder, vervangHistorie = false }: Props) {
  const router = useRouter();
  const [ongelezenFeedback, setOngelezenFeedback] = useState(0);
  const [openAanvragen, setOpenAanvragen] = useState(0);
  const zichtbaar = INSTELLINGEN_TABS.filter((t) => !t.admin || isBeheerder);

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

  const tabs: TabDef[] = zichtbaar.map((t) => ({
    key: t.key,
    label: t.label,
    content: PANEEL[t.key],
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
      onChange={(key) => {
        const pad = padVanTab(key as TabKey);
        if (vervangHistorie) router.replace(pad);
        else router.push(pad);
      }}
    />
  );
}
