/**
 * @file Typed client for the PMO StackLab backend API.
 *
 * All network access to the generalized process endpoint is funnelled through
 * here, so the rest of the frontend never touches `fetch` or raw URLs. The
 * typedefs mirror the JSON the backend serves (see the typed parameter schema in
 * `modules/core/parameters.py` and the registry in `modules/core/registry.py`);
 * they are the contract the schema-driven UI is built against.
 */

/**
 * One parameter's schema. `type` selects which control the UI renders; the
 * numeric bounds/choices describe its constraints; `description` feeds the info
 * tip.
 *
 * @typedef {Object} ParamSchema
 * @property {string} name
 * @property {"float"|"int"|"bool"|"choice"} type
 * @property {number|boolean|string} default
 * @property {number|null} [minimum]
 * @property {number|null} [maximum]
 * @property {number|null} [step]
 * @property {string[]} [choices]
 * @property {string} [description]
 */

/**
 * @typedef {Object} AlgorithmSchema
 * @property {string} name
 * @property {string} label
 * @property {string} description
 * @property {ParamSchema[]} parameters
 */

/**
 * @typedef {Object} SubprocessSchema
 * @property {string} name
 * @property {string} label
 * @property {string} description
 * @property {AlgorithmSchema[]} algorithms
 */

/**
 * @typedef {Object} ProcessSchema
 * @property {string} name
 * @property {SubprocessSchema[]} subprocesses
 */

/**
 * The user's choice for one subprocess, sent back to the run endpoint.
 *
 * @typedef {Object} SubprocessChoice
 * @property {string} algorithm
 * @property {Object<string, number|boolean|string>} params
 */

const API_ROOT = "/api";

/**
 * Perform a fetch and parse its JSON body, raising the backend's error message
 * on any non-2xx response.
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `request failed (${response.status})`);
  }
  return body;
}

/**
 * Fetch the configured pipeline as an ordered list of process names.
 * @returns {Promise<{order: string[]}>}
 */
export function getPipeline() {
  return requestJSON(`${API_ROOT}/schema`);
}

/**
 * Fetch one process's full parameter schema (used to render its config menus).
 * @param {string} processName
 * @returns {Promise<ProcessSchema>}
 */
export function getProcessSchema(processName) {
  return requestJSON(`${API_ROOT}/schema/${encodeURIComponent(processName)}`);
}

/**
 * Run a process with the user's per-subprocess choices.
 * @param {string} processName
 * @param {Object<string, SubprocessChoice>} configs
 * @returns {Promise<any>} the backend's process-output summary.
 */
export function runProcess(processName, configs) {
  return requestJSON(`${API_ROOT}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ process: processName, configs }),
  });
}

/**
 * Upload FITS frames as a multipart form (lights/darks/bias/flats fields).
 * @param {FormData} formData
 * @returns {Promise<any>} the upload summary (per-set frame counts).
 */
export function uploadFrames(formData) {
  return requestJSON(`${API_ROOT}/upload`, { method: "POST", body: formData });
}

/**
 * List the filters available to preview for a completed step.
 * @param {string} step - "Upload" or a process name.
 * @returns {Promise<{step: string, filters: string[]}>}
 */
export function getPreviewFilters(step) {
  return requestJSON(`${API_ROOT}/preview/${encodeURIComponent(step)}`);
}

/**
 * Fetch per-filter quality metrics for a step. Computed on full-resolution linear
 * data, so the numbers are independent of the display stretch.
 * @param {string} step - "Upload" or a process name.
 * @returns {Promise<{step: string, filters: Object<string, Object<string, number>>}>}
 */
export function getMetrics(step) {
  return requestJSON(`${API_ROOT}/metrics/${encodeURIComponent(step)}`);
}

/**
 * Fetch the colour-combine schema: source step, available filters, channel names,
 * a default channel->filter mapping, and the combine-algorithm schema.
 * @returns {Promise<any>}
 */
export function getColorSchema() {
  return requestJSON(`${API_ROOT}/color`);
}

/**
 * Combine the mapped per-filter frames into an RGB image (stored server-side).
 * @param {string} algorithm - combine algorithm name.
 * @param {Object<string, number>} params - the algorithm's parameter values.
 * @param {Object<string, string|null>} mapping - channel -> filter (or null).
 * @returns {Promise<{shape: number[], mapping: Object<string, string|null>}>}
 */
export function combineColor(algorithm, params, mapping) {
  return requestJSON(`${API_ROOT}/color`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ algorithm, params, mapping }),
  });
}

/**
 * Build the URL for the most recently combined RGB PNG (used as an <img> src).
 * @param {{t?: number}} [params] - optional cache-buster `t`.
 * @returns {string}
 */
export function colorImageUrl(params = {}) {
  const qs = params.t != null ? `?t=${params.t}` : "";
  return `${API_ROOT}/color.png${qs}`;
}

/**
 * Build the download URL for a step/filter's full-resolution frame.
 * @param {string} step - "Upload" or a process name.
 * @param {string} filter - the filter to download.
 * @param {"fits"|"png"} fmt - file format.
 * @param {{stretch?: string, intensity?: number}} [params] - display stretch for
 *   the PNG render (ignored for FITS, which is the verbatim linear data).
 * @returns {string}
 */
export function downloadUrl(step, filter, fmt, params = {}) {
  const query = new URLSearchParams();
  if (fmt === "png") {
    if (params.stretch) query.set("stretch", params.stretch);
    if (params.intensity != null) query.set("intensity", String(params.intensity));
  }
  const qs = query.toString();
  return (
    `${API_ROOT}/download/${encodeURIComponent(step)}/` +
    `${encodeURIComponent(filter)}.${fmt}${qs ? `?${qs}` : ""}`
  );
}

/**
 * Build the URL for a step's preview PNG. Used directly as an <img> src (the
 * browser fetches it), so this returns a URL string rather than a promise.
 *
 * @param {string} step - "Upload" or a process name.
 * @param {string} filter - the filter to render.
 * @param {{stretch?: string, intensity?: number, cx?: number, cy?: number,
 *   t?: number}} [params] - display controls (stretch name, intensity 0-1), an
 *   optional fractional zoom centre (cx, cy in [0,1]), plus an optional
 *   cache-buster `t`.
 * @returns {string}
 */
export function previewImageUrl(step, filter, params = {}) {
  const query = new URLSearchParams();
  if (params.stretch) query.set("stretch", params.stretch);
  if (params.intensity != null) query.set("intensity", String(params.intensity));
  if (params.cx != null && params.cy != null) {
    query.set("cx", String(params.cx));
    query.set("cy", String(params.cy));
  }
  if (params.t != null) query.set("t", String(params.t));
  const qs = query.toString();
  return (
    `${API_ROOT}/preview/${encodeURIComponent(step)}/` +
    `${encodeURIComponent(filter)}.png${qs ? `?${qs}` : ""}`
  );
}
