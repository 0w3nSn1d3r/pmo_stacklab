/**
 * @file Controller for the Upload page.
 *
 * Collects the per-role FITS file inputs (lights/darks/bias/flats) into a
 * multipart form and POSTs them to `/api/upload`, which builds the session's
 * initial ImageData. Attaches an info tip to each frame-role input, with
 * role-specific placeholder copy, and shows the upload summary.
 */
import { uploadFrames } from "./api.js";
import { buildNav } from "./nav.js";
import { createInfoTip } from "./info-tip.js";

async function init() {
  buildNav();

  // Replace each label's [data-info] placeholder with an info tip. The copy is
  // placeholder for now (Owen will supply the real pedagogical text).
  document.querySelectorAll(".param-label [data-info]").forEach((slot) => {
    slot.replaceWith(createInfoTip(""));
  });

  const form = /** @type {HTMLFormElement|null} */ (
    document.querySelector("#upload-form")
  );
  const resultEl = document.querySelector("#result");
  const uploadBtn = /** @type {HTMLButtonElement|null} */ (
    document.querySelector("#upload")
  );
  if (!form || !uploadBtn) return;

  uploadBtn.addEventListener("click", async () => {
    const formData = new FormData(form);

    uploadBtn.disabled = true;
    setResult(resultEl, "Uploading...");
    try {
      const result = await uploadFrames(formData);
      setResult(resultEl, JSON.stringify(result, null, 2));
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
    } finally {
      uploadBtn.disabled = false;
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
