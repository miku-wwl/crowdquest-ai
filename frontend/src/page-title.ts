const titles: Record<string, string> = {
  "/": "CrowdQuest AI · Director Dashboard",
  "/broadcast-studio": "CrowdQuest AI · Broadcast Studio",
  "/overlay": "CrowdQuest AI · Overlay",
  "/obs-admin": "CrowdQuest AI · OBS Admin",
};

export function titleForPathname(pathname: string): string {
  return titles[pathname] || "CrowdQuest AI";
}
