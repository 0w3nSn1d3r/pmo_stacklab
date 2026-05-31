/**
 * @file Schema-driven configuration custom elements.
 *
 * These are the frontend mirror of the backend's Subprocess/Algorithm registry:
 * given a subprocess schema served by `/api/schema/<process>`, `<config-menu>`
 * renders a radio group of algorithm choices (`<algo-option>`), each revealing its
 * own parameter controls, and exposes the user's selection as the
 * `{algorithm, params}` object the run endpoint expects. Because the GUI is built
 * entirely from the served schema, adding or changing an algorithm on the backend
 * needs no frontend change.
 *
 * Both are AUTONOMOUS custom elements (extending HTMLElement), deliberately not
 * customized built-ins (`is="..."`), which Safari does not support.
 *
 * Pedagogy: every subprocess and every algorithm option carries an info tip (see
 * info-tip.js), sourced from the schema's `description` fields.
 *
 * @typedef {import("./api.js").ParamSchema} ParamSchema
 * @typedef {import("./api.js").AlgorithmSchema} AlgorithmSchema
 * @typedef {import("./api.js").SubprocessSchema} SubprocessSchema
 */
import { createInfoTip } from "./info-tip.js";

/**
 * A rendered parameter control: its DOM subtree and a reader for its value.
 *
 * @typedef {Object} ParamControl
 * @property {string} name
 * @property {HTMLElement} element
 * @property {() => number|boolean|string} getValue
 */

/**
 * Build the input control for one parameter, dispatching on its type. Numeric
 * parameters with both bounds render as sliders with a live readout; unbounded
 * numerics fall back to a number field; booleans render as a checkbox; choices
 * render as a dropdown -- a categorical, never a slider.
 *
 * @param {ParamSchema} param
 * @returns {ParamControl}
 */
function createParamControl(param) {
  switch (param.type) {
    case "float":
    case "int":
      return createNumberControl(param);
    case "bool":
      return createBoolControl(param);
    case "choice":
      return createChoiceControl(param);
    default:
      // Unknown type: show a disabled note rather than breaking the whole menu.
      return createUnsupportedControl(param);
  }
}

/**
 * A label cell carrying the parameter name and, when described, an info tip.
 * @param {ParamSchema} param
 * @returns {HTMLElement}
 */
function paramLabel(param) {
  const label = document.createElement("span");
  label.className = "param-label";
  label.textContent = param.name;
  label.appendChild(createInfoTip(param.description));
  return label;
}

/**
 * @param {ParamSchema} param
 * @returns {ParamControl}
 */
function createNumberControl(param) {
  const wrap = document.createElement("div");
  wrap.className = "param";
  wrap.appendChild(paramLabel(param));

  const isInt = param.type === "int";
  const bounded = param.minimum != null && param.maximum != null;
  const step = param.step != null ? param.step : isInt ? 1 : 0.01;

  const input = document.createElement("input");
  input.value = String(param.default);
  input.step = String(step);

  if (bounded) {
    input.type = "range";
    input.min = String(param.minimum);
    input.max = String(param.maximum);
    const output = document.createElement("output");
    output.className = "param-value";
    output.textContent = String(param.default);
    input.addEventListener("input", () => {
      output.textContent = input.value;
    });
    wrap.append(input, output);
  } else {
    input.type = "number";
    wrap.appendChild(input);
  }

  const getValue = () =>
    isInt ? parseInt(input.value, 10) : parseFloat(input.value);
  return { name: param.name, element: wrap, getValue };
}

/**
 * @param {ParamSchema} param
 * @returns {ParamControl}
 */
function createBoolControl(param) {
  const wrap = document.createElement("div");
  wrap.className = "param";

  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(param.default);

  const label = document.createElement("label");
  label.className = "param-label";
  label.append(input, document.createTextNode(" " + param.name));

  wrap.append(label, createInfoTip(param.description));
  return { name: param.name, element: wrap, getValue: () => input.checked };
}

/**
 * @param {ParamSchema} param
 * @returns {ParamControl}
 */
function createChoiceControl(param) {
  const wrap = document.createElement("div");
  wrap.className = "param";
  wrap.appendChild(paramLabel(param));

  const select = document.createElement("select");
  for (const choice of param.choices || []) {
    const option = document.createElement("option");
    option.value = choice;
    option.textContent = choice;
    if (choice === param.default) option.selected = true;
    select.appendChild(option);
  }
  wrap.appendChild(select);

  return { name: param.name, element: wrap, getValue: () => select.value };
}

/**
 * @param {ParamSchema} param
 * @returns {ParamControl}
 */
function createUnsupportedControl(param) {
  const wrap = document.createElement("div");
  wrap.className = "param param-unsupported";
  wrap.textContent = `${param.name} (unsupported type: ${param.type})`;
  return { name: param.name, element: wrap, getValue: () => param.default };
}

/**
 * One selectable algorithm: a radio button (with an info tip) plus that
 * algorithm's parameter controls, which are shown only while the radio is
 * selected.
 */
class AlgoOption extends HTMLElement {
  /** @type {AlgorithmSchema|null} */
  #schema = null;
  /** @type {string} */
  #group = "";
  /** @type {HTMLInputElement|null} */
  #radio = null;
  /** @type {HTMLFieldSetElement|null} */
  #params = null;
  /** @type {ParamControl[]} */
  #controls = [];

  /** @param {AlgorithmSchema} schema */
  set schema(schema) {
    this.#schema = schema;
  }

  /** @param {string} group shared radio-group name (the subprocess name). */
  set group(group) {
    this.#group = group;
  }

  /** @returns {string} the algorithm name this option represents. */
  get algorithmName() {
    return this.#schema ? this.#schema.name : "";
  }

  /** @returns {boolean} whether this option's radio is selected. */
  get checked() {
    return this.#radio ? this.#radio.checked : false;
  }

  /** @param {boolean} value */
  set checked(value) {
    if (this.#radio) this.#radio.checked = value;
    this.updateState();
  }

  connectedCallback() {
    if (this.#schema && !this.#radio) this.render();
  }

  render() {
    const schema = /** @type {AlgorithmSchema} */ (this.#schema);

    const header = document.createElement("label");
    header.className = "algo-header";

    this.#radio = document.createElement("input");
    this.#radio.type = "radio";
    this.#radio.name = this.#group;
    this.#radio.value = schema.name;
    header.append(
      this.#radio,
      document.createTextNode(" " + (schema.label || schema.name))
    );
    // Info tip explaining this algorithm choice.
    header.appendChild(createInfoTip(schema.description));
    this.appendChild(header);

    // Parameter controls live in a fieldset so they can be disabled as a group
    // when this algorithm is not selected.
    this.#params = document.createElement("fieldset");
    this.#params.className = "algo-params";
    this.#controls = (schema.parameters || []).map((param) => {
      const control = createParamControl(param);
      /** @type {HTMLFieldSetElement} */ (this.#params).appendChild(control.element);
      return control;
    });
    this.appendChild(this.#params);

    this.updateState();
  }

  /** Show this option's parameters only while its radio is selected. */
  updateState() {
    if (!this.#params) return;
    const on = this.checked;
    this.#params.disabled = !on;
    this.#params.hidden = !on;
    this.classList.toggle("selected", on);
  }

  /** @returns {Object<string, number|boolean|string>} this algorithm's params. */
  getParams() {
    return Object.fromEntries(
      this.#controls.map((control) => [control.name, control.getValue()])
    );
  }
}

/**
 * One subprocess slot: a fieldset of `<algo-option>` radios sharing a group (with
 * an info tip on the slot itself), exposing the chosen `{algorithm, params}` via
 * `.value`.
 */
class ConfigMenu extends HTMLElement {
  /** @type {SubprocessSchema|null} */
  #schema = null;
  /** @type {AlgoOption[]} */
  #options = [];

  /** @param {SubprocessSchema} schema */
  set schema(schema) {
    this.#schema = schema;
  }

  /** @returns {string} the subprocess name (the key sent back in configs). */
  get subprocessName() {
    return this.#schema ? this.#schema.name : "";
  }

  connectedCallback() {
    if (this.#schema && !this.#options.length) this.render();
  }

  render() {
    const schema = /** @type {SubprocessSchema} */ (this.#schema);

    const fieldset = document.createElement("fieldset");
    fieldset.className = "config-menu";

    const legend = document.createElement("legend");
    legend.textContent = schema.label || schema.name;
    // Info tip explaining this subprocess's role in the pipeline.
    legend.appendChild(createInfoTip(schema.description));
    fieldset.appendChild(legend);

    this.#options = schema.algorithms.map((algo) => {
      const option = /** @type {AlgoOption} */ (
        document.createElement("algo-option")
      );
      option.schema = algo;
      option.group = schema.name;
      fieldset.appendChild(option); // connectedCallback renders it
      return option;
    });
    this.appendChild(fieldset);

    // Default to the first algorithm and keep parameter visibility in sync as
    // the selection changes.
    if (this.#options.length) this.#options[0].checked = true;
    fieldset.addEventListener("change", () => {
      for (const option of this.#options) option.updateState();
    });
  }

  /** @returns {{algorithm: string, params: Object<string, number|boolean|string>}} */
  get value() {
    const selected =
      this.#options.find((option) => option.checked) || this.#options[0];
    return {
      algorithm: selected ? selected.algorithmName : "",
      params: selected ? selected.getParams() : {},
    };
  }
}

customElements.define("algo-option", AlgoOption);
customElements.define("config-menu", ConfigMenu);

export { AlgoOption, ConfigMenu };
