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

/**
 * Format a duration between two ISO timestamps as a human-readable string.
 * Returns compact forms like "1m 30s", "45s", or "--:--" if timestamps are missing.
 * @param {string|null} startedAt
 * @param {string|null} completedAt
 * @returns {string}
 */
export function formatDuration(startedAt, completedAt) {
  if (!startedAt || !completedAt) return '--:--';
  const secs = Math.max(0, Math.round((new Date(completedAt) - new Date(startedAt)) / 1000));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
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
 * Word-wrap text to fit within a given width, breaking at word boundaries.
 * Returns an array of lines. Long words that exceed the width are broken
 * mid-word so nothing overflows.
 * @param {string} text
 * @param {number} width - maximum characters per line
 * @param {number} [maxLines=0] - if >0, limit output to this many lines (last line gets ellipsis)
 * @returns {string[]}
 */
export function wrapText(text, width, maxLines = 0) {
  if (!text) return [''];
  if (width <= 0) return [text];

  const words = text.split(/\s+/);
  const lines = [];
  let current = '';

  for (const word of words) {
    if (!word) continue;

    // Word fits on the current line
    if (current.length === 0) {
      current = word;
    } else if (current.length + 1 + word.length <= width) {
      current += ' ' + word;
    } else {
      lines.push(current);
      current = word;
    }

    // Break long words that exceed the width
    while (current.length > width) {
      lines.push(current.slice(0, width));
      current = current.slice(width);
    }
  }

  if (current.length > 0) {
    lines.push(current);
  }

  if (lines.length === 0) return [''];

  if (maxLines > 0 && lines.length > maxLines) {
    const truncated = lines.slice(0, maxLines);
    const last = truncated[maxLines - 1];
    truncated[maxLines - 1] = last.length >= width - 1
      ? last.slice(0, width - 1) + '…'
      : last + '…';
    return truncated;
  }

  return lines;
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

/**
 * Workflow event patterns recognised from raw log lines.
 * Each pattern maps to an icon, a phase label, and a regex to extract detail.
 * Order matters — first match wins.
 * @type {{ icon: string, phase: string, pattern: RegExp, extract?: number }[]}
 */
const WORKFLOW_PATTERNS = [
  { icon: '🔗', phase: 'beads',       pattern: /Beads \(bd\) issue tracking active/ },
  { icon: '🔗', phase: 'beads',       pattern: /Beads issue (\S+)/, extract: 0 },
  { icon: '🧠', phase: 'coordinator', pattern: /Prompt enhanced with project context/ },
  { icon: '⚠',  phase: 'coordinator', pattern: /No project context found/ },
  { icon: '📋', phase: 'coordinator', pattern: /Checking prerequisites/ },
  { icon: '👔', phase: 'lead',        pattern: /Lead planned (\d+ task\(s\).*)/, extract: 1 },
  { icon: '👔', phase: 'lead',        pattern: /Lead agent (.*)/, extract: 1 },
  { icon: '🎯', phase: 'dispatch',    pattern: /Coordinator dispatching (.*)/, extract: 1 },
  { icon: '🔨', phase: 'builder',     pattern: /Builder done: (.*)/, extract: 1 },
  { icon: '↺',  phase: 'builder',     pattern: /Builder failed \(attempt (.*)\)/, extract: 0 },
  { icon: '✗',  phase: 'builder',     pattern: /Builder failed after (.*)/, extract: 0 },
  { icon: '✗',  phase: 'builder',     pattern: /Builder error (.*)/, extract: 0 },
  { icon: '🔍', phase: 'reviewer',    pattern: /Reviewer checking: (.*)/, extract: 1 },
  { icon: '✓',  phase: 'reviewer',    pattern: /Review passed: (.*)/, extract: 1 },
  { icon: '⚠',  phase: 'reviewer',    pattern: /Review flagged issues: (.*)/, extract: 1 },
  { icon: '⚠',  phase: 'reviewer',    pattern: /Reviewer failed (.*)/, extract: 0 },
  { icon: '📤', phase: 'push',        pattern: /Pushed branch (\S+)/, extract: 1 },
  { icon: '🔗', phase: 'PR',          pattern: /PR created: (.*)/, extract: 1 },
  { icon: '🔗', phase: 'PR',          pattern: /PR already exists: (.*)/, extract: 1 },
  { icon: '📋', phase: 'diff',        pattern: /Changes in (.*)/, extract: 1 },
];

/**
 * Parse raw log lines into structured workflow events.
 * Each event has { icon, phase, message, raw }.
 * Non-matching lines are skipped.
 *
 * @param {string[]} logs
 * @returns {{ icon: string, phase: string, message: string, raw: string }[]}
 */
export function parseWorkflowEvents(logs) {
  const events = [];
  for (const line of logs) {
    const stripped = line.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '').trim();
    if (!stripped) continue;
    for (const wp of WORKFLOW_PATTERNS) {
      const m = stripped.match(wp.pattern);
      if (m) {
        const detail = wp.extract !== undefined ? m[wp.extract] : '';
        const message = detail ? `${m[0]}` : m[0];
        events.push({ icon: wp.icon, phase: wp.phase, message, raw: stripped });
        break;
      }
    }
  }
  return events;
}

/**
 * Render structured workflow output for the log pane using blessed tags.
 * Returns an array of blessed-tagged lines showing a clean event timeline.
 *
 * @param {string[]} logs   - Raw log lines from the agent.
 * @param {object}   agent  - The agent object (for state, branch, prUrl, etc.).
 * @returns {string[]}
 */
export function renderWorkflowOutput(logs, agent) {
  const events = parseWorkflowEvents(logs);
  const lines = [];

  // Event timeline
  const phaseColors = {
    beads:       '{grey-fg}',
    coordinator: '{white-fg}',
    lead:        '{cyan-fg}',
    dispatch:    '{blue-fg}',
    builder:     '{yellow-fg}',
    reviewer:    '{magenta-fg}',
    push:        '{green-fg}',
    PR:          '{cyan-fg}',
    diff:        '{grey-fg}',
  };

  for (const event of events) {
    const color = phaseColors[event.phase] || '{white-fg}';
    lines.push(`  ${event.icon}  ${color}${escapeBlessedTags(event.message)}{/}`);
  }

  // Spinner for running agents
  if (agent.state === 'running' && events.length > 0) {
    const lastPhase = events[events.length - 1].phase;
    const spinFrames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
    const frame = spinFrames[Math.floor(Date.now() / 100) % spinFrames.length];
    lines.push(`  {yellow-fg}${frame}  ${lastPhase} in progress…{/yellow-fg}`);
  }

  // Completion summary for finished agents
  if (agent.state === 'completed' || agent.state === 'failed' || agent.state === 'stopped') {
    lines.push('');
    lines.push('{grey-fg}' + '─'.repeat(52) + '{/grey-fg}');
    if (agent.state === 'completed') {
      lines.push('  {green-fg}{bold}✅  Agent completed successfully{/bold}{/green-fg}');
    } else if (agent.state === 'failed') {
      lines.push('  {red-fg}{bold}❌  Agent failed{/bold}{/red-fg}');
    } else {
      lines.push('  {grey-fg}{bold}■   Agent stopped by user{/bold}{/grey-fg}');
    }
    if (agent.prUrl) {
      lines.push(`  {cyan-fg}PR: ${escapeBlessedTags(agent.prUrl)}{/cyan-fg}`);
    }
    if (agent.startedAt && agent.completedAt) {
      const secs = Math.round((new Date(agent.completedAt) - new Date(agent.startedAt)) / 1000);
      const mins = Math.floor(secs / 60);
      const rem = secs % 60;
      const duration = mins > 0 ? `${mins}m ${rem}s` : `${secs}s`;
      lines.push(`  {grey-fg}Duration: ${duration}{/grey-fg}`);
    }
    lines.push('{grey-fg}' + '─'.repeat(52) + '{/grey-fg}');
  }

  return lines;
}

/** Escape blessed tag characters in text for safe display. */
function escapeBlessedTags(str) {
  if (!str) return '';
  return str.replace(/\{/g, '\\{').replace(/\}/g, '\\}');
}
