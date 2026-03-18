/**
 * @module worktree
 * Git worktree management — create, remove, list, lookup, and bulk-clean worktrees
 * used to isolate each agent's working directory.
 *
 * ## How ocha uses worktrees
 *
 * Each builder/reviewer agent pair runs inside its own `git worktree` so that:
 * - Agents never conflict with each other or with the running ocha process.
 * - Each agent has a clean branch (`ocha/<task-slug>`) branched from the base branch.
 * - Worktrees are created under `<repoDir>/.ocha-worktrees/<branch-slug>/`.
 * - After an agent finishes (or the session is stopped), the worktree is removed
 *   and the branch is pushed to origin for PR review.
 *
 * ## Typical lifecycle
 *
 * ```
 * createWorktree('ocha/task-1', 'main')   // agent starts
 *   → <repo>/.ocha-worktrees/ocha-task-1/
 *
 * getWorktreeForBranch('ocha/task-1')     // look up path by branch
 *   → '/abs/path/.ocha-worktrees/ocha-task-1'
 *
 * removeWorktree(path)                    // agent done / stopped
 *
 * cleanOchaWorktrees()                    // session-level full cleanup
 * ```
 */
import { resolve } from 'path';
import { ensureDir, pathExists } from './files.js';
import { WORKTREES_DIR } from './paths.js';
import { git, gitSafe } from './exec.js';

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
  const worktreesDir = repoDir ? resolve(repoDir, '.ocha-worktrees') : WORKTREES_DIR;
  ensureDir(worktreesDir);
  const worktreePath = resolve(worktreesDir, branch.replace(/\//g, '-'));

  // Prune stale worktree registrations before attempting to create
  gitSafe(['worktree', 'prune'], { cwd: repoDir });

  if (pathExists(worktreePath)) return worktreePath;

  try {
    git(['worktree', 'add', '-b', branch, worktreePath, baseBranch], { cwd: repoDir });
  } catch {
    // Branch already exists — delete it and recreate fresh from baseBranch
    gitSafe(['branch', '-D', branch], { cwd: repoDir });
    try {
      git(['worktree', 'add', '-b', branch, worktreePath, baseBranch], { cwd: repoDir });
    } catch {
      // Last resort: reuse existing branch as-is
      git(['worktree', 'add', worktreePath, branch], { cwd: repoDir });
    }
  }
  return worktreePath;
}

/**
 * Force-removes a git worktree at the given path.
 * Does nothing if the path does not exist.
 * Returns true on success, false if removal failed (e.g. git internal error).
 *
 * @param {string} worktreePath - Absolute path to the worktree to remove.
 * @param {string} [repoDir] - Repo root to run git commands in (defaults to cwd).
 * @returns {boolean} True if the worktree was removed (or did not exist), false on error.
 */
export function removeWorktree(worktreePath, repoDir) {
  if (!pathExists(worktreePath)) return true;
  return gitSafe(['worktree', 'remove', worktreePath, '--force'], { cwd: repoDir }) !== null;
}

/**
 * Lists all git worktrees in the repository.
 *
 * @param {string} [repoDir] - Repo root to run git commands in (defaults to cwd).
 * @returns {Array<{path: string, branch?: string, bare?: boolean}>} Array of worktree objects.
 */
export function listWorktrees(repoDir) {
  const out = git(['worktree', 'list', '--porcelain'], { cwd: repoDir });
  const trees = [];
  let current = {};
  for (const line of out.split('\n')) {
    if (line.startsWith('worktree ')) {
      current = { path: line.slice(9) };
    } else if (line.startsWith('branch ')) {
      current.branch = line.slice(7);
    } else if (line === 'bare') {
      current.bare = true;
    } else if (line === '') {
      if (current.path) trees.push(current);
      current = {};
    }
  }
  return trees;
}

/**
 * Finds the worktree path for a given branch name.
 * Searches the git worktree list for a matching `refs/heads/<branch>` entry.
 *
 * @param {string} branch - Branch name to look up (e.g. "ocha/task-1").
 * @param {string} [repoDir] - Repo root to run git commands in (defaults to cwd).
 * @returns {string|null} Absolute path to the worktree, or null if not found.
 */
export function getWorktreeForBranch(branch, repoDir) {
  const trees = listWorktrees(repoDir);
  const ref = `refs/heads/${branch}`;
  const found = trees.find(t => t.branch === ref);
  return found ? found.path : null;
}

/**
 * Removes all git worktrees whose branch starts with "ocha/" (or a custom prefix).
 * Useful for a full session cleanup when `.ocha-worktrees/` has already been deleted
 * but git still tracks the registrations, or for pruning individually.
 *
 * Prunes stale registrations first, then force-removes each matching worktree.
 *
 * @param {string} [repoDir] - Repo root to run git commands in (defaults to cwd).
 * @param {string} [branchPrefix='refs/heads/ocha/'] - Branch ref prefix to match.
 * @returns {{ removed: string[], failed: string[] }} Lists of removed and failed worktree paths.
 */
export function cleanOchaWorktrees(repoDir, branchPrefix = 'refs/heads/ocha/') {
  // Prune stale registrations first
  gitSafe(['worktree', 'prune'], { cwd: repoDir });

  const trees = listWorktrees(repoDir);
  const removed = [];
  const failed = [];

  for (const tree of trees) {
    if (!tree.branch || !tree.branch.startsWith(branchPrefix)) continue;
    const ok = removeWorktree(tree.path, repoDir);
    if (ok) {
      removed.push(tree.path);
    } else {
      failed.push(tree.path);
    }
  }

  // Final prune to clear any leftover registrations
  gitSafe(['worktree', 'prune'], { cwd: repoDir });

  return { removed, failed };
}
