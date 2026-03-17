/**
 * @module worktree
 * Git worktree management — create, remove, and list worktrees
 * used to isolate each agent's working directory.
 */
import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import { WORKTREES_DIR } from './paths.js';

/**
 * Creates a git worktree for the given branch.
 * If the worktree already exists, returns its path without recreating.
 * Tries to create a new branch; falls back to using an existing one.
 *
 * @param {string} branch - Branch name for the worktree (e.g. "ocha/task-1").
 * @param {string} [baseBranch='main'] - Base branch to create the new branch from.
 * @returns {string} Absolute path to the created worktree directory.
 */
export function createWorktree(branch, baseBranch = 'main') {
  if (!existsSync(WORKTREES_DIR)) {
    mkdirSync(WORKTREES_DIR, { recursive: true });
  }
  const worktreePath = resolve(WORKTREES_DIR, branch.replace(/\//g, '-'));
  if (existsSync(worktreePath)) return worktreePath;

  try {
    execSync(`git worktree add -b ${branch} "${worktreePath}" ${baseBranch}`, {
      stdio: 'pipe',
    });
  } catch (err) {
    // Branch may already exist
    execSync(`git worktree add "${worktreePath}" ${branch}`, {
      stdio: 'pipe',
    });
  }
  return worktreePath;
}

/**
 * Force-removes a git worktree at the given path.
 * @param {string} worktreePath - Absolute path to the worktree to remove.
 */
export function removeWorktree(worktreePath) {
  if (!existsSync(worktreePath)) return;
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
