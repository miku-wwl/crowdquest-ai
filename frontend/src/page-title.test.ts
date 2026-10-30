import { describe, expect, it } from "vitest";
import { titleForPathname } from "./page-title";

describe("route titles", () => {
  it.each([
    ["/", "CrowdQuest AI · Director Dashboard"],
    ["/broadcast-studio", "CrowdQuest AI · Broadcast Studio"],
    ["/overlay", "CrowdQuest AI · Overlay"],
    ["/obs-admin", "CrowdQuest AI · OBS Admin"],
  ])("uses the product title for %s", (pathname, title) => {
    expect(titleForPathname(pathname)).toBe(title);
  });

  it("uses a neutral title for unrecognized routes", () => {
    expect(titleForPathname("/unknown")).toBe("CrowdQuest AI");
  });
});
