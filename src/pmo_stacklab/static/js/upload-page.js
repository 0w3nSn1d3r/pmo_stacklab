/**
 * @file Controller for the Upload page.
 *
 * Collects the per-role FITS file inputs (lights/darks/bias/flats) into a
 * multipart form and POSTs them to `/api/upload`, which builds the session's
 * initial ImageData. Attaches an info tip to each frame-role input, and shows the
 * upload preview.
 *
 * Also drives the Quick Stack controls: "Quick Stack" applies the saved recipe to
 * the uploaded frames in one shot and previews the final result; the settings menu
 * offers "Configure" (a link into the per-process config walkthrough) and "Reset
 * to Default".
 */
import {
  resetQuickStackConfig,
  runQuickStack,
  uploadFrames,
} from "./api.js";
import { buildNav } from "./nav.js";
import { createInfoTip } from "./info-tip.js";
import { showPreview } from "./preview-panel.js";

// The last process in the pipeline -- Quick Stack's final output to preview.
const FINAL_STEP = "Post-Process";

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
  const previewEl = /** @type {HTMLElement|null} */ (
    document.querySelector("#preview")
  );
  const uploadBtn = /** @type {HTMLButtonElement|null} */ (
    document.querySelector("#upload")
  );
  if (!form || !uploadBtn) return;

  uploadBtn.addEventListener("click", async () => {
    const formData = new FormData(form);

    uploadBtn.disabled = true;
    setResult(resultEl, "Uploading...");
    try {
      await uploadFrames(formData);
      setResult(resultEl, "");
      // Uploaded data is linear, so the preview offers display-stretch controls.
      if (previewEl) await showPreview(previewEl, "Upload", { displayControls: true });
    } catch (err) {
      setResult(resultEl, `Error: ${err.message}`);
    } finally {
      uploadBtn.disabled = false;
    }
  });

  // -- Quick Stack: upload (if needed) then run the whole saved recipe at once.
  const quickStackBtn = /** @type {HTMLButtonElement|null} */ (
    document.querySelector("#quick-stack")
  );
  if (quickStackBtn) {
    quickStackBtn.addEventListener("click", async () => {
      quickStackBtn.disabled = true;
      uploadBtn.disabled = true;
      setResult(resultEl, "Uploading frames...");
      try {
        // Upload the selected frames first, so Quick Stack always runs on the
        // current selection without a separate Upload click.
        if (form.querySelector('input[type="file"][name="lights"]').files.length) {
          await uploadFrames(new FormData(form));
        }
        setResult(resultEl, "Running Quick Stack...");
        await runQuickStack();
        setResult(resultEl, "");
        // Quick Stack's output is the post-processed (display-ready) final image,
        // so it is shown as-is and blinks against the prior step.
        if (previewEl) {
          await showPreview(previewEl, FINAL_STEP, {
            displayControls: false,
            beforeStep: "Stack",
          });
        }
      } catch (err) {
        setResult(resultEl, `Error: ${err.message}`);
      } finally {
        quickStackBtn.disabled = false;
        uploadBtn.disabled = false;
      }
    });
  }

  // -- "Reset to Default" in the settings menu.
  const resetBtn = document.querySelector("#qs-reset");
  if (resetBtn) {
    resetBtn.addEventListener("click", async () => {
      try {
        await resetQuickStackConfig();
        setResult(resultEl, "Quick Stack settings reset to default.", "success");
      } catch (err) {
        setResult(resultEl, `Error: ${err.message}`);
      }
    });
  }
}

/**
 * Show a status line. ``kind`` is "error" (default, red) or "success" (green), so
 * a confirmation is not styled as an alarming error.
 *
 * @param {Element|null} el
 * @param {string} text
 * @param {"error"|"success"} [kind]
 */
function setResult(el, text, kind = "error") {
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("success", kind === "success");
}

document.addEventListener("DOMContentLoaded", init);
