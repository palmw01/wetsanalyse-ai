/**
 * Uit welke checkout deze MCP draait (Termijnen e2e, 20 nov 2026). De registratie is machine-lokaal en wijst naar
 * `dist/` van de checkout waarin Claude Code start. Stond die op een oudere branch, dan draaide het team met oude tools:
 * `bron_lezen` las de Leidraad 9.x niet en het agenttype van de regelspecialist ontbrak, terwijl beide op master al
 * klopten. `wie_ben_ik` zegt het nu, zodat de coördinator het vóór de run ziet.
 */
import { execFileSync } from "node:child_process";

export type Git = (args: string[]) => string;

export interface CheckoutStand {
  branch: string;
  commit: string;
  /** Hoeveel commits `origin/master` (zoals hij hier laatst gehaald is) vóór ligt; `null` als dat niet te zeggen is. */
  achter_op_master: number | null;
  waarschuwing?: string;
}

export function gitIn(repo: string): Git {
  return (args) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8", timeout: 5000 }).trim();
}

export function checkoutStand(git: Git): CheckoutStand {
  const lees = (args: string[]): string => {
    try {
      return git(args);
    } catch {
      return "";
    }
  };
  const branch = lees(["rev-parse", "--abbrev-ref", "HEAD"]);
  const commit = lees(["rev-parse", "--short", "HEAD"]);
  const achter = lees(["rev-list", "--count", "HEAD..origin/master"]);
  const n = /^\d+$/.test(achter) ? Number(achter) : null;
  const uit: CheckoutStand = { branch, commit, achter_op_master: n };
  if (n !== null && n > 0) {
    uit.waarschuwing =
      `Deze MCP draait uit ${branch || "een checkout"} (${commit}), ${n} commit(s) achter origin/master: tools en ` +
      "agenttypes kunnen verouderd zijn. Start het team vanuit een checkout op master.";
  }
  return uit;
}
