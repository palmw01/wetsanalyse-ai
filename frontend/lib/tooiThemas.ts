// De thema's van TOOI tooitop (spoor I6), als keuze voor een werkgebied. Een kopie van
// `api/app/tooi_themas.json`; `tooiThemas.test.ts` bewaakt dat ze niet afdrijft.
import data from "./tooi-themas.json";

export interface Thema { uri: string; label: string; breder: string | null }

const ALLE: Thema[] = Object.entries(data.themas as Record<string, { label: string; breder: string | null }>)
  .map(([uri, t]) => ({ uri, label: t.label, breder: t.breder }));

const isHoofd = (t: Thema) => !t.breder || t.breder.endsWith("/toplijst");

/** Per hoofdthema zijn subthema's, alfabetisch: de vorm van de keuzelijst (`optgroup`). */
export function themaGroepen(): { hoofd: Thema; subs: Thema[] }[] {
  return ALLE.filter(isHoofd).sort((a, b) => a.label.localeCompare(b.label, "nl"))
    .map((hoofd) => ({ hoofd, subs: ALLE.filter((t) => t.breder === hoofd.uri).sort((a, b) => a.label.localeCompare(b.label, "nl")) }));
}

export function themaLabel(uri: string | undefined | null): string {
  return ALLE.find((t) => t.uri === uri)?.label ?? "";
}
