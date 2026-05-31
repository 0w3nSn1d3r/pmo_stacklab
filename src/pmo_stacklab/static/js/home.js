/**
 * @file Home page entry point.
 *
 * The home page is static content; its only dynamic element is the shared,
 * data-driven navigation bar.
 */
import { buildNav } from "./nav.js";

document.addEventListener("DOMContentLoaded", () => {
  buildNav();
});
