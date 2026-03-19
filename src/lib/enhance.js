/**
 * @module enhance
 * Coordinator prompt enhancement via direct project inspection.
 * Reads key project files (package.json, README, directory tree, configs,
 * git context, and .junie guidelines) and builds an enriched task brief
 * without spawning a Junie subprocess.
 */
import { readdirSync, readFileSync, existsSync, statSync } from 'fs';
import { join } from 'path';
import { git } from './exec.js';

/**
 * Enhances a raw user task with project context by inspecting the project directly.
 * Reads package.json, README, directory structure, git context, .junie guidelines,
 * and key config files. Falls back to the original task if inspection fails.
 *
 * @param {string} task - The raw user task description.
 * @param {string} projectDir - The project root directory.
 * @returns {Promise<string>} The enhanced task description.
 */
export async function enhanceTask(task, projectDir, extraRepoDirs = []) {
  try {
    const allDirs = [projectDir, ...extraRepoDirs.filter(d => d !== projectDir)];
    const contexts = [];
    for (const dir of allDirs) {
      const ctx = gatherProjectContext(dir);
      if (ctx) contexts.push(`### Repo: ${dir}\n\n${ctx}`);
    }
    if (!contexts.length) return task;
    const combined = contexts.join('\n\n---\n\n');
    return `## Task\n${task}\n\n---\n## Project Context (auto-gathered by ocha coordinator)\n\n${combined}`;
  } catch {
    return task;
  }
}

/**
 * Gathers project context by reading key files and directory structure.
 * @param {string} projectDir
 * @returns {string|null}
 */
function gatherProjectContext(projectDir) {
  const parts = [];

  // 1. Package info
  const pkgPath = join(projectDir, 'package.json');
  if (existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
      const info = [`**Project:** ${pkg.name || 'unknown'} v${pkg.version || '?'}`];
      if (pkg.description) info.push(`**Description:** ${pkg.description}`);
      if (pkg.scripts) {
        const scripts = Object.entries(pkg.scripts).slice(0, 8).map(([k, v]) => `  - \`${k}\`: ${v}`).join('\n');
        info.push(`**Scripts:**\n${scripts}`);
      }
      if (pkg.dependencies) {
        const deps = Object.keys(pkg.dependencies).slice(0, 15).join(', ');
        info.push(`**Dependencies:** ${deps}`);
      }
      if (pkg.devDependencies) {
        const devDeps = Object.keys(pkg.devDependencies).slice(0, 10).join(', ');
        info.push(`**Dev Dependencies:** ${devDeps}`);
      }
      parts.push(info.join('\n'));
    } catch {}
  }

  // 2. Git context (branch + recent commits)
  const gitContext = gatherGitContext(projectDir);
  if (gitContext) parts.push(gitContext);

  // 3. README excerpt (first 80 lines)
  for (const name of ['README.md', 'readme.md', 'README']) {
    const p = join(projectDir, name);
    if (existsSync(p)) {
      try {
        const allLines = readFileSync(p, 'utf-8').split('\n');
        const lines = allLines.slice(0, 80).join('\n');
        const truncated = allLines.length > 80 ? `\n… (${allLines.length - 80} more lines)` : '';
        parts.push(`**README (excerpt):**\n${lines}${truncated}`);
        break;
      } catch {}
    }
  }

  // 4. .junie guidelines / memory for project conventions
  const junieContext = gatherJunieContext(projectDir);
  if (junieContext) parts.push(junieContext);

  // 5. Directory tree (2 levels deep, skip node_modules/.git/dist)
  const tree = buildTree(projectDir, projectDir, 0, 2);
  if (tree.length) parts.push(`**Directory structure:**\n${tree.join('\n')}`);

  // 6. Key config files (nginx, docker, env, turbo, etc.)
  const configFiles = [
    'turbo.json', 'docker-compose.yml', 'docker-compose.yaml',
    'Dockerfile', '.env.example', 'nginx.conf',
    'next.config.js', 'next.config.ts', 'vite.config.ts', 'vite.config.js',
    'bun.lockb', 'pnpm-workspace.yaml', 'tsconfig.json', '.eslintrc.js',
    '.eslintrc.json', 'jest.config.js', 'jest.config.ts', 'vitest.config.ts',
  ];
  const foundConfigs = [];
  for (const f of configFiles) {
    const p = join(projectDir, f);
    if (existsSync(p)) {
      try {
        const content = readFileSync(p, 'utf-8').slice(0, 600);
        foundConfigs.push(`**${f}:**\n\`\`\`\n${content}\n\`\`\``);
      } catch {}
    }
  }
  if (foundConfigs.length) parts.push(foundConfigs.join('\n\n'));

  // 7. Key source file snippets (entry points, main modules)
  const sourceSnippets = gatherSourceSnippets(projectDir);
  if (sourceSnippets) parts.push(sourceSnippets);

  return parts.length ? parts.join('\n\n') : null;
}

/**
 * Gathers git context: current branch and recent commit log.
 * @param {string} projectDir
 * @returns {string|null}
 */
function gatherGitContext(projectDir) {
  try {
    const branch = git(['rev-parse', '--abbrev-ref', 'HEAD'], { cwd: projectDir, timeout: 3000 }).trim();
    const log = git(['log', '--oneline', '-8'], { cwd: projectDir, timeout: 3000 }).trim();

    const lines = [`**Git branch:** ${branch}`];
    if (log) lines.push(`**Recent commits:**\n${log.split('\n').map(l => `  ${l}`).join('\n')}`);
    return lines.join('\n');
  } catch {
    return null;
  }
}

/**
 * Gathers .junie guidelines and relevant memory files for project conventions.
 * @param {string} projectDir
 * @returns {string|null}
 */
function gatherJunieContext(projectDir) {
  const junieDir = join(projectDir, '.junie');
  if (!existsSync(junieDir)) return null;

  const sections = [];

  // Guidelines file
  const guidelinesPath = join(junieDir, 'guidelines.md');
  if (existsSync(guidelinesPath)) {
    try {
      const content = readFileSync(guidelinesPath, 'utf-8').trim();
      if (content) sections.push(`**Project Guidelines (.junie/guidelines.md):**\n${content.slice(0, 800)}`);
    } catch {}
  }

  // Memory files (tasks, feedback, errors)
  const memoryDir = join(junieDir, 'memory');
  const memoryFiles = ['tasks.md', 'feedback.md', 'errors.md'];
  for (const mf of memoryFiles) {
    const mp = join(memoryDir, mf);
    if (existsSync(mp)) {
      try {
        const content = readFileSync(mp, 'utf-8').trim();
        if (content) sections.push(`**Memory (${mf}):**\n${content.slice(0, 400)}`);
      } catch {}
    }
  }

  return sections.length ? sections.join('\n\n') : null;
}

/**
 * Gathers brief snippets from key source files to help the lead agent
 * understand the codebase structure (first 30 lines of entry points).
 * @param {string} projectDir
 * @returns {string|null}
 */
function gatherSourceSnippets(projectDir) {
  const candidates = [
    'src/index.js', 'src/index.ts', 'src/main.js', 'src/main.ts',
    'index.js', 'index.ts', 'main.js', 'main.ts',
    'bin/cli.js', 'bin/index.js',
  ];

  // Also scan bin/ for the main entry
  const binDir = join(projectDir, 'bin');
  if (existsSync(binDir)) {
    try {
      for (const f of readdirSync(binDir).sort()) {
        if (f.endsWith('.js') || f.endsWith('.ts')) {
          candidates.push(`bin/${f}`);
        }
      }
    } catch {}
  }

  const snippets = [];
  const seen = new Set();
  for (const rel of candidates) {
    if (seen.has(rel)) continue;
    seen.add(rel);
    const p = join(projectDir, rel);
    if (!existsSync(p)) continue;
    try {
      const lines = readFileSync(p, 'utf-8').split('\n').slice(0, 30).join('\n');
      snippets.push(`**${rel} (first 30 lines):**\n\`\`\`\n${lines}\n\`\`\``);
      if (snippets.length >= 3) break; // cap at 3 snippets
    } catch {}
  }

  return snippets.length ? `**Key source files:**\n\n${snippets.join('\n\n')}` : null;
}

/**
 * Recursively builds a directory tree string array.
 */
function buildTree(rootDir, dir, depth, maxDepth) {
  if (depth > maxDepth) return [];
  const SKIP = new Set(['node_modules', '.git', 'dist', 'build', '.next', '.turbo', 'coverage', '.ocha-worktrees']);
  const lines = [];
  let entries;
  try { entries = readdirSync(dir); } catch { return []; }
  for (const entry of entries.sort()) {
    if (SKIP.has(entry)) continue;
    const full = join(dir, entry);
    const indent = '  '.repeat(depth);
    try {
      const stat = statSync(full);
      if (stat.isDirectory()) {
        lines.push(`${indent}${entry}/`);
        lines.push(...buildTree(rootDir, full, depth + 1, maxDepth));
      } else {
        lines.push(`${indent}${entry}`);
      }
    } catch {}
  }
  return lines;
}
