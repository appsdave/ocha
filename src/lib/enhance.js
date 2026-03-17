/**
 * @module enhance
 * Coordinator prompt enhancement via Junie AI.
 * Takes the raw user task and enriches it with project context before
 * passing it down to the lead agent.
 */
import { spawn } from 'child_process';
import { resolve } from 'path';
import { existsSync, readFileSync, mkdirSync } from 'fs';
import { OCHA_DIR } from './paths.js';

const ENHANCE_PROMPT = `You are the **coordinator** in an ocha multi-agent workflow. Your job is to take a raw user task and produce an enriched, detailed task brief that gives the lead agent everything it needs to plan and assign work.

## What you must do

1. **Understand the task** — read the user's request carefully.
2. **Gather project context** — inspect the project structure, key files, and relevant code to understand what exists and what needs to change.
3. **Produce an enhanced brief** — write a clear, detailed task description that includes:
   - What the user wants (restated clearly)
   - Relevant project context (key files, modules, patterns)
   - Constraints or risks to be aware of
   - Suggested approach or areas to focus on

## Output Format

Output ONLY valid JSON (no markdown fences, no commentary):
{
  "enhancedTask": "Full enriched task description with all context the lead needs"
}

Do NOT implement anything. Do NOT modify any files. ONLY output the JSON brief.`;

/**
 * Enhances a raw user task with project context using Junie AI.
 * Runs Junie in the actual project directory (read-only analysis).
 * Falls back to the original task if enhancement fails.
 *
 * @param {string} task - The raw user task description.
 * @param {string} projectDir - The project root directory.
 * @returns {Promise<string>} The enhanced task description.
 */
export async function enhanceTask(task, projectDir) {
  const outputFile = resolve(OCHA_DIR, 'enhance-output.json');

  try {
    const result = await runJunieEnhance(task, outputFile, projectDir);
    if (result && result.enhancedTask && result.enhancedTask.trim().length > 0) {
      return result.enhancedTask;
    }
  } catch (err) {
    throw err;
  }

  return task;
}

/**
 * Runs Junie as a subprocess to enhance the task prompt.
 * Enforces a 3-minute timeout.
 *
 * @param {string} task - The raw task description.
 * @param {string} outputFile - Path where Junie writes its JSON output.
 * @param {string} projectDir - The project directory for context analysis.
 * @returns {Promise<object>} Parsed JSON output from Junie.
 */
function runJunieEnhance(task, outputFile, projectDir) {
  mkdirSync(OCHA_DIR, { recursive: true });
  const fullPrompt = `${ENHANCE_PROMPT}\n\nUser task:\n${task}`;

  return new Promise((resolve, reject) => {
    const proc = spawn('junie', [
      '--project', projectDir,
      '--task', fullPrompt,
      '--json-output-file', outputFile,
      '--brave',
    ], { stdio: 'pipe' });

    let stdout = '';
    const handleData = (d) => {
      const text = d.toString();
      stdout += text;
      for (const line of text.split('\n')) {
        const t = line.trim();
        if (!t) continue;
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
      reject(new Error('Enhancement timed out'));
    }, 180000);

    proc.on('close', (code) => {
      clearTimeout(timeout);
      // 1. Try the dedicated output file first
      if (existsSync(outputFile)) {
        try {
          const data = JSON.parse(readFileSync(outputFile, 'utf-8'));
          if (data && data.enhancedTask) return resolve(data);
        } catch {}
      }
      // 2. Scan stdout for the first JSON object containing enhancedTask
      const jsonMatch = stdout.match(/\{[\s\S]*?"enhancedTask"[\s\S]*?\}/);
      if (jsonMatch) {
        try {
          const data = JSON.parse(jsonMatch[0]);
          if (data && data.enhancedTask) return resolve(data);
        } catch {}
      }
      // 3. If Junie wrote a plain-text result (TASK RESULT: ...), use that
      const taskResultMatch = stdout.match(/TASK RESULT:\s*([\s\S]+)/);
      if (taskResultMatch) {
        return resolve({ enhancedTask: taskResultMatch[1].trim() });
      }
      reject(new Error(`No enhancement output (exit ${code})`));
    });

    proc.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}
