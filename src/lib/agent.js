import { spawn } from 'child_process';
import { resolve } from 'path';
import { readFileSync, existsSync } from 'fs';
import { OCHA_DIR } from './paths.js';
import { updateTask } from './status.js';

const runningAgents = new Map();

export function spawnAgent(task, worktreePath, role) {
  const outputFile = resolve(OCHA_DIR, `${task.id}-output.json`);
  const rolePrompt = loadRolePrompt(role);
  const fullTask = `${rolePrompt}\n\n## Your Task\n${task.description}`;

  const proc = spawn('junie', [
    '--project', worktreePath,
    '--task', fullTask,
    '--json-output-file', outputFile,
  ], {
    stdio: 'inherit',
    detached: false,
  });

  runningAgents.set(task.id, { proc, outputFile, worktreePath });

  updateTask(task.id, {
    state: 'running',
    worktree: worktreePath,
    outputFile,
    startedAt: new Date().toISOString(),
    pid: proc.pid,
  });

  return new Promise((resolve, reject) => {
    proc.on('close', (code) => {
      runningAgents.delete(task.id);
      const result = readAgentOutput(outputFile);
      updateTask(task.id, {
        state: code === 0 ? 'completed' : 'failed',
        completedAt: new Date().toISOString(),
        exitCode: code,
        result,
      });
      resolve({ code, result, taskId: task.id });
    });
    proc.on('error', (err) => {
      runningAgents.delete(task.id);
      updateTask(task.id, {
        state: 'failed',
        completedAt: new Date().toISOString(),
        error: err.message,
      });
      reject(err);
    });
  });
}

function readAgentOutput(outputFile) {
  if (!existsSync(outputFile)) return null;
  try {
    return JSON.parse(readFileSync(outputFile, 'utf-8'));
  } catch {
    return null;
  }
}

function loadRolePrompt(role) {
  const rolePath = resolve(OCHA_DIR, 'roles', `${role}.md`);
  if (existsSync(rolePath)) {
    return readFileSync(rolePath, 'utf-8');
  }
  return `You are a ${role} agent. Complete the assigned task thoroughly.`;
}

export function killAllAgents() {
  for (const [taskId, { proc }] of runningAgents) {
    try {
      proc.kill('SIGTERM');
    } catch {}
    runningAgents.delete(taskId);
  }
}

export function getRunningAgents() {
  return [...runningAgents.keys()];
}
