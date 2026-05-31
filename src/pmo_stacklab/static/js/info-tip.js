/**
 * @file The pedagogical info-tip control.
 *
 * Pedagogy is a first-class goal of PMO StackLab: every choice the user makes --
 * each subprocess and each algorithm option -- carries a small "i" icon that, on
 * hover or keyboard focus, reveals a short explanation of how that choice fits
 * into the broader stacking pipeline. This module builds that control.
 *
 * The explanatory text is sourced from the backend schema's `description` fields
 * (single source of truth: write the copy once on the backend, it appears here),
 * falling back to placeholder text where a description is not yet written.
 */

/** Placeholder shown until real explanatory copy is written on the backend. */
export const PLACEHOLDER_INFO =
  "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " +
  "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.";

/**
 * Build an accessible info tip: an "i" icon that reveals `text` on hover/focus.
 *
 * The tip is keyboard-focusable and exposes its text to assistive tech, so the
 * pedagogical content is available without a mouse. Revealing is handled in CSS
 * (`.info-tip:hover`/`:focus-within`), keeping this purely structural.
 *
 * @param {string} [text] explanatory copy; the placeholder is used when empty.
 * @returns {HTMLElement} the info-tip element, ready to append next to a label.
 */
export function createInfoTip(text) {
  const tip = document.createElement("span");
  tip.className = "info-tip";
  tip.tabIndex = 0;
  tip.setAttribute("role", "note");
  tip.setAttribute("aria-label", "More information");

  const icon = document.createElement("span");
  icon.className = "info-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "i";

  const bubble = document.createElement("span");
  bubble.className = "info-bubble";
  bubble.textContent = text && text.trim() ? text : PLACEHOLDER_INFO;

  tip.append(icon, bubble);
  return tip;
}
