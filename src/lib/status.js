/**
 * @module status
 * Session status management — read, write, and update task state
 * in the .ocha/status.json file.
 */
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { STATUS_FILE } from './paths.js';

/**
 * Reads the current session status from disk.
 * @returns {object|null} The parsed status object, or null if no status file exists.
 */
export function readStatus() {
  if (!existsSync(STATUS_FILE)) return null;
  return JSON.parse(readFileSync(STATUS_FILE, 'utf-8'));
}

/**
 * Writes a status object to the status file.
 * @param {object} status - The status object to persist.
 */
export function writeStatus(status) {
  writeFileSync(STATUS_FILE, JSON.stringify(status, null, 2));
}

/**
 * Updates a specific task within the status file by merging new properties.
 * @param {string} taskId - The ID of the task to update (e.g. "task-1").
 * @param {object} updates - Key-value pairs to merge into the task object.
 */
export function updateTask(taskId, updates) {
  const status = readStatus();
  if (!status) return;
  const task = status.tasks.find(t => t.id === taskId);
  if (task) Object.assign(task, updates);
  writeStatus(status);
}

/**
 * Creates an initial status object for a new session.
 * @param {string} sessionTask - The high-level task description.
 * @param {Array<{description: string, role?: string, branch?: string}>} tasks - Decomposed subtasks.
 * @returns {object} A status object with session metadata and task entries.
 */
export function createInitialStatus(sessionTask, tasks) {
  return {
    session: {
      task: sessionTask,
      startedAt: new Date().toISOString(),
      state: 'running',
    },
    tasks: tasks.map((t, i) => ({
      id: `task-${i + 1}`,
      description: t.description,
      role: t.role || 'builder',
      branch: t.branch || `ocha/task-${i + 1}`,
      state: 'pending',
      worktree: null,
      outputFile: null,
      result: null,
      startedAt: null,
      completedAt: null,
    })),
  };
}
