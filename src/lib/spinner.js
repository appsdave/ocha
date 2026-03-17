/**
 * @module spinner
 * Loading spinner for agent activity feedback.
 * Wraps `ora` to provide a consistent UX across the CLI.
 */
import ora from 'ora';

/** @type {import('ora').Ora | null} */
let activeSpinner = null;

/**
 * Starts a spinner with the given text.
 * If a spinner is already active, updates its text instead.
 * @param {string} text - The message to display alongside the spinner.
 * @returns {import('ora').Ora} The spinner instance.
 */
export function startSpinner(text) {
  if (activeSpinner) {
    activeSpinner.text = text;
    return activeSpinner;
  }
  activeSpinner = ora({ text, color: 'cyan', spinner: 'dots' }).start();
  return activeSpinner;
}

/**
 * Updates the text of the active spinner without stopping it.
 * No-op if no spinner is active.
 * @param {string} text - New spinner text.
 */
export function updateSpinner(text) {
  if (activeSpinner) activeSpinner.text = text;
}

/**
 * Temporarily pauses the spinner, logs a message, and resumes.
 * If no spinner is active, just logs normally.
 * @param {string} message - The message to log.
 */
export function logWithSpinner(message) {
  if (activeSpinner) {
    activeSpinner.stop();
    console.log(message);
    activeSpinner.start();
  } else {
    console.log(message);
  }
}

/**
 * Stops the active spinner with a success mark.
 * @param {string} [text] - Optional final text to display.
 */
export function succeedSpinner(text) {
  if (activeSpinner) {
    activeSpinner.succeed(text);
    activeSpinner = null;
  }
}

/**
 * Stops the active spinner with a failure mark.
 * @param {string} [text] - Optional final text to display.
 */
export function failSpinner(text) {
  if (activeSpinner) {
    activeSpinner.fail(text);
    activeSpinner = null;
  }
}

/**
 * Stops the active spinner without any status mark.
 */
export function stopSpinner() {
  if (activeSpinner) {
    activeSpinner.stop();
    activeSpinner = null;
  }
}
