/** Alleen de exacte ontwikkelroute mag zonder account worden geopend. */
export function graafMockAan(): boolean {
  return process.env.NODE_ENV === "development" && process.env.GRAAF_MOCK === "1";
}
