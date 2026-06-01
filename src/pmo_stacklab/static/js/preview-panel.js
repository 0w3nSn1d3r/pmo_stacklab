/**
 * @file The preview panel: a step's rendered image, metrics, and before/after blink.
 *
 * After a step runs (or after upload), this panel shows the server-rendered preview
 * PNG for a chosen filter, plus a metrics table for that filter.
 *
 * For the linear steps (Upload..Stack) it offers display-only controls -- a
 * stretch-type dropdown and an intensity slider -- that re-request the image with
 * new query params; these affect ONLY the displayed copy, never the data flowing
 * through the pipeline. Post-Process output is already display-ready (the user's
 * own stretch produced it), so that step renders with stretch="linear" and hides
 * the display controls to avoid double-stretching.
 *
 * BLINK: when a "before" step is supplied (the step's input -- i.e. the previous
 * step's output), the panel shows a before/after comparator. The two images are
 * stacked in the SAME spatial position and a toggle button flips which is visible,
 * so the eye sees only what changed -- the classic astronomer's "blink". Both
 * images are always rendered with IDENTICAL filter + stretch + intensity, so the
 * comparison reflects the processing, not a difference in display. The metrics
 * table swaps together with the image, so the numbers always describe the image
 * on screen.
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
 * @param {string} step - the step to preview ("Upload" or a process name).
 * @param {{displayControls?: boolean, beforeStep?: string|null}} [options]
 *   - displayControls: defaults to true; pass false for already-display-ready
 *     output (Post-Process).
 *   - beforeStep: the step whose output is this step's input; when given (and it
 *     has a preview), the panel becomes a before/after blink. Omit for steps with
 *     no predecessor (Upload).
 * @returns {Promise<void>}
 */
export async function showPreview(container, step, options = {}) {
  const displayControls = options.displayControls !== false;
  const beforeStep = options.beforeStep || null;
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

  // A "view" is one comparable image: its step and a human label. Single-view for
  // a step with no predecessor; two-view (before, after) for the blink.
  const views = await buildViews(step, beforeStep);

  // -- controls: filter, optional display stretch/intensity, optional blink toggle
  const controls = document.createElement("div");
  controls.className = "preview-controls";

  const filterSelect = selectOf(filters);
  controls.append(labelled("Filter", filterSelect));

  let stretchSelect = null;
  let intensityInput = null;
  if (displayControls) {
    stretchSelect = selectOf(STRETCHES, "asinh");
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

  // -- image stack: one <img> per view, overlaid in the same grid cell
  const stack = document.createElement("div");
  stack.className = "blink-stack";
  const images = views.map((view) => {
    const img = document.createElement("img");
    img.className = "preview-image";
    img.alt = `${view.step} preview`;
    stack.appendChild(img);
    return img;
  });

  // -- action bar: blink toggle (when there are two views) + zoom-out (when zoomed)
  const blinkBar = document.createElement("div");
  blinkBar.className = "blink-bar";
  let activeIndex = views.length - 1; // default to "after"
  let toggleBtn = null;
  const activeLabel = document.createElement("span");
  activeLabel.className = "blink-label";
  if (views.length > 1) {
    toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "run-button blink-toggle";
    toggleBtn.textContent = "Blink ⇄"; // ⇄
    blinkBar.append(toggleBtn, activeLabel);
  }

  // Click an image to zoom into a fixed tile centred there; this state is shared
  // across views so zoom and blink compose (compare the SAME zoomed region).
  /** @type {{cx: number, cy: number}|null} */
  let zoom = null;
  const zoomOutBtn = document.createElement("button");
  zoomOutBtn.type = "button";
  zoomOutBtn.className = "run-button zoom-out";
  zoomOutBtn.textContent = "Zoom out";
  zoomOutBtn.hidden = true;
  blinkBar.append(zoomOutBtn);

  const metricsTable = document.createElement("table");
  metricsTable.className = "metrics-table";

  container.append(controls, blinkBar, stack, metricsTable);

  // Metrics per view step (independent of display stretch; fetched once each).
  const metricsByStep = {};
  await Promise.all(
    views.map(async (view) => {
      try {
        const { filters: m } = await getMetrics(view.step);
        metricsByStep[view.step] = m;
      } catch {
        metricsByStep[view.step] = {};
      }
    })
  );

  const displayParams = () => ({
    stretch: stretchSelect ? stretchSelect.value : "linear",
    intensity: intensityInput ? Number(intensityInput.value) : 0.5,
  });

  // Re-request every view's image with the shared (matched) display params and the
  // shared zoom, so the blink only ever differs by the processing -- never by the
  // display transform or the region viewed.
  const refreshImages = () => {
    const params = displayParams();
    if (zoom) {
      params.cx = zoom.cx;
      params.cy = zoom.cy;
    }
    views.forEach((view, i) => {
      images[i].src = previewImageUrl(view.step, filterSelect.value, {
        ...params,
        t: Date.now(), // cache-buster
      });
    });
    zoomOutBtn.hidden = !zoom;
    stack.classList.toggle("zoomable", !zoom);
  };

  // Clicking an image zooms into a tile centred on the click (in fractional image
  // coordinates, so the backend maps it onto the full-resolution frame).
  const onImageClick = (event) => {
    if (zoom) return; // already zoomed; use "Zoom out" to reset
    const img = /** @type {HTMLImageElement} */ (event.currentTarget);
    const rect = img.getBoundingClientRect();
    zoom = {
      cx: (event.clientX - rect.left) / rect.width,
      cy: (event.clientY - rect.top) / rect.height,
    };
    refreshImages();
  };
  images.forEach((img) => img.addEventListener("click", onImageClick));
  zoomOutBtn.addEventListener("click", () => {
    zoom = null;
    refreshImages();
  });

  // Show only the active view's image and its metrics; keep the on-screen image in
  // a fixed position so toggling reads as a blink, not a layout change.
  const showActive = () => {
    images.forEach((img, i) => img.classList.toggle("active", i === activeIndex));
    const view = views[activeIndex];
    renderMetrics(metricsTable, (metricsByStep[view.step] || {})[filterSelect.value]);
    if (views.length > 1) activeLabel.textContent = view.label;
  };

  filterSelect.addEventListener("change", () => {
    refreshImages();
    showActive();
  });
  if (stretchSelect) stretchSelect.addEventListener("change", refreshImages);
  if (intensityInput) intensityInput.addEventListener("input", refreshImages);
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      activeIndex = (activeIndex + 1) % views.length;
      showActive();
    });
  }

  refreshImages();
  showActive();
}

/**
 * Build the list of views for a step. Returns a single "after" view, or -- when a
 * usable before step is given -- a [before, after] pair for the blink. The before
 * step is dropped (single view) if it has no available preview.
 *
 * @param {string} step
 * @param {string|null} beforeStep
 * @returns {Promise<Array<{step: string, label: string}>>}
 */
async function buildViews(step, beforeStep) {
  const after = { step, label: `After — ${step}` };
  if (!beforeStep) return [after];
  try {
    const { filters } = await getPreviewFilters(beforeStep);
    if (!filters.length) return [after];
  } catch {
    return [after];
  }
  return [{ step: beforeStep, label: `Before — ${beforeStep}` }, after];
}

/**
 * Render a metrics dict into a two-column table. Counts show as integers; other
 * statistics use a compact format so large ADU values and small fractions both
 * read cleanly.
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
 * Build a <select> from string options, optionally pre-selecting one.
 * @param {string[]} options
 * @param {string} [selected]
 * @returns {HTMLSelectElement}
 */
function selectOf(options, selected) {
  const select = document.createElement("select");
  for (const value of options) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    if (value === selected) opt.selected = true;
    select.appendChild(opt);
  }
  return select;
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
