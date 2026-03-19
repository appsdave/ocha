/**
 * @module lead
 * Lead agent — analyzes the project and produces a builder task plan.
 * Runs Junie with the lead role prompt in the real project directory (read-only).
 * Returns a list of builder tasks with descriptions and branch names.
 */
import { spawn } from 'child_process';
import { resolve } from 'path';
import { existsSync, readFileSync } from 'fs';
import { readText } from './files.js';
import { OCHA_DIR, ROLES_DIR } from './paths.js';

/** Common stop words filtered out when building a task slug. */
const STOP_WORDS = new Set([
  'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'and',
  'or', 'but', 'not', 'this', 'that', 'it', 'its', 'as', 'do', 'does',
  'did', 'will', 'would', 'should', 'could', 'can', 'may', 'might',
  'has', 'have', 'had', 'so', 'if', 'then', 'than', 'when', 'what',
  'which', 'who', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
  'some', 'any', 'no', 'just', 'about', 'up', 'out', 'into', 'over',
]);

/**
 * Build a short slug (up to `maxWords` meaningful words) from a task description.
 * Strips markdown, stop words, and non-alphanumeric characters.
 *
 * @param {string} description - Free-form task description.
 * @param {number} [maxWords=6] - Maximum number of words in the slug.
 * @returns {string} Hyphen-separated lowercase slug, e.g. "fix-retry-logic-config-parser".
 */
export function taskSlug(description, maxWords = 6) {
  if (!description) return '';
  const cleaned = description
    .replace(/^##\s*Task\s*\n/i, '')       // strip markdown task header
    .replace(/\n---\n[\s\S]*$/, '')         // strip context block
    .replace(/[^a-zA-Z0-9\s-]/g, ' ')      // keep only alphanumeric, spaces, hyphens
    .toLowerCase();
  const words = cleaned
    .split(/[\s-]+/)
    .filter(w => w.length > 1 && !STOP_WORDS.has(w));
  const slug = words.slice(0, maxWords).join('-');
  return slug || 'task';
}

/**
 * Add a timestamp + task-summary slug to a model-chosen branch name for uniqueness.
 * The model picks the descriptive part; the slug provides human-readable context.
 */
function ensureUniqueBranch(branch, index, description, prefix = 'ocha') {
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14).replace(/(\d{8})(\d{6})/, '$1-$2');
  const slug = taskSlug(description);
  // Sanitize: collapse consecutive dots (git forbids ".."), strip leading/trailing dots
  const sanitize = (name) => name.replace(/\.{2,}/g, '.').replace(/(^\.|\.$)/g, '');
  if (branch) {
    const raw = branch.replace(/^ocha\//, '');
    return `${prefix}/${sanitize(`${raw}-${ts}.${slug}`)}`;
  }
  return `${prefix}/${sanitize(`task-${index}-${ts}.${slug}`)}`;
}

/**
 * Runs the lead agent to analyze the project and produce a builder task plan.
 * Falls back to a single builder task wrapping the enhanced task if the lead fails.
 *
 * @param {string} enhancedTask - The coordinator-enhanced task description.
 * @param {string} projectDir   - The project root directory.
 * @returns {Promise<Array<{description: string, role: string, branch: string}>>} Builder tasks.
 */
export async function runLeadAgent(enhancedTask, projectDir) {
  const outputFile = resolve(OCHA_DIR, 'lead-output.json');

  try {
    const result = await runJunieLead(enhancedTask, outputFile, projectDir);
    if (result && result.tasks && result.tasks.length > 0) {
      // Ensure all tasks have role = 'builder'; use the model's branch name with a short unique suffix
      return result.tasks.map((t, i) => ({
        description: t.description,
        role: 'builder',
        branch: ensureUniqueBranch(t.branch, i + 1, t.description),
      }));
    }
  } catch {
    // Fall through to fallback
  }

  // Fallback: single builder task
  return [{
    description: enhancedTask,
    role: 'builder',
    branch: ensureUniqueBranch(null, 1, enhancedTask),
  }];
}

/**
 * Runs Junie as a subprocess with the lead role prompt.
 * Enforces a 4-minute timeout.
 *
 * @param {string} task        - The enhanced task description.
 * @param {string} outputFile  - Path where Junie writes its JSON output.
 * @param {string} projectDir  - The project directory for analysis.
 * @returns {Promise<object>} Parsed JSON output from Junie.
 */
function runJunieLead(task, outputFile, projectDir) {
  const rolePromptPath = resolve(ROLES_DIR, 'lead.md');
  const rolePrompt = readText(rolePromptPath, 'You are a lead agent. Analyze the project and output a JSON task plan.');
  const fullPrompt = `${rolePrompt}\n\n## Task Brief from Coordinator\n\n${task}`;

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
      reject(new Error('Lead agent timed out'));
    }, 240000);

    proc.on('close', (code) => {
      clearTimeout(timeout);
      // 1. Try the dedicated output file first
      if (existsSync(outputFile)) {
        try {
          const data = JSON.parse(readFileSync(outputFile, 'utf-8'));
          if (data && data.tasks) return resolve(data);
        } catch {}
      }
      // 2. Scan stdout for JSON containing tasks array
      const jsonMatch = stdout.match(/\{[\s\S]*?"tasks"[\s\S]*?\}/);
      if (jsonMatch) {
        try {
          const data = JSON.parse(jsonMatch[0]);
          if (data && data.tasks) return resolve(data);
        } catch {}
      }
      reject(new Error(`No lead output (exit ${code})`));
    });

    proc.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}
