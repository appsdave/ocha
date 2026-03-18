/**
 * @module ui
 * Shared terminal UI utilities for responsive layout and aesthetics.
 */
import chalk from 'chalk';

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
   
  return str.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, '');
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

/**
 * Renders a responsive bordered box to the console.
 *
 * @param {string} title         - Title shown in the top border (plain text, no ANSI).
 * @param {string[][]} rows      - Each row is [label, value] or [value] (full-width).
 * @param {object}  [opts]
 * @param {number}  [opts.minWidth=52]  - Minimum box width (columns).
 * @param {number}  [opts.maxWidth=80]  - Maximum box width (columns).
 * @param {Function}[opts.borderColor]  - chalk colour fn for the border. Default: chalk.bold.blue
 */
export function drawBox(title, rows, opts = {}) {
  const {
    minWidth = 52,
    maxWidth = 80,
    borderColor = chalk.bold.blue,
  } = opts;

  const termWidth = getTerminalWidth();
  const boxWidth  = Math.max(minWidth, Math.min(termWidth - 2, maxWidth));
  // Inner width: box edges (2) + padding spaces (2 left, 1 right) = 5 overhead
  const innerWidth = boxWidth - 5;

  // Top border
  const titleStr   = ` ${title} `;
  const dashCount  = Math.max(1, boxWidth - 2 - stripAnsi(titleStr).length - 1);
  console.log(borderColor(`\n┌─${titleStr}${'─'.repeat(dashCount)}┐`));

  // Rows
  for (const row of rows) {
    if (row.length === 0) {
      // blank separator line
      console.log(borderColor('│') + ' '.repeat(boxWidth - 2) + borderColor('│'));
      continue;
    }
    if (row.length === 1) {
      // full-width value, no label
      const lines = wrapText(String(row[0]), innerWidth + 2);
      for (const line of lines) {
        const pad = ' '.repeat(Math.max(0, innerWidth + 2 - stripAnsi(line).length));
        console.log(borderColor('│') + '  ' + line + pad + ' ' + borderColor('│'));
      }
      continue;
    }
    // [label, value] pair
    const label      = String(row[0]);
    const value      = String(row[1]);
    const labelCols  = stripAnsi(label).length;
    const valueWidth = Math.max(1, innerWidth - labelCols - 1);
    const lines      = wrapText(stripAnsi(value) ? value : ' ', valueWidth);
    const first      = lines[0];
    const firstPad   = ' '.repeat(Math.max(0, valueWidth - stripAnsi(first).length));
    console.log(borderColor('│') + `  ${label} ${first}${firstPad} ` + borderColor('│'));
    for (let i = 1; i < lines.length; i++) {
      const indent = ' '.repeat(labelCols + 1);
      const pad    = ' '.repeat(Math.max(0, valueWidth - stripAnsi(lines[i]).length));
      console.log(borderColor('│') + `  ${indent}${lines[i]}${pad} ` + borderColor('│'));
    }
  }

  // Bottom border
  console.log(borderColor('└' + '─'.repeat(boxWidth - 2) + '┘'));
}

/**
 * Renders a horizontal progress bar string.
 *
 * @param {number} done   - Number of completed items.
 * @param {number} total  - Total number of items.
 * @param {number} [width=20] - Visual width of the bar in characters.
 * @returns {string} Coloured bar, e.g. "████████░░░░  4/10"
 */
export function progressBar(done, total, width = 20) {
  if (total <= 0) return chalk.gray('─'.repeat(width) + '  0/0');
  const ratio   = Math.min(1, Math.max(0, done / total));
  const filled  = Math.round(ratio * width);
  const empty   = width - filled;
  const bar     = chalk.green('█'.repeat(filled)) + chalk.gray('░'.repeat(empty));
  const pct     = `${done}/${total}`;
  return `${bar}  ${chalk.bold(pct)}`;
}

/**
 * Returns a short coloured badge string for a task/session state.
 *
 * @param {string} state - e.g. 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
 * @returns {string} Chalk-coloured badge text.
 */
export function badge(state) {
  switch (state) {
    case 'completed': return chalk.bgGreen.black(` ${state} `);
    case 'running':   return chalk.bgYellow.black(` ${state} `);
    case 'failed':    return chalk.bgRed.white(` ${state} `);
    case 'stopped':   return chalk.bgGray.white(` ${state} `);
    case 'pending':   return chalk.bgBlackBright.white(` ${state} `);
    default:          return chalk.bgWhite.black(` ${state} `);
  }
}
