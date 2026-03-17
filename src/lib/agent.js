import { spawn } from 'child_process';
import { resolve } from 'path';
import { readFileSync, existsSync } from 'fs';
import { OCHA_DIR } from './paths.js';
import { updateTask } from './status.js';
import chalk from 'chalk';

const runningAgents = new Map();

export function spawnAgent(task, worktreePath, role) {
  const outputFile = resolve(OCHA_DIR, `${task.id}-output.json`);
  const rolePrompt = loadRolePrompt(role);
  const fullTask = `${rolePrompt}\n\n## Your Task\n${task.description}`;

  const proc = spawn('junie', [
    '--project', worktreePath,
    '--task', fullTask,
    '--json-output-file', outputFile,
    '--brave',
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
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

  const prefix = chalk.gray(`  │ [${task.id}] `);

  // Show only key lines from agent output (nested, filtered)
  const handleData = (data) => {
    const lines = data.toString().split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      // Show only important lines: task results, thinking, errors, commits
      if (
        trimmed.startsWith('● TASK RESULT:') ||
        trimmed.startsWith('● Thinking') ||
        trimmed.startsWith('TASK RESULT:') ||
        trimmed.includes('error') ||
        trimmed.includes('Error') ||
        trimmed.startsWith('Authenticated') ||
        trimmed.includes('committed') ||
        trimmed.includes('commit ')
      ) {
        console.log(prefix + trimmed);
      }
    }
  };

  proc.stdout.on('data', handleData);
  proc.stderr.on('data', handleData);

  return new Promise((resolveP, reject) => {
    proc.on('close', (code) => {
      runningAgents.delete(task.id);
      const result = readAgentOutput(outputFile);
      updateTask(task.id, {
        state: code === 0 ? 'completed' : 'failed',
        completedAt: new Date().toISOString(),
        exitCode: code,
        result,
      });
      resolveP({ code, result, taskId: task.id });
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
      process.kill(-proc.pid, 'SIGTERM');
    } catch {
      try { proc.kill('SIGTERM'); } catch {}
    }
    runningAgents.delete(taskId);
  }
}

export function getRunningAgents() {
  return [...runningAgents.keys()];
}
