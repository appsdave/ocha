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
 * Shows status, branch, duration and PR — task is already visible in the log header.
 * @param {object} agent
 * @returns {string[]}
 */
export function formatCompletionSummary(agent) {
  const lines = [];
  const divider = '─'.repeat(52);
  lines.push('');
  lines.push(divider);
  if (agent.state === 'completed') {
    lines.push('  ✅  Agent completed successfully');
  } else if (agent.state === 'failed') {
    lines.push('  ❌  Agent failed');
  } else if (agent.state === 'stopped') {
    lines.push('  ■   Agent stopped by user');
  }
  if (agent.repo) {
    lines.push(`  Repo     : ${agent.repo}`);
  }
  lines.push(`  Branch   : ${agent.branch || 'unknown'}`);
  if (agent.startedAt && agent.completedAt) {
    const secs = Math.round((new Date(agent.completedAt) - new Date(agent.startedAt)) / 1000);
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    const duration = mins > 0 ? `${mins}m ${remaining}s` : `${secs}s`;
    lines.push(`  Duration : ${duration}`);
  }
  if (agent.prUrl) {
    lines.push(`  PR       : ${agent.prUrl}`);
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

/**
 * Sort agents for display: running/active agents first, then
 * completed/failed/stopped agents at the bottom.
 * Returns a new array of { agent, originalIndex } objects.
 * @param {object[]} agents
 * @returns {{ agent: object, originalIndex: number }[]}
 */
export function sortAgentsForDisplay(agents) {
  const active = [];
  const done = [];
  agents.forEach((agent, i) => {
    const entry = { agent, originalIndex: i };
    if (agent.state === 'running') {
      active.push(entry);
    } else {
      done.push(entry);
    }
  });
  return [...active, ...done];
}

/**
 * Apply blessed strikethrough styling to text.
 * Uses Unicode combining long stroke overlay (U+0336) since blessed
 * does not support native strikethrough escape sequences.
 * Skips blessed escape sequences (\{ and \}) so tag parsing is preserved.
 * @param {string} text
 * @returns {string}
 */
export function strikethrough(text) {
  let result = '';
  for (let i = 0; i < text.length; i++) {
    if (text[i] === '\\' && i + 1 < text.length && (text[i + 1] === '{' || text[i + 1] === '}')) {
      // Preserve blessed escape sequences without strikethrough
      result += text[i] + text[i + 1];
      i++;
    } else {
      result += text[i] + '\u0336';
    }
  }
  return result;
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
