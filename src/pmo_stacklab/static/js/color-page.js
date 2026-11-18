/**
 * @file Controller for the Color combination page.
 *
 * Colour combination is a terminal step parallel to the pipeline: it gives each
 * stacked filter a colour, mixes them, and tone-maps the result into one image.
 * This page fetches the schema (/api/color), renders one colour swatch per
 * available filter (pre-filled with the server's name-based guess), a luminance
 * choice, and `<config-menu>`s for the tone-map and luminance algorithms; on
 * "Combine" it POSTs the assignment and shows the resulting image.
 *
 * The assignment is per filter rather than per RGB channel because filter sets
 * are not RGB -- there may be two filters or six, and a narrowband line is one
 * colour (OIII is teal) rather than a contribution to two channels. Unticked
 * filters simply do not contribute.
 */
import {
  colorDownloadUrl,
  colorImageUrl,
  combineColor,
  getColorSchema,
} from "./api.js";
import { buildNav } from "./nav.js";
import { createInfoTip } from "./info-tip.js";
import "./config-menu.js"; // registers <config-menu>

/** Swatch colour offered for a filter the server did not assign one to. */
const UNASSIGNED_COLOR = "#808080";

async function init() {
  buildNav();

  const config = document.querySelector("#color-config");
  const resultEl = document.querySelector("#result");
  const image = /** @type {HTMLImageElement} */ (document.querySelector("#color-image"));
  const downloadMenu = document.querySelector("#color-download");
  const combineBtn = /** @type {HTMLButtonElement|null} */ (
    document.querySelector("#combine")
  );
  if (!config || !combineBtn) return;

  // Point the download links at the combined image; revealed after a combine.
  const pngLink = document.querySelector("#color-dl-png");
  const fitsLink = document.querySelector("#color-dl-fits");
  if (pngLink) pngLink.href = colorDownloadUrl("png");
  if (fitsLink) fitsLink.href = colorDownloadUrl("fits");

  let schema;
  try {
    schema = await getColorSchema();
  } catch (err) {
    // 409 until something has been stacked.
    config.textContent = `Color combination is not available yet: ${err.message}`;
    combineBtn.disabled = true;
    return;
  }

  const filterRows = buildFilterColors(config, schema);
  const lumSelect = buildLuminanceChoice(config, schema);

  // -- how each filter is put on the common scale. This is what decides whether
  // the combined background is neutral, so it is an explicit choice.
  const normMenu = /** @type {*} */ (document.createElement("config-menu"));
  normMenu.schema = schema.normalization;
  config.appendChild(normMenu);

  // -- tone-map choice (reuses the schema-driven <config-menu>)
  const menu = /** @type {*} */ (document.createElement("config-menu"));
  menu.schema = schema.combine;
  config.appendChild(menu);

  // -- how to apply the luminance frame; only meaningful once one is chosen, so
  // the menu follows that dropdown (matching the backend, which ignores the
  // block when no filter is named).
  const lumMenu = /** @type {*} */ (document.createElement("config-menu"));
  lumMenu.schema = schema.luminance;
  config.appendChild(lumMenu);

  const syncLuminance = () => {
    lumMenu.hidden = !lumSelect.value;
  };
  lumSelect.addEventListener("change", syncLuminance);
  syncLuminance();

  combineBtn.addEventListener("click", async () => {
    const colors = {};
    const gains = {};
    for (const row of filterRows) {
      if (!row.include.checked) continue;
      colors[row.filter] = row.swatch.value;
      gains[row.filter] = Number(row.gain.value);
    }
    if (!Object.keys(colors).length) {
      setResult(resultEl, "Error: assign a colour to at least one filter.");
      return;
    }

    const { algorithm, params } = menu.value;
    const luminance = lumSelect.value
      ? { filter: lumSelect.value, ...lumMenu.value }
      : undefined;

    combineBtn.disabled = true;
    setResult(resultEl, "Combining...");
    try {
      await combineColor(algorithm, params, colors, {
        gains,
        normalization: normMenu.value,
        luminance,
      });
      setResult(resultEl, "");
      image.src = colorImageUrl({ t: Date.now() });
      image.hidden = false;
      if (downloadMenu) downloadMenu.hidden = false;
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
    } finally {
      combineBtn.disabled = false;
    }
  });
}

/**
 * Render one "include + colour" row per filter.
 *
 * @param {Element} config - container to append the fieldset to.
 * @param {*} schema - the /api/color payload.
 * @returns {{filter: string, include: HTMLInputElement, swatch: HTMLInputElement}[]}
 */
function buildFilterColors(config, schema) {
  const box = document.createElement("fieldset");
  box.className = "config-menu";
  const legend = document.createElement("legend");
  legend.textContent = "Filter colours";
  legend.appendChild(
    createInfoTip(
      "Give each filter a colour, and a gain setting how strongly its signal " +
        "registers in the mix. Any number of filters can contribute; untick one " +
        "to leave it out. The gain acts on signal only -- the background stays " +
        "where the normalization put it, so turning a filter up does not tint " +
        "the sky."
    )
  );
  box.appendChild(legend);

  const rows = schema.filters.map((filt) => {
    const assigned = schema.default_colors[filt];

    const row = document.createElement("div");
    row.className = "param color-row";

    const include = document.createElement("input");
    include.type = "checkbox";
    include.checked = Boolean(assigned);

    const label = document.createElement("label");
    label.className = "param-label";
    label.append(include, document.createTextNode(" " + filt));

    const swatch = document.createElement("input");
    swatch.type = "color";
    swatch.className = "color-swatch";
    swatch.value = assigned || UNASSIGNED_COLOR;
    // Picking a colour is a statement of intent, so tick the filter for the user.
    swatch.addEventListener("input", () => {
      include.checked = true;
    });

    // Gain: how strongly this filter's signal registers in the mix. Normalization
    // equalizes the backgrounds; this is the balance control on top of it.
    const [min, max] = schema.gain_range;
    const gain = document.createElement("input");
    gain.type = "range";
    gain.className = "gain-slider";
    gain.min = String(min);
    gain.max = String(max);
    gain.step = "0.05";
    gain.value = String(schema.default_gains[filt] ?? 1);
    const readout = document.createElement("output");
    readout.className = "param-value";
    readout.textContent = Number(gain.value).toFixed(2);
    gain.addEventListener("input", () => {
      readout.textContent = Number(gain.value).toFixed(2);
    });

    row.append(label, swatch, gain, readout);
    box.appendChild(row);
    return { filter: filt, include, swatch, gain };
  });

  config.appendChild(box);
  return rows;
}

/**
 * Render the luminance filter dropdown.
 *
 * @param {Element} config - container to append the fieldset to.
 * @param {*} schema - the /api/color payload.
 * @returns {HTMLSelectElement}
 */
function buildLuminanceChoice(config, schema) {
  const box = document.createElement("fieldset");
  box.className = "config-menu";
  const legend = document.createElement("legend");
  legend.textContent = "Luminance";
  legend.appendChild(
    createInfoTip(
      "Optionally lend one filter's lightness to the colour image (LRGB). A " +
        "deep unfiltered frame carries the detail; the colour filters carry the hue."
    )
  );
  box.appendChild(legend);

  const select = document.createElement("select");
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "(none)";
  select.appendChild(none);
  for (const filt of schema.filters) {
    const option = document.createElement("option");
    option.value = filt;
    option.textContent = filt;
    select.appendChild(option);
  }
  if (schema.default_luminance) select.value = schema.default_luminance;

  const row = document.createElement("div");
  row.className = "param";
  const label = document.createElement("span");
  label.className = "param-label";
  label.textContent = "luminance filter";
  row.append(label, select);
  box.appendChild(row);

  config.appendChild(box);
  return select;
}

/**
 * @param {Element|null} el
 * @param {string} text
 */
function setResult(el, text) {
  if (el) el.textContent = text;
}

document.addEventListener("DOMContentLoaded", init);
