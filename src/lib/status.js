/**
 * @module status
 * Session status management — read, write, and update task state
 * in the .ocha/status.json file.
 */
import { readJSON, writeJSON } from './files.js';
import { STATUS_FILE } from './paths.js';

/**
 * Reads the current session status from disk.
 * @returns {object|null} The parsed status object, or null if no status file exists.
 */
export function readStatus() {
  return readJSON(STATUS_FILE);
}

/**
 * Writes a status object to the status file.
 * @param {object} status - The status object to persist.
 */
export function writeStatus(status) {
  writeJSON(STATUS_FILE, status);
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
  const status = {
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
  writeJSON(STATUS_FILE, status);
  return status;
}
