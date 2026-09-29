// Minimale typen voor het deel van d3-force-3d dat `lib/samenhang.ts` gebruikt (het pakket levert
// er zelf geen). Dezelfde engine rekent de layout van react-force-graph-3d.
declare module "d3-force-3d" {
  export interface SimKnoop { id: string; x?: number; y?: number; z?: number; fx?: number | null; fy?: number | null; fz?: number | null }
  export interface SimLink<N> { source: string | N; target: string | N }
  export interface Kracht { (alpha: number): void }
  export interface LinkKracht<N, L> extends Kracht {
    id(f: (n: N) => string): LinkKracht<N, L>;
    distance(f: (l: L) => number): LinkKracht<N, L>;
    strength(f: number | ((l: L) => number)): LinkKracht<N, L>;
  }
  export interface LadingKracht extends Kracht { strength(s: number | ((n: SimKnoop) => number)): LadingKracht; distanceMax(d: number): LadingKracht }
  export interface Simulatie<N> {
    force(naam: string, kracht: Kracht | null): Simulatie<N>;
    tick(aantal?: number): Simulatie<N>;
    stop(): Simulatie<N>;
    nodes(): N[];
  }
  export function forceSimulation<N extends SimKnoop>(nodes: N[], dimensies?: number): Simulatie<N>;
  export function forceLink<N extends SimKnoop, L extends SimLink<N>>(links: L[]): LinkKracht<N, L>;
  export function forceManyBody(): LadingKracht;
  export function forceCenter(x?: number, y?: number, z?: number): Kracht;
}
