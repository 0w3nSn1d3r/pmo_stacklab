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
 */
import { getProcessSchema, runProcess } from "./api.js";
import { buildNav } from "./nav.js";
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

  // Post-Process output is already display-ready (the user's own stretch made it),
  // so its preview is shown as-is without the display-stretch controls.
  const displayControls = processName !== "Post-Process";

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
  runBtn.addEventListener("click", async () => {
    /** @type {Object<string, import("./api.js").SubprocessChoice>} */
    const configs = {};
    for (const menu of menus) configs[menu.subprocessName] = menu.value;

    runBtn.disabled = true;
    setResult(resultEl, "Running...");
    try {
      await runProcess(processName, configs);
      setResult(resultEl, "");
      if (previewEl) await showPreview(previewEl, processName, { displayControls });
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
    } finally {
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
