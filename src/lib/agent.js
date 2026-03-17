import { spawn, execSync } from 'child_process';
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
      // If we got auth during --version, that's fine
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
