/**
 * @file Controller for the process configuration pages (Calibrate, Stack, ...).
 *
 * Reads the target process from the `data-process` attribute of the `#config`
 * mount, fetches that process's schema, renders one `<config-menu>` per
 * subprocess, and -- on "Run" -- collects each menu's selection into the
 * `configs` object and POSTs it to the run endpoint, showing the result summary.
 *
 * The page is fully generic: the same script drives every process page, with the
 * process identity supplied by the template's `data-process` attribute.
 *
 * Two modes:
 *  - normal: "Run" applies the process to the session's data and previews it.
 *  - Quick Stack config (`?quickstack=1`): no frames are run; the title gains a
 *    "(Quick Stack Config)" suffix and the button becomes "Save & Continue",
 *    saving this process's choices into the Quick Stack recipe and advancing to the
 *    next process page (or back to Upload after the last). This walks the user
 *    through the pipeline purely to configure their saved defaults.
 */
import {
  getPipeline,
  getProcessSchema,
  getQuickStackConfig,
  runProcess,
  saveQuickStackConfig,
} from "./api.js";
import { buildNav } from "./nav.js";
import { routeFor } from "./nav.js";
import { showPreview } from "./preview-panel.js";
import "./config-menu.js"; // registers <config-menu> / <algo-option>

async function init() {
  buildNav();

  const mount = /** @type {HTMLElement|null} */ (
    document.querySelector("#config[data-process]")
  );
  if (!mount) return;

  const processName = mount.dataset.process || "";
  const resultEl = document.querySelector("#result");
  const previewEl = /** @type {HTMLElement|null} */ (
    document.querySelector("#preview")
  );
  const runBtn = /** @type {HTMLButtonElement|null} */ (
    document.querySelector("#run")
  );

  // Quick Stack config mode walks the user through the pipeline to set their saved
  // recipe, running no frames.
  const configMode = new URLSearchParams(window.location.search).has("quickstack");

  // Post-Process output is already display-ready (the user's own stretch made it),
  // so its preview is shown as-is without the display-stretch controls.
  const displayControls = processName !== "Post-Process";

  // The pipeline order drives both the blink "before" step and, in config mode,
  // which page comes next.
  let order = [];
  try {
    ({ order } = await getPipeline());
  } catch {
    /* tolerate an unreachable pipeline; fall back to sensible defaults below */
  }
  const idx = order.indexOf(processName);
  const beforeStep = idx > 0 ? order[idx - 1] : "Upload";

  /** @type {import("./api.js").ProcessSchema} */
  let schema;
  try {
    schema = await getProcessSchema(processName);
  } catch {
    // Processes not yet adopted into the pipeline (e.g. Reproject) 404 here --
    // say so plainly rather than showing an empty form.
    mount.textContent = `${processName} is not available yet.`;
    if (runBtn) runBtn.disabled = true;
    return;
  }

  const menus = schema.subprocesses.map((sub) => {
    const menu = /** @type {*} */ (document.createElement("config-menu"));
    menu.schema = sub;
    mount.appendChild(menu);
    return menu;
  });

  if (!runBtn) return;
  if (configMode) {
    setupConfigMode(processName, order, idx, menus, runBtn, resultEl);
    return;
  }

  runBtn.addEventListener("click", async () => {
    /** @type {Object<string, import("./api.js").SubprocessChoice>} */
    const configs = {};
    for (const menu of menus) configs[menu.subprocessName] = menu.value;

    runBtn.disabled = true;
    setResult(resultEl, "Running...");
    try {
      await runProcess(processName, configs);
      setResult(resultEl, "");
      if (previewEl) {
        await showPreview(previewEl, processName, { displayControls, beforeStep });
      }
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
    } finally {
      runBtn.disabled = false;
    }
  });
}

/**
 * Wire the page for Quick Stack config mode: suffix the title, relabel the button,
 * and on click merge this process's choices into the saved recipe and advance.
 *
 * @param {string} processName
 * @param {string[]} order - the pipeline process order.
 * @param {number} idx - this process's index in `order`.
 * @param {any[]} menus - the rendered config-menu elements.
 * @param {HTMLButtonElement} runBtn
 * @param {Element|null} resultEl
 */
function setupConfigMode(processName, order, idx, menus, runBtn, resultEl) {
  const isLast = idx === order.length - 1;

  // Title suffix, e.g. "Calibrate (Quick Stack Config)".
  const heading = document.querySelector("h1");
  if (heading) heading.textContent = `${heading.textContent} (Quick Stack Config)`;

  runBtn.textContent = isLast ? "Save & Finish" : "Save & Continue";

  runBtn.addEventListener("click", async () => {
    const processConfig = {};
    for (const menu of menus) processConfig[menu.subprocessName] = menu.value;

    runBtn.disabled = true;
    setResult(resultEl, "Saving...");
    try {
      // Merge this process's slice into the saved recipe and persist.
      const { recipe } = await getQuickStackConfig();
      recipe[processName] = processConfig;
      await saveQuickStackConfig(recipe);
      // Advance to the next process's config page, or back to Upload when done.
      const next = isLast
        ? "/upload"
        : `${routeFor(order[idx + 1])}?quickstack=1`;
      window.location.assign(next);
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
      runBtn.disabled = false;
    }
  });
}

/**
 * @param {Element|null} el
 * @param {string} text
 */
function setResult(el, text) {
  if (el) el.textContent = text;
}

document.addEventListener("DOMContentLoaded", init);
