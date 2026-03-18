/**
 * @module worktree
 * Git worktree management — create, remove, and list worktrees
 * used to isolate each agent's working directory.
 */
import { execSync } from 'child_process';
import { resolve } from 'path';
import { ensureDir, pathExists } from './files.js';
import { WORKTREES_DIR } from './paths.js';

/**
 * Creates a git worktree for the given branch.
 * If the worktree already exists, returns its path without recreating.
 * Tries to create a new branch; falls back to using an existing one.
 *
 * @param {string} branch - Branch name for the worktree (e.g. "ocha/task-1").
 * @param {string} [baseBranch='main'] - Base branch to create the new branch from.
 * @param {string} [repoDir] - Repo root to run git commands in (defaults to cwd).
 * @returns {string} Absolute path to the created worktree directory.
 */
export function createWorktree(branch, baseBranch = 'main', repoDir) {
  // Each repo gets its own worktrees dir: <repoDir>/.ocha-worktrees/
  const worktreesDir = repoDir ? resolve(repoDir, '.ocha-worktrees') : WORKTREES_DIR;
  ensureDir(worktreesDir);
  const worktreePath = resolve(worktreesDir, branch.replace(/\//g, '-'));
  const gitOpts = { stdio: 'pipe', ...(repoDir ? { cwd: repoDir } : {}) };

  // Prune stale worktree registrations before attempting to create
  try { execSync('git worktree prune', gitOpts); } catch (_) {}

  if (pathExists(worktreePath)) return worktreePath;

  try {
    execSync(`git worktree add -b ${branch} "${worktreePath}" ${baseBranch}`, gitOpts);
  } catch (err) {
    // Branch already exists — delete it and recreate fresh from baseBranch
    try { execSync(`git branch -D ${branch}`, gitOpts); } catch (_) {}
    try {
      execSync(`git worktree add -b ${branch} "${worktreePath}" ${baseBranch}`, gitOpts);
    } catch (_) {
      // Last resort: reuse existing branch as-is
      execSync(`git worktree add "${worktreePath}" ${branch}`, gitOpts);
    }
  }
  return worktreePath;
}

/**
 * Force-removes a git worktree at the given path.
 * @param {string} worktreePath - Absolute path to the worktree to remove.
 */
export function removeWorktree(worktreePath) {
  if (!pathExists(worktreePath)) return;
  execSync(`git worktree remove "${worktreePath}" --force`, { stdio: 'pipe' });
}

/**
 * Lists all git worktrees in the repository.
 * @returns {Array<{path: string, branch?: string}>} Array of worktree objects.
 */
export function listWorktrees() {
  const out = execSync('git worktree list --porcelain', { encoding: 'utf-8' });
  const trees = [];
  let current = {};
  for (const line of out.split('\n')) {
    if (line.startsWith('worktree ')) {
      current = { path: line.slice(9) };
    } else if (line.startsWith('branch ')) {
      current.branch = line.slice(7);
    } else if (line === '') {
      if (current.path) trees.push(current);
      current = {};
    }
  }
  return trees;
}
