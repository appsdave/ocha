/**
 * @module agent
 * Agent spawning, lifecycle management, and output handling.
 * Each agent is a Junie child process running in an isolated git worktree.
 */
import { spawn } from 'child_process';
import { resolve } from 'path';
import { readJSON, readText, pathExists } from './files.js';
import { OCHA_DIR } from './paths.js';
import { updateTask } from './status.js';
import chalk from 'chalk';

/** @type {Map<string, {proc: ChildProcess, outputFile: string, worktreePath: string}>} */
const runningAgents = new Map();

/**
 * Spawns a Junie agent process for a given task.
 * The agent runs in the specified worktree with the given role prompt.
 * Updates the status file with running/completed/failed state.
 *
 * @param {object} task - The task object from status (must have id, description).
 * @param {string} worktreePath - Absolute path to the git worktree.
 * @param {string} role - Agent role name (e.g. "builder", "reviewer").
 * @returns {Promise<{code: number, result: object|null, taskId: string}>} Resolves when the agent exits.
 */
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

/**
 * Reads and parses the JSON output file produced by a Junie agent.
 * @param {string} outputFile - Path to the agent's output JSON file.
 * @returns {object|null} Parsed output, or null if missing/invalid.
 */
function readAgentOutput(outputFile) {
  return readJSON(outputFile);
}

/**
 * Loads the markdown role prompt for a given agent role.
 * Falls back to a generic prompt if the role file doesn't exist.
 * @param {string} role - Role name (e.g. "builder").
 * @returns {string} The role prompt content.
 */
function loadRolePrompt(role) {
  const rolePath = resolve(OCHA_DIR, 'roles', `${role}.md`);
  return readText(rolePath, `You are a ${role} agent. Complete the assigned task thoroughly.`);
}

/**
 * Terminates all currently running agent processes via SIGTERM.
 * Clears the internal running agents map.
 */
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

/**
 * Returns the task IDs of all currently running agents.
 * @returns {string[]} Array of task IDs.
 */
export function getRunningAgents() {
  return [...runningAgents.keys()];
}
