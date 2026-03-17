import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import { WORKTREES_DIR } from './paths.js';

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

export function removeWorktree(worktreePath) {
  if (!existsSync(worktreePath)) return;
  execSync(`git worktree remove "${worktreePath}" --force`, { stdio: 'pipe' });
}

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
