// Het verschil tussen twee teksten per regel, voor het vergelijken van twee versies (ADR-016 §B7). Zuiver en zonder
// afhankelijkheid: de langste gemeenschappelijke reeks regels, met het gelijke begin en eind er eerst af.

export type RegelSoort = "gelijk" | "erbij" | "weg";

export interface VerschilRegel {
  soort: RegelSoort;
  tekst: string;
  /** Het regelnummer in de oude en in de nieuwe tekst (1 = de eerste regel); `null` waar de regel niet bestaat. */
  oud: number | null;
  nieuw: number | null;
}

export interface Tekstverschil {
  regels: VerschilRegel[];
  erbij: number;
  weg: number;
  /** De teksten waren te lang om regel voor regel te vergelijken: het midden staat als één blok weg en één blok erbij. */
  grof: boolean;
}

/** Boven dit aantal cellen (regels oud × regels nieuw, na het gelijke begin en eind) wordt het midden niet uitgerekend. */
export const MAX_CELLEN = 4_000_000;

function splits(tekst: string): string[] {
  if (tekst === "") return [];
  const regels = tekst.replace(/\r\n/g, "\n").split("\n");
  // Een afsluitende regelovergang is geen lege laatste regel.
  if (regels.at(-1) === "") regels.pop();
  return regels;
}

export function tekstverschil(oud: string, nieuw: string, maxCellen = MAX_CELLEN): Tekstverschil {
  const a = splits(oud), b = splits(nieuw);
  let begin = 0;
  while (begin < a.length && begin < b.length && a[begin] === b[begin]) begin++;
  let eind = 0;
  while (eind < a.length - begin && eind < b.length - begin && a[a.length - 1 - eind] === b[b.length - 1 - eind]) eind++;
  const n = a.length - begin - eind, m = b.length - begin - eind;

  const regels: VerschilRegel[] = [];
  for (let i = 0; i < begin; i++) regels.push({ soort: "gelijk", tekst: a[i], oud: i + 1, nieuw: i + 1 });
  const weg = (i: number) => regels.push({ soort: "weg", tekst: a[begin + i], oud: begin + i + 1, nieuw: null });
  const erbij = (j: number) => regels.push({ soort: "erbij", tekst: b[begin + j], oud: null, nieuw: begin + j + 1 });

  const grof = n * m > maxCellen;
  if (grof) {
    for (let i = 0; i < n; i++) weg(i);
    for (let j = 0; j < m; j++) erbij(j);
  } else if (n > 0 || m > 0) {
    // lengte[i][j] = de langste gemeenschappelijke reeks van a[i..] en b[j..], in één platte tabel.
    const breed = m + 1;
    const lengte = new Uint32Array((n + 1) * breed);
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        lengte[i * breed + j] = a[begin + i] === b[begin + j]
          ? lengte[(i + 1) * breed + j + 1] + 1
          : Math.max(lengte[(i + 1) * breed + j], lengte[i * breed + j + 1]);
      }
    }
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[begin + i] === b[begin + j]) {
        regels.push({ soort: "gelijk", tekst: a[begin + i], oud: begin + i + 1, nieuw: begin + j + 1 });
        i++; j++;
      } else if (lengte[(i + 1) * breed + j] >= lengte[i * breed + j + 1]) weg(i++);
      else erbij(j++);
    }
    while (i < n) weg(i++);
    while (j < m) erbij(j++);
  }
  for (let k = 0; k < eind; k++) {
    regels.push({ soort: "gelijk", tekst: a[a.length - eind + k], oud: a.length - eind + k + 1, nieuw: b.length - eind + k + 1 });
  }
  return { regels, erbij: regels.filter((r) => r.soort === "erbij").length, weg: regels.filter((r) => r.soort === "weg").length, grof };
}

export type Blok = { soort: "regels"; regels: VerschilRegel[] } | { soort: "gelijk"; regels: VerschilRegel[] };

/** Het verschil in blokken: wat veranderde met `context` gelijke regels eromheen; een langere gelijke reeks is één
 *  blok dat de weergave inklapt. Zonder verschil is er één gelijk blok (of geen, bij twee lege teksten). */
export function blokken(regels: VerschilRegel[], context = 3): Blok[] {
  const tonen = new Array<boolean>(regels.length).fill(false);
  regels.forEach((r, i) => {
    if (r.soort === "gelijk") return;
    for (let k = Math.max(0, i - context); k <= Math.min(regels.length - 1, i + context); k++) tonen[k] = true;
  });
  const uit: Blok[] = [];
  regels.forEach((r, i) => {
    const soort = tonen[i] ? "regels" : "gelijk";
    const laatste = uit.at(-1);
    if (laatste?.soort === soort) laatste.regels.push(r);
    else uit.push({ soort, regels: [r] });
  });
  return uit;
}

/** "3 regels erbij, 1 regel weg", of "geen verschil". */
export function verschilZin(v: Pick<Tekstverschil, "erbij" | "weg">): string {
  if (!v.erbij && !v.weg) return "geen verschil";
  const regel = (n: number) => (n === 1 ? "1 regel" : `${n} regels`);
  return [v.erbij && `${regel(v.erbij)} erbij`, v.weg && `${regel(v.weg)} weg`].filter(Boolean).join(", ");
}
