import { readFileSync, writeFileSync, existsSync } from 'fs';
import { STATUS_FILE } from './paths.js';

export function readStatus() {
  if (!existsSync(STATUS_FILE)) return null;
  return JSON.parse(readFileSync(STATUS_FILE, 'utf-8'));
}

export function writeStatus(status) {
  writeFileSync(STATUS_FILE, JSON.stringify(status, null, 2));
}

export function updateTask(taskId, updates) {
  const status = readStatus();
  if (!status) return;
  const task = status.tasks.find(t => t.id === taskId);
  if (task) Object.assign(task, updates);
  writeStatus(status);
}

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
