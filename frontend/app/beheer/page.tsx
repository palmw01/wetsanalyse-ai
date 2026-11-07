import { redirect } from "next/navigation";
import { instellingenOpWerkplek } from "@/lib/instellingen";

/** Beheer is opgegaan in het instellingenvenster. Deze route blijft als doorverwijzing bestaan; de rolgate zit in
 *  `auth.config.ts`, en het venster toont de beheer-tabs alleen aan een beheerder. */
export default function BeheerPagina() {
  redirect(instellingenOpWerkplek("modelprofielen"));
}
