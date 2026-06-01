/**
 * @file Controller for the Color combination page.
 *
 * Colour combination is a terminal step parallel to the pipeline: it maps the
 * per-filter stacked frames onto the red/green/blue channels and combines them
 * into one image. This page fetches the combine schema (/api/color), renders the
 * channel->filter dropdowns (pre-filled with a name-based default mapping) and a
 * <config-menu> for the chosen combine algorithm, and -- on "Combine" -- POSTs the
 * mapping + algorithm choice and shows the resulting RGB image.
 *
 * Unmapped channels are left black, so partial (e.g. two-channel) combines work.
 */
import { combineColor, colorImageUrl, getColorSchema } from "./api.js";
import { buildNav } from "./nav.js";
import { createInfoTip } from "./info-tip.js";
import "./config-menu.js"; // registers <config-menu>

async function init() {
  buildNav();

  const config = document.querySelector("#color-config");
  const resultEl = document.querySelector("#result");
  const image = /** @type {HTMLImageElement} */ (document.querySelector("#color-image"));
  const combineBtn = /** @type {HTMLButtonElement|null} */ (
    document.querySelector("#combine")
  );
  if (!config || !combineBtn) return;

  let schema;
  try {
    schema = await getColorSchema();
  } catch (err) {
    // 409 until something has been stacked.
    config.textContent = `Color combination is not available yet: ${err.message}`;
    combineBtn.disabled = true;
    return;
  }

  // -- channel -> filter mapping dropdowns (with info tips)
  const channelSelects = {};
  const mappingBox = document.createElement("fieldset");
  mappingBox.className = "config-menu";
  const legend = document.createElement("legend");
  legend.textContent = "Channel mapping";
  legend.appendChild(
    createInfoTip("Assign a filter to each colour channel. Unassigned channels stay black.")
  );
  mappingBox.appendChild(legend);

  for (const channel of schema.channels) {
    const select = document.createElement("select");
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "(none)";
    select.appendChild(none);
    for (const filt of schema.filters) {
      const opt = document.createElement("option");
      opt.value = filt;
      opt.textContent = filt;
      select.appendChild(opt);
    }
    // Pre-select the server's name-based default for this channel.
    const def = schema.default_mapping[channel];
    if (def) select.value = def;
    channelSelects[channel] = select;

    const row = document.createElement("div");
    row.className = "param";
    const label = document.createElement("span");
    label.className = "param-label";
    label.textContent = channel;
    row.append(label, select);
    mappingBox.appendChild(row);
  }
  config.appendChild(mappingBox);

  // -- combine-algorithm choice (reuses the schema-driven <config-menu>)
  const menu = /** @type {*} */ (document.createElement("config-menu"));
  menu.schema = schema.combine;
  config.appendChild(menu);

  combineBtn.addEventListener("click", async () => {
    const mapping = {};
    for (const [channel, select] of Object.entries(channelSelects)) {
      mapping[channel] = select.value || null;
    }
    const { algorithm, params } = menu.value;

    combineBtn.disabled = true;
    setResult(resultEl, "Combining...");
    try {
      await combineColor(algorithm, params, mapping);
      setResult(resultEl, "");
      image.src = colorImageUrl({ t: Date.now() });
      image.hidden = false;
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
    } finally {
      combineBtn.disabled = false;
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
