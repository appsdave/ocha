import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { randomBytes } from 'crypto';
import { execSync } from 'child_process';

import {
  createWorktree,
  removeWorktree,
  listWorktrees,
  getWorktreeForBranch,
  cleanOchaWorktrees,
} from '../../src/lib/worktree.js';

/** Unique temp dir for the test git repo */
const REPO_DIR = join(tmpdir(), 'ocha-worktree-test-' + randomBytes(4).toString('hex'));

function git(cmd) {
  return execSync(`git ${cmd}`, { cwd: REPO_DIR, stdio: 'pipe' });
}

before(() => {
  mkdirSync(REPO_DIR, { recursive: true });
  git('init -b main');
  git('config user.email "test@ocha"');
  git('config user.name "ocha-test"');
  writeFileSync(join(REPO_DIR, 'README.md'), '# test');
  git('add .');
  git('commit -m "init"');
});

after(() => {
  // Remove any lingering worktrees first so git is happy
  try { execSync('git worktree prune', { cwd: REPO_DIR, stdio: 'pipe' }); } catch (_) {}
  rmSync(REPO_DIR, { recursive: true, force: true });
});

describe('listWorktrees', () => {
  it('returns at least the main worktree', () => {
    const trees = listWorktrees(REPO_DIR);
    assert.ok(trees.length >= 1);
    assert.ok(trees.some(t => t.path === REPO_DIR));
  });

  it('each entry has a path property', () => {
    const trees = listWorktrees(REPO_DIR);
    for (const t of trees) {
      assert.ok(typeof t.path === 'string' && t.path.length > 0);
    }
  });
});

describe('createWorktree', () => {
  it('creates a worktree directory for a new branch', () => {
    const wt = createWorktree('ocha/test-create', 'main', REPO_DIR);
    assert.ok(existsSync(wt), `worktree path should exist: ${wt}`);
    // cleanup
    removeWorktree(wt, REPO_DIR);
  });

  it('returns same path if worktree already exists', () => {
    const wt1 = createWorktree('ocha/test-idempotent', 'main', REPO_DIR);
    const wt2 = createWorktree('ocha/test-idempotent', 'main', REPO_DIR);
    assert.equal(wt1, wt2);
    removeWorktree(wt1, REPO_DIR);
  });
});

describe('removeWorktree', () => {
  it('returns true and removes an existing worktree', () => {
    const wt = createWorktree('ocha/test-remove', 'main', REPO_DIR);
    assert.ok(existsSync(wt));
    const ok = removeWorktree(wt, REPO_DIR);
    assert.equal(ok, true);
    assert.ok(!existsSync(wt));
  });

  it('returns true when path does not exist (idempotent)', () => {
    const fakePath = join(REPO_DIR, 'nonexistent-worktree');
    const ok = removeWorktree(fakePath, REPO_DIR);
    assert.equal(ok, true);
  });
});

describe('getWorktreeForBranch', () => {
  it('returns the path for an existing worktree branch', () => {
    const wt = createWorktree('ocha/test-lookup', 'main', REPO_DIR);
    const found = getWorktreeForBranch('ocha/test-lookup', REPO_DIR);
    assert.equal(found, wt);
    removeWorktree(wt, REPO_DIR);
  });

  it('returns null for a branch with no worktree', () => {
    const found = getWorktreeForBranch('ocha/no-such-branch', REPO_DIR);
    assert.equal(found, null);
  });
});

describe('cleanOchaWorktrees', () => {
  it('removes all ocha/* worktrees and returns removed list', () => {
    const wt1 = createWorktree('ocha/clean-a', 'main', REPO_DIR);
    const wt2 = createWorktree('ocha/clean-b', 'main', REPO_DIR);
    assert.ok(existsSync(wt1));
    assert.ok(existsSync(wt2));

    const { removed, failed } = cleanOchaWorktrees(REPO_DIR);

    assert.ok(removed.includes(wt1), 'wt1 should be in removed');
    assert.ok(removed.includes(wt2), 'wt2 should be in removed');
    assert.equal(failed.length, 0);
    assert.ok(!existsSync(wt1));
    assert.ok(!existsSync(wt2));
  });

  it('returns empty lists when no ocha/* worktrees exist', () => {
    const { removed, failed } = cleanOchaWorktrees(REPO_DIR);
    assert.equal(removed.length, 0);
    assert.equal(failed.length, 0);
  });

  it('respects a custom branchPrefix', () => {
    const wt = createWorktree('ocha/custom-prefix-test', 'main', REPO_DIR);
    // Should NOT remove it when prefix doesn't match
    const { removed: r1 } = cleanOchaWorktrees(REPO_DIR, 'refs/heads/other/');
    assert.ok(!r1.includes(wt), 'should not remove with wrong prefix');
    // Now clean up properly
    removeWorktree(wt, REPO_DIR);
  });
});
