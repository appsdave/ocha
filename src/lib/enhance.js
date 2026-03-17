/**
 * @module enhance
 * Coordinator prompt enhancement via direct project inspection.
 * Reads key project files (package.json, README, directory tree, configs)
 * and builds an enriched task brief without spawning a Junie subprocess.
 */
import { readdirSync, readFileSync, existsSync, statSync } from 'fs';
import { resolve, join, relative } from 'path';

/**
 * Enhances a raw user task with project context by inspecting the project directly.
 * Reads package.json, README, directory structure, and key config files.
 * Falls back to the original task if inspection fails.
 *
 * @param {string} task - The raw user task description.
 * @param {string} projectDir - The project root directory.
 * @returns {Promise<string>} The enhanced task description.
 */
export async function enhanceTask(task, projectDir) {
  try {
    const context = gatherProjectContext(projectDir);
    if (!context) return task;

    return `${task}

---
## Project Context (auto-gathered by ocha coordinator)

${context}`;
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
      parts.push(info.join('\n'));
    } catch {}
  }

  // 2. README excerpt (first 60 lines)
  for (const name of ['README.md', 'readme.md', 'README']) {
    const p = join(projectDir, name);
    if (existsSync(p)) {
      try {
        const lines = readFileSync(p, 'utf-8').split('\n').slice(0, 60).join('\n');
        parts.push(`**README (excerpt):**\n${lines}`);
        break;
      } catch {}
    }
  }

  // 3. Directory tree (2 levels deep, skip node_modules/.git/dist)
  const tree = buildTree(projectDir, projectDir, 0, 2);
  if (tree.length) parts.push(`**Directory structure:**\n${tree.join('\n')}`);

  // 4. Key config files (nginx, docker, env, turbo, etc.)
  const configFiles = [
    'turbo.json', 'docker-compose.yml', 'docker-compose.yaml',
    'Dockerfile', '.env.example', 'nginx.conf',
    'next.config.js', 'next.config.ts', 'vite.config.ts', 'vite.config.js',
    'bun.lockb', 'pnpm-workspace.yaml',
  ];
  const foundConfigs = [];
  for (const f of configFiles) {
    const p = join(projectDir, f);
    if (existsSync(p)) {
      try {
        const content = readFileSync(p, 'utf-8').slice(0, 500);
        foundConfigs.push(`**${f}:**\n\`\`\`\n${content}\n\`\`\``);
      } catch {}
    }
  }
  if (foundConfigs.length) parts.push(foundConfigs.join('\n\n'));

  return parts.length ? parts.join('\n\n') : null;
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
    const rel = relative(rootDir, full);
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
