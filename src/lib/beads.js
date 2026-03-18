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
import { execSync } from 'child_process';

const BD = 'bd';

/**
 * Check whether beads is initialized in the given project directory.
 * @param {string} [cwd] - Project directory (defaults to process.cwd()).
 * @returns {boolean}
 */
export function isBeadsInitialized(cwd) {
  try {
    execSync(`${BD} list --json`, { cwd, stdio: 'pipe', encoding: 'utf-8', timeout: 10000 });
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
    execSync(`${BD} dolt start`, { cwd, stdio: 'pipe', timeout: 15000 });
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
    const depsFlag = parentId ? ` --deps discovered-from:${parentId}` : '';
    const safeTitle = title.replace(/"/g, '\\"');
    const safeDesc = description.replace(/"/g, '\\"').replace(/\n/g, '\\n');
    const cmd = `${BD} create "${safeTitle}" --description="${safeDesc}" -t ${type} -p ${priority}${depsFlag} --json`;
    const out = execSync(cmd, { cwd, stdio: 'pipe', encoding: 'utf-8', timeout: 15000 });
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
    execSync(`${BD} update ${issueId} --claim --json`, { cwd, stdio: 'pipe', encoding: 'utf-8', timeout: 10000 });
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
    const safeReason = reason.replace(/"/g, '\\"');
    execSync(`${BD} close ${issueId} --reason "${safeReason}" --json`, { cwd, stdio: 'pipe', encoding: 'utf-8', timeout: 10000 });
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
    execSync(`${BD} dolt push`, { cwd, stdio: 'pipe', encoding: 'utf-8', timeout: 30000 });
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
    const out = execSync(`${BD} ready --json`, { cwd, stdio: 'pipe', encoding: 'utf-8', timeout: 10000 });
    const data = JSON.parse(out);
    return Array.isArray(data) ? data : (data.issues || []);
  } catch {
    return [];
  }
}
