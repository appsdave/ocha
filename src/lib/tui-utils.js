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

/**
 * Format a clean completion summary block for the log pane.
 * @param {object} agent
 * @returns {string[]}
 */
export function formatCompletionSummary(agent) {
  const lines = [];
  const divider = '─'.repeat(48);
  lines.push('');
  lines.push(divider);
  if (agent.state === 'completed') {
    lines.push('  ✅  Agent completed successfully');
  } else if (agent.state === 'failed') {
    lines.push('  ❌  Agent failed');
  } else if (agent.state === 'stopped') {
    lines.push('  ■   Agent stopped by user');
  }
  lines.push(`  Task   : ${agent.task}`);
  lines.push(`  Branch : ${agent.branch}`);
  if (agent.startedAt && agent.completedAt) {
    const secs = Math.round((new Date(agent.completedAt) - new Date(agent.startedAt)) / 1000);
    lines.push(`  Duration: ${secs}s`);
  }
  if (agent.prUrl) {
    lines.push(`  PR     : ${agent.prUrl}`);
  }
  lines.push(divider);
  lines.push('');
  return lines;
}

/**
 * Truncate a task description to `max` characters, breaking at a word
 * boundary where possible and appending an ellipsis.
 * @param {string} text
 * @param {number} max
 * @returns {string}
 */
export function truncateTask(text, max) {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  const lastSpace = cut.lastIndexOf(' ');
  return (lastSpace > max * 0.5 ? cut.slice(0, lastSpace) : cut) + '…';
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
