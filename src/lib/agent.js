/**
 * @module agent
 * Agent spawning, lifecycle management, and output handling.
 * Each agent is a Junie child process running in an isolated git worktree.
 */
import { spawn, execSync } from 'child_process';
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
      // Show important lines: results, thinking, auth, commits, file ops
      if (
        trimmed.startsWith('● TASK RESULT:') ||
        trimmed.startsWith('● Thinking') ||
        trimmed.startsWith('TASK RESULT:') ||
        trimmed.startsWith('Authenticated') ||
        trimmed.includes('committed') ||
        trimmed.includes('commit ') ||
        trimmed.startsWith('● cd ') ||
        trimmed.startsWith('● cat ') ||
        trimmed.startsWith('● find ') ||
        trimmed.startsWith('● mkdir ') ||
        trimmed.includes('created') ||
        trimmed.includes('updated') ||
        trimmed.includes('Added') ||
        trimmed.includes('Modified') ||
        trimmed.includes('Wrote') ||
        trimmed.includes('Writing')
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

      // Auto push the branch after agent completes successfully
      if (code === 0) {
        try {
          execSync(`cd "${worktreePath}" && git push -u origin ${task.branch} --force`, { stdio: 'pipe' });
          console.log(prefix + chalk.green('Pushed branch to origin'));
        } catch {
          console.log(prefix + chalk.yellow('Could not push branch (no remote or auth issue)'));
        }
      }

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
 * Checks that Junie authentication is valid by running `junie --version`.
 * @returns {Promise<boolean>} Resolves true if authenticated.
 */
export function ensureAuthenticated() {
  return new Promise((resolveP, reject) => {
    const proc = spawn('junie', ['--version'], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let authenticated = false;
    let output = '';

    const handleData = (data) => {
      const text = data.toString();
      output += text;
      if (text.includes('Authenticated successfully')) {
        authenticated = true;
      }
    };

    proc.stdout.on('data', handleData);
    proc.stderr.on('data', handleData);

    const timeout = setTimeout(() => {
      proc.kill();
      if (authenticated) resolveP(true);
      else reject(new Error('Authentication timed out'));
    }, 30000);

    proc.on('close', () => {
      clearTimeout(timeout);
      resolveP(true);
    });

    proc.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
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
