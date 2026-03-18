/**
 * @module tui-utils
 * Shared utility functions for the TUI: slugify, elapsed time, badge helpers.
 */

/** Slugify a task description for use in branch/worktree names */
export function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

/** Format elapsed seconds as mm:ss */
export function elapsed(startedAt) {
  if (!startedAt) return '--:--';
  const secs = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  const m = Math.floor(secs / 60).toString().padStart(2, '0');
  const s = (secs % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

/** Status badge text */
export function badgeText(state) {
  switch (state) {
    case 'running':   return ' ● ';
    case 'completed': return ' ✔ ';
    case 'failed':    return ' ✗ ';
    case 'stopped':   return ' ■ ';
    default:          return ' ○ ';
  }
}

/** Status badge blessed color tag */
export function badgeColor(state) {
  switch (state) {
    case 'running':   return '{yellow-fg}';
    case 'completed': return '{green-fg}';
    case 'failed':    return '{red-fg}';
    case 'stopped':   return '{grey-fg}';
    default:          return '{white-fg}';
  }
}
