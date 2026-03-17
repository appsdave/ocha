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

Given a high-level task, break it into the smallest set of independent subtasks that can be worked on in parallel in separate git worktrees. Each subtask must be able to run without depending on or conflicting with any other subtask.

## Decomposition Rules

1. **Minimize file overlap**: each subtask should touch a distinct set of files. If two subtasks would edit the same file, merge them into one.
2. **Be specific**: write clear, actionable descriptions that tell the agent exactly what to do, which files to touch, and what the expected outcome is.
3. **Right-size tasks**: do not over-decompose. If the original task is simple and focused, return a single task. Only split when there are genuinely independent pieces of work.
4. **Choose the right role**:
   - \`builder\` — writes code, adds/updates tests, commits changes. Use for most implementation work.
   - \`reviewer\` — reads code and produces a review report. Use when the task is to audit or review existing changes.
   - \`lead\` — handles complex subtasks requiring architectural decisions or cross-cutting changes that span multiple modules.
5. **Branch naming**: use short, descriptive names prefixed with \`ocha/\` (e.g., \`ocha/add-retry-logic\`, \`ocha/fix-config-parser\`). No spaces, no special characters beyond hyphens.

## Output Format

Output ONLY valid JSON (no markdown fences, no explanation, no commentary):
{
  "tasks": [
    { "description": "Clear, specific description of what to implement and how to verify it", "role": "builder", "branch": "ocha/descriptive-branch-name" }
  ]
}

Do NOT run any commands. Do NOT modify any files. Do NOT open any tools. ONLY output the JSON decomposition.`;

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
    const handleData = (d) => {
      const text = d.toString();
      output += text;
      // Show only key progress lines (filter out raw JSON, noise)
      for (const line of text.split('\n')) {
        const t = line.trim();
        if (!t) continue;
        // Skip raw JSON fragments leaking from Junie
        if (t.startsWith('{') || t.startsWith('}') || t.startsWith('"') || t.startsWith('[') || t.startsWith(']')) continue;
        if (
          t.startsWith('● Thinking') ||
          t.startsWith('● TASK RESULT') ||
          t.startsWith('TASK RESULT')
        ) {
          process.stdout.write(`   ${t}\n`);
        }
      }
    };
    proc.stdout.on('data', handleData);
    proc.stderr.on('data', handleData);

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
