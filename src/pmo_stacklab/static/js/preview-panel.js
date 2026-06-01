/**
 * @file The preview panel: shows a step's rendered image with display controls.
 *
 * After a step runs (or after upload), this panel displays the server-rendered
 * preview PNG for a chosen filter. For the linear steps (Upload..Stack) it offers
 * display-only controls -- a stretch-type dropdown and an intensity slider -- that
 * re-request the image with new query params; these affect ONLY the displayed
 * copy, never the data flowing through the pipeline.
 *
 * Post-Process output is already display-ready (the user's own stretch produced
 * it), so for that step the panel renders with stretch="linear" and hides the
 * display controls to avoid double-stretching.
 *
 * Below the image it shows a metrics table for the selected filter. Metrics come
 * from /api/metrics (computed on full-resolution linear data), so they are
 * independent of the display stretch -- the numbers describe the image, not how
 * it is shown.
 *
 * @typedef {import("./api.js").ProcessSchema} ProcessSchema
 */
import { getMetrics, getPreviewFilters, previewImageUrl } from "./api.js";

/** Display-stretch options offered for the linear steps. */
const STRETCHES = ["asinh", "log", "sqrt", "linear"];

/** Metric keys to display, in order, with friendly labels. */
const METRIC_LABELS = {
  count: "Valid pixels",
  min: "Min",
  max: "Max",
  mean: "Mean",
  median: "Median",
  std: "Std dev",
};

/**
 * Render the preview panel for a step into a container.
 *
 * @param {HTMLElement} container - the element to render the panel into.
 * @param {string} step - the step name to preview ("Upload" or a process name).
 * @param {{displayControls?: boolean}} [options] - displayControls defaults to
 *   true; pass false for already-display-ready output (Post-Process).
 * @returns {Promise<void>}
 */
export async function showPreview(container, step, options = {}) {
  const displayControls = options.displayControls !== false;
  container.replaceChildren();

  let filters;
  try {
    ({ filters } = await getPreviewFilters(step));
  } catch (err) {
    container.textContent = `No preview available: ${err.message}`;
    return;
  }
  if (!filters.length) {
    container.textContent = "No preview available.";
    return;
  }

  // Controls: filter picker, and (for linear steps) stretch + intensity.
  const controls = document.createElement("div");
  controls.className = "preview-controls";

  const filterSelect = document.createElement("select");
  for (const filt of filters) {
    const opt = document.createElement("option");
    opt.value = filt;
    opt.textContent = filt;
    filterSelect.appendChild(opt);
  }
  controls.append(labelled("Filter", filterSelect));

  let stretchSelect = null;
  let intensityInput = null;
  if (displayControls) {
    stretchSelect = document.createElement("select");
    for (const s of STRETCHES) {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      stretchSelect.appendChild(opt);
    }
    stretchSelect.value = "asinh";

    intensityInput = document.createElement("input");
    intensityInput.type = "range";
    intensityInput.min = "0";
    intensityInput.max = "1";
    intensityInput.step = "0.05";
    intensityInput.value = "0.5";

    controls.append(
      labelled("Display stretch", stretchSelect),
      labelled("Intensity", intensityInput)
    );
  }

  const img = document.createElement("img");
  img.className = "preview-image";
  img.alt = `${step} preview`;

  const metricsTable = document.createElement("table");
  metricsTable.className = "metrics-table";

  container.append(controls, img, metricsTable);

  // Metrics are per-filter and independent of the display stretch, so fetch them
  // once for the step and just re-render the selected filter on filter change.
  /** @type {Object<string, Object<string, number>>} */
  let metricsByFilter = {};
  try {
    ({ filters: metricsByFilter } = await getMetrics(step));
  } catch {
    /* leave metrics empty; the image preview still works */
  }

  const refreshImage = () => {
    img.src = previewImageUrl(step, filterSelect.value, {
      stretch: stretchSelect ? stretchSelect.value : "linear",
      intensity: intensityInput ? Number(intensityInput.value) : 0.5,
      // cache-buster so the browser re-fetches when controls change
      t: Date.now(),
    });
  };

  const refreshMetrics = () => {
    renderMetrics(metricsTable, metricsByFilter[filterSelect.value]);
  };

  filterSelect.addEventListener("change", () => {
    refreshImage();
    refreshMetrics();
  });
  if (stretchSelect) stretchSelect.addEventListener("change", refreshImage);
  if (intensityInput) intensityInput.addEventListener("input", refreshImage);

  refreshImage();
  refreshMetrics();
}

/**
 * Render a metrics dict into a two-column table. Counts show as integers; the
 * other statistics use a compact significant-figure format so large ADU values
 * and small fractions both read cleanly.
 *
 * @param {HTMLTableElement} table
 * @param {Object<string, number>|undefined} metrics
 */
function renderMetrics(table, metrics) {
  table.replaceChildren();
  if (!metrics) return;
  for (const [key, label] of Object.entries(METRIC_LABELS)) {
    if (!(key in metrics)) continue;
    const row = table.insertRow();
    const name = row.insertCell();
    name.className = "metric-name";
    name.textContent = label;
    const value = row.insertCell();
    value.className = "metric-value";
    value.textContent =
      key === "count" ? String(metrics[key]) : formatNumber(metrics[key]);
  }
}

/**
 * Format a statistic compactly: plain for human-scale magnitudes, exponential for
 * very large or very small ones.
 * @param {number} x
 * @returns {string}
 */
function formatNumber(x) {
  if (!Number.isFinite(x)) return String(x);
  const abs = Math.abs(x);
  if (abs !== 0 && (abs >= 1e5 || abs < 1e-3)) return x.toExponential(3);
  return x.toFixed(3);
}

/**
 * Wrap a control in a labelled cell.
 * @param {string} text
 * @param {HTMLElement} control
 * @returns {HTMLElement}
 */
function labelled(text, control) {
  const wrap = document.createElement("label");
  wrap.className = "preview-control";
  const span = document.createElement("span");
  span.textContent = text;
  wrap.append(span, control);
  return wrap;
}
