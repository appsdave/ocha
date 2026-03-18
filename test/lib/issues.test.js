import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, rmSync, existsSync } from 'fs';
import { dirname } from 'path';

import { reportIssue, getIssues, clearIssues } from '../../src/lib/issues.js';
import { ISSUES_FILE } from '../../src/lib/paths.js';

/** Ensure .ocha/ exists and wipe issues.json before/after each test */
beforeEach(() => {
  mkdirSync(dirname(ISSUES_FILE), { recursive: true });
  if (existsSync(ISSUES_FILE)) rmSync(ISSUES_FILE);
});

afterEach(() => {
  if (existsSync(ISSUES_FILE)) rmSync(ISSUES_FILE);
});

describe('reportIssue', () => {
  it('returns the recorded issue object', () => {
    const issue = reportIssue('task-1', 'error', 'Something broke');
    assert.equal(issue.taskId, 'task-1');
    assert.equal(issue.level, 'error');
    assert.equal(issue.message, 'Something broke');
    assert.ok(typeof issue.reportedAt === 'string');
  });

  it('includes detail when provided', () => {
    const issue = reportIssue('task-1', 'warning', 'Slow response', 'Took 30s');
    assert.equal(issue.detail, 'Took 30s');
  });

  it('omits detail key when not provided', () => {
    const issue = reportIssue('task-1', 'info', 'Started');
    assert.ok(!Object.prototype.hasOwnProperty.call(issue, 'detail'));
  });

  it('persists multiple issues across calls', () => {
    reportIssue('task-1', 'error', 'First');
    reportIssue('task-2', 'info', 'Second');
    assert.equal(getIssues().length, 2);
  });

  it('accepts all three severity levels', () => {
    reportIssue('task-1', 'error', 'e');
    reportIssue('task-1', 'warning', 'w');
    reportIssue('task-1', 'info', 'i');
    assert.deepEqual(getIssues().map(i => i.level), ['error', 'warning', 'info']);
  });
});

describe('getIssues', () => {
  it('returns empty array when no issues have been reported', () => {
    assert.deepEqual(getIssues(), []);
  });

  it('returns all issues when called without a taskId', () => {
    reportIssue('task-1', 'error', 'A');
    reportIssue('task-2', 'info', 'B');
    assert.equal(getIssues().length, 2);
  });

  it('filters by taskId when provided', () => {
    reportIssue('task-1', 'error', 'A');
    reportIssue('task-2', 'info', 'B');
    reportIssue('task-1', 'warning', 'C');
    const t1 = getIssues('task-1');
    assert.equal(t1.length, 2);
    assert.ok(t1.every(i => i.taskId === 'task-1'));
  });

  it('returns empty array for unknown taskId', () => {
    reportIssue('task-1', 'error', 'A');
    assert.deepEqual(getIssues('task-99'), []);
  });
});

describe('clearIssues', () => {
  it('removes all issues from the feed', () => {
    reportIssue('task-1', 'error', 'A');
    reportIssue('task-2', 'info', 'B');
    clearIssues();
    assert.deepEqual(getIssues(), []);
  });

  it('is safe to call when no issues exist', () => {
    assert.doesNotThrow(() => clearIssues());
    assert.deepEqual(getIssues(), []);
  });
});
