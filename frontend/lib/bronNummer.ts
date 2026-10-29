/** Nummeropmaak voor bronweergaven. Opsommingstekens zijn geen afkortingen. */
export const OPSOMMINGSTEKENS = new Set(["–", "—", "-", "•", "·", "●"]);

export function bronNummer(nummer?: string): string {
  const n = nummer?.trim() ?? "";
  if (!n || n.endsWith(".") || OPSOMMINGSTEKENS.has(n)) return n;
  return `${n}.`;
}
