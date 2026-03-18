/**
 * @module ui
 * Shared terminal UI utilities for responsive layout.
 */

/**
 * Returns the current terminal column width, defaulting to 80.
 * @returns {number}
 */
export function getTerminalWidth() {
  return process.stdout.columns || 80;
}

/**
 * Strips ANSI escape codes from a string so its visible length can be measured.
 * @param {string} str
 * @returns {string}
 */
export function stripAnsi(str) {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1B\[[0-9;]*m/g, '');
}

/**
 * Wraps `text` at word boundaries so each line fits within `width` columns.
 * Returns an array of lines. Always returns at least one element.
 * @param {string} text
 * @param {number} width - Max visible characters per line.
 * @returns {string[]}
 */
export function wrapText(text, width) {
  if (!text) return [''];
  if (width <= 0) return [text];

  const words = text.split(/\s+/);
  const lines = [];
  let current = '';

  for (const word of words) {
    if (!current) {
      current = word;
    } else if (current.length + 1 + word.length <= width) {
      current += ' ' + word;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines.length ? lines : [''];
}
