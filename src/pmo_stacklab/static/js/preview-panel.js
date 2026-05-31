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
 * @typedef {import("./api.js").ProcessSchema} ProcessSchema
 */
import { getPreviewFilters, previewImageUrl } from "./api.js";

/** Display-stretch options offered for the linear steps. */
const STRETCHES = ["asinh", "log", "sqrt", "linear"];

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

  container.append(controls, img);

  const refresh = () => {
    img.src = previewImageUrl(step, filterSelect.value, {
      stretch: stretchSelect ? stretchSelect.value : "linear",
      intensity: intensityInput ? Number(intensityInput.value) : 0.5,
      // cache-buster so the browser re-fetches when controls change
      t: Date.now(),
    });
  };

  filterSelect.addEventListener("change", refresh);
  if (stretchSelect) stretchSelect.addEventListener("change", refresh);
  if (intensityInput) intensityInput.addEventListener("input", refresh);
  refresh();
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
