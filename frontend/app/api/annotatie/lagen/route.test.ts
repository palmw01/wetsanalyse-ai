import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

process.env.API_BASE_URL = "http://api.test";
process.env.API_TOKEN = "test-token";

vi.mock("@/app/api/_lib/session", () => ({
  sessionUserId: async () => "gebruiker-a",
  geenSessie: () => Response.json({ detail: "Niet ingelogd." }, { status: 401 }),
}));

let GET: typeof import("./route").GET;

beforeAll(async () => {
  ({ GET } = await import("./route"));
});

afterEach(() => vi.unstubAllGlobals());

describe("lagen-route", () => {
  it("stuurt alle query-parameters door, met de identiteit uit de sessie", async () => {
    // Een parameter die hier sneuvelt faalt stil: dan toont "Door mij bewerkt" gewoon alles.
    const upstream = vi.fn((_url: string, _init?: RequestInit) =>
      Promise.resolve(Response.json([])),
    );
    vi.stubGlobal("fetch", upstream);

    await GET(new Request("http://app.test/api/annotatie/lagen?mijn=true&bwbId=BWBR0004770&limit=50"));

    const [url, init] = upstream.mock.calls[0];
    expect(url).toBe("http://api.test/v1/annotatie/lagen?mijn=true&bwbId=BWBR0004770&limit=50");
    expect(new Headers(init?.headers).get("X-User-Id")).toBe("gebruiker-a");
  });
});
