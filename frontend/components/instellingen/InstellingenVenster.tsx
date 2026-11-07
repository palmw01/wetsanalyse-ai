"use client";

import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { INSTELLINGEN_PARAM, isAdminTab, tabUitParam } from "@/lib/instellingen";
import { InstellingenDialog } from "./InstellingenDialog";

/** Het instellingenvenster op elke pagina: open zolang `?instellingen=` in de URL staat. Ook na herladen of via een
 *  link, en dus nooit een losse pagina. Alleen voor wie is ingelogd; een beheer-tab opent voor een analist op `account`. */
export function InstellingenVenster() {
  const tab = tabUitParam(useSearchParams().get(INSTELLINGEN_PARAM));
  const { data: session, status } = useSession();
  if (!tab || status !== "authenticated") return null;
  const isBeheerder = session?.user?.role === "beheerder";
  return <InstellingenDialog actief={isAdminTab(tab) && !isBeheerder ? "account" : tab} isBeheerder={isBeheerder} />;
}
