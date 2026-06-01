/**
 * @file Data-driven navigation bar.
 *
 * Populates every `#navbar` on the page with links to Home, Upload, and each
 * process in the configured pipeline (fetched from `/api/schema`), so the nav
 * reflects the real, user-configured pipeline order rather than a hard-coded list.
 */
import { getPipeline } from "./api.js";

/**
 * Map a process name to its page route (e.g. "Post-Process" -> "/postprocess").
 * @param {string} processName
 * @returns {string}
 */
export function routeFor(processName) {
  return "/" + processName.toLowerCase().replace(/[^a-z0-9]/g, "");
}

/**
 * Build the navigation bar(s). If the pipeline cannot be fetched, the nav
 * degrades gracefully to the static Home/Upload links.
 * @returns {Promise<void>}
 */
export async function buildNav() {
  const bars = document.querySelectorAll("#navbar");
  if (!bars.length) return;

  /** @type {Array<[string, string]>} */
  const items = [
    ["Home", "/"],
    ["Upload", "/upload"],
  ];
  try {
    const { order } = await getPipeline();
    for (const name of order) items.push([name, routeFor(name)]);
  } catch {
    /* keep the base links if the pipeline cannot be reached */
  }
  // Colour combination is a terminal step parallel to the pipeline (not in ORDER),
  // so it is appended explicitly after the process pages.
  items.push(["Color", "/color"]);

  for (const bar of bars) {
    bar.replaceChildren();
    for (const [label, href] of items) {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      link.className = "nav-link";
      if (window.location.pathname === href) {
        link.setAttribute("aria-current", "page");
      }
      bar.appendChild(link);
    }
  }
}
