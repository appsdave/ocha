/**
 * @module issues
 * Agent issue feed — lets agents report problems, warnings, and notes
 * during execution. Issues are persisted to .ocha/issues.json so the
 * coordinator and TUI can surface them to the user.
 */
import { readJSON, writeJSON } from './files.js';
import { ISSUES_FILE } from './paths.js';

/**
 * @typedef {'error'|'warning'|'info'} IssueLevel
 *
 * @typedef {object} Issue
 * @property {string}     taskId     - ID of the task that reported the issue.
 * @property {IssueLevel} level      - Severity level of the issue.
 * @property {string}     message    - Human-readable description.
 * @property {string}     [detail]   - Optional extra context (stack trace, file path, etc.).
 * @property {string}     reportedAt - ISO timestamp when the issue was recorded.
 */

/**
 * Appends a new issue entry to the issues feed file.
 *
 * @param {string}     taskId  - The reporting agent's task ID.
 * @param {IssueLevel} level   - Severity: 'error' | 'warning' | 'info'.
 * @param {string}     message - Short description of the issue.
 * @param {string}     [detail] - Optional additional context.
 * @returns {Issue} The issue object that was recorded.
 */
export function reportIssue(taskId, level, message, detail) {
  const issues = readJSON(ISSUES_FILE, []);

  /** @type {Issue} */
  const issue = {
    taskId,
    level,
    message,
    ...(detail !== undefined && { detail }),
    reportedAt: new Date().toISOString(),
  };

  issues.push(issue);
  writeJSON(ISSUES_FILE, issues);
  return issue;
}

/**
 * Returns all recorded issues, optionally filtered by task ID.
 *
 * @param {string} [taskId] - When provided, returns only issues for that task.
 * @returns {Issue[]} Array of matching issue objects (empty array if none).
 */
export function getIssues(taskId) {
  const issues = readJSON(ISSUES_FILE, []);
  if (taskId !== undefined) {
    return issues.filter(i => i.taskId === taskId);
  }
  return issues;
}

/**
 * Removes all recorded issues from the feed.
 * Useful when starting a fresh session.
 */
export function clearIssues() {
  writeJSON(ISSUES_FILE, []);
}
