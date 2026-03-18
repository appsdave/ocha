/**
 * @module beads
 * Integration with the beads (bd) issue tracker for multi-agent task coordination.
 *
 * Beads prevents merge conflicts in multi-agent workflows by:
 * - Tracking each task as a beads issue with atomic claim/close semantics
 * - Providing dependency-aware scheduling so agents don't step on each other
 * - Syncing state through Dolt (git-versioned database) instead of file conflicts
 *
 * All bd commands use --json for reliable parsing and run non-interactively.
 */
import { exec } from './exec.js';

const BD = 'bd';

/**
 * Check whether beads is initialized in the given project directory.
 * @param {string} [cwd] - Project directory (defaults to process.cwd()).
 * @returns {boolean}
 */
export function isBeadsInitialized(cwd) {
  try {
    exec(BD, ['list', '--json'], { cwd, timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Ensure the Dolt server is running (beads requires it).
 * Safe to call multiple times — bd handles idempotent starts.
 * @param {string} [cwd] - Project directory.
 */
export function ensureDoltServer(cwd) {
  try {
    exec(BD, ['dolt', 'start'], { cwd, timeout: 15_000 });
  } catch {
    // Server may already be running — that's fine
  }
}

/**
 * Create a beads issue for a task.
 * @param {string} title - Short task title.
 * @param {string} description - Full task description.
 * @param {object} [opts] - Extra options.
 * @param {string} [opts.type='task'] - Issue type (bug, feature, task, epic, chore).
 * @param {number} [opts.priority=2] - Priority 0-4.
 * @param {string} [opts.parentId] - Parent issue ID for discovered-from linking.
 * @param {string} [opts.cwd] - Working directory.
 * @returns {string|null} The created issue ID, or null on failure.
 */
export function createBeadsIssue(title, description, opts = {}) {
  const { type = 'task', priority = 2, parentId, cwd } = opts;
  try {
    const args = ['create', title, `--description=${description}`, '-t', type, '-p', String(priority)];
    if (parentId) args.push('--deps', `discovered-from:${parentId}`);
    args.push('--json');
    const out = exec(BD, args, { cwd, timeout: 15_000 });
    const data = JSON.parse(out);
    return data.id || data.issue_id || null;
  } catch {
    return null;
  }
}

/**
 * Atomically claim a beads issue for the current agent.
 * @param {string} issueId - Beads issue ID (e.g. "ocha-a3f2dd").
 * @param {string} [cwd] - Working directory.
 * @returns {boolean} True if claimed successfully.
 */
export function claimBeadsIssue(issueId, cwd) {
  try {
    exec(BD, ['update', issueId, '--claim', '--json'], { cwd, timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Close a beads issue with a reason.
 * @param {string} issueId - Beads issue ID.
 * @param {string} [reason='Completed by ocha agent'] - Closure reason.
 * @param {string} [cwd] - Working directory.
 * @returns {boolean} True if closed successfully.
 */
export function closeBeadsIssue(issueId, reason = 'Completed by ocha agent', cwd) {
  try {
    exec(BD, ['close', issueId, '--reason', reason, '--json'], { cwd, timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Push beads data to remote via Dolt.
 * @param {string} [cwd] - Working directory.
 * @returns {boolean}
 */
export function pushBeadsData(cwd) {
  try {
    exec(BD, ['dolt', 'push'], { cwd, timeout: 30_000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Get ready (unblocked, unclaimed) issues.
 * @param {string} [cwd] - Working directory.
 * @returns {Array<object>} Array of ready issues.
 */
export function getReadyIssues(cwd) {
  try {
    const out = exec(BD, ['ready', '--json'], { cwd, timeout: 10_000 });
    const data = JSON.parse(out);
    return Array.isArray(data) ? data : (data.issues || []);
  } catch {
    return [];
  }
}
