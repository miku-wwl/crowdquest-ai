import { createRoot } from "react-dom/client";
import { Dashboard, Overlay } from "./ui";
import { ObsAdmin } from "./obs-admin";
import { BroadcastStudio } from "./studio";
import { titleForPathname } from "./page-title";
import "./style.css";
import "./championship.css";

document.title = titleForPathname(window.location.pathname);

document.body.classList.toggle(
  "is-overlay",
  window.location.pathname === "/overlay",
);
document.documentElement.classList.toggle(
  "is-overlay",
  window.location.pathname === "/overlay",
);

createRoot(document.getElementById("root")!).render(
  window.location.pathname === "/overlay" ? (
    <Overlay />
  ) : window.location.pathname === "/broadcast-studio" ? (
    <BroadcastStudio />
  ) : window.location.pathname === "/obs-admin" ? (
    <ObsAdmin />
  ) : (
    <Dashboard />
  ),
);
