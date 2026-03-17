/**
 * @module decompose
 * Task decomposition via Junie AI.
 * Sends a high-level task to Junie for analysis-only decomposition into
 * independent, parallelizable subtasks. Falls back to a single task on failure.
 */
import { spawn } from 'child_process';
import { resolve } from 'path';
import { existsSync, readFileSync, mkdtempSync } from 'fs';
import { tmpdir } from 'os';
import { OCHA_DIR } from './paths.js';

const DECOMPOSE_PROMPT = `You are a task decomposition agent. You ONLY analyze and decompose tasks — you do NOT execute any code, run any commands, or make any changes.

Given a high-level task, break it into independent subtasks that can be worked on in parallel in separate git worktrees.

Output ONLY valid JSON (no markdown fences) in this exact format:
{
  "tasks": [
    { "description": "...", "role": "builder", "branch": "ocha/descriptive-branch-name" }
  ]
}

Roles available: builder (writes code), reviewer (reviews code), lead (coordinates sub-work).
Keep subtasks focused and independent. Use descriptive branch names prefixed with "ocha/".
Do NOT run any commands. Do NOT modify any files. ONLY output the JSON decomposition.`;

/**
 * Decomposes a high-level task into independent subtasks using Junie AI.
 * Runs Junie in a temporary directory (read-only) with a decomposition prompt.
 * Falls back to a single builder task if decomposition fails or times out.
 *
 * @param {string} task - The high-level task description to decompose.
 * @returns {Promise<Array<{description: string, role: string, branch: string}>>} Array of subtask objects.
 */
export async function decomposeTask(task) {
  const outputFile = resolve(OCHA_DIR, 'decompose-output.json');

  // Use a temp directory so Junie can't modify the real project
  const tempDir = mkdtempSync(resolve(tmpdir(), 'ocha-decompose-'));

  try {
    const result = await runJunieDecompose(task, outputFile, tempDir);
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

/**
 * Runs Junie as a subprocess to decompose a task.
 * Enforces a 2-minute timeout to prevent hanging.
 *
 * @param {string} task - The task description.
 * @param {string} outputFile - Path where Junie writes its JSON output.
 * @param {string} tempDir - Temporary directory for the Junie project context.
 * @returns {Promise<object>} Parsed JSON output from Junie.
 */
function runJunieDecompose(task, outputFile, tempDir) {
  const fullPrompt = `${DECOMPOSE_PROMPT}\n\nTask to decompose:\n${task}`;

  return new Promise((resolve, reject) => {
    const proc = spawn('junie', [
      '--project', tempDir,
      '--task', fullPrompt,
      '--json-output-file', outputFile,
      '--brave',
    ], { stdio: 'pipe' });

    let output = '';
    proc.stdout.on('data', (d) => { output += d; });
    proc.stderr.on('data', (d) => { output += d; });

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
