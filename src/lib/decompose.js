import { spawn } from 'child_process';
import { resolve } from 'path';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { OCHA_DIR } from './paths.js';

const DECOMPOSE_PROMPT = `You are a task decomposition agent. Given a high-level task, break it into independent subtasks that can be worked on in parallel in separate git worktrees.

Output ONLY valid JSON (no markdown fences) in this exact format:
{
  "tasks": [
    { "description": "...", "role": "builder", "branch": "ocha/descriptive-branch-name" }
  ]
}

Roles available: builder (writes code), reviewer (reviews code), lead (coordinates sub-work).
Keep subtasks focused and independent. Use descriptive branch names prefixed with "ocha/".`;

export async function decomposeTask(task) {
  const outputFile = resolve(OCHA_DIR, 'decompose-output.json');

  // First try: use Junie to decompose
  try {
    const result = await runJunieDecompose(task, outputFile);
    if (result && result.tasks && result.tasks.length > 0) {
      return result.tasks;
    }
  } catch {
    // Fall through to simple decomposition
  }

  // Fallback: treat the whole task as a single builder task
  return [{
    description: task,
    role: 'builder',
    branch: 'ocha/main-task',
  }];
}

function runJunieDecompose(task, outputFile) {
  const fullPrompt = `${DECOMPOSE_PROMPT}\n\nTask to decompose:\n${task}`;

  return new Promise((resolve, reject) => {
    const proc = spawn('junie', [
      '--project', process.cwd(),
      '--task', fullPrompt,
      '--json-output-file', outputFile,
    ], { stdio: 'inherit' });

    const timeout = setTimeout(() => {
      proc.kill();
      reject(new Error('Decomposition timed out'));
    }, 120000);

    proc.on('close', (code) => {
      clearTimeout(timeout);
      if (existsSync(outputFile)) {
        try {
          const data = JSON.parse(readFileSync(outputFile, 'utf-8'));
          resolve(data);
        } catch {
          reject(new Error('Failed to parse decomposition output'));
        }
      } else {
        reject(new Error('No decomposition output'));
      }
    });

    proc.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}
