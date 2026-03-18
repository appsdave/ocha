import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { validateBranchName, validateMaxAgents, validateTask, validatePriority } from '../../src/lib/validate.js';

describe('validateBranchName', () => {
  it('accepts a valid branch name', () => {
    assert.equal(validateBranchName('ocha/my-task'), 'ocha/my-task');
  });

  it('trims whitespace', () => {
    assert.equal(validateBranchName('  main  '), 'main');
  });

  it('rejects empty string', () => {
    assert.throws(() => validateBranchName(''), /required/);
  });

  it('rejects null/undefined', () => {
    assert.throws(() => validateBranchName(null), /required/);
    assert.throws(() => validateBranchName(undefined), /required/);
  });

  it('rejects names with spaces', () => {
    assert.throws(() => validateBranchName('my branch'), /forbidden/);
  });

  it('rejects names with shell metacharacters', () => {
    assert.throws(() => validateBranchName('branch;rm -rf'), /forbidden/);
  });

  it('rejects names with double dots', () => {
    assert.throws(() => validateBranchName('a..b'), /forbidden/);
  });

  it('rejects names starting with dash', () => {
    assert.throws(() => validateBranchName('-bad'), /invalid start/i);
  });

  it('rejects names ending with .lock', () => {
    assert.throws(() => validateBranchName('branch.lock'), /invalid start/i);
  });
});

describe('validateMaxAgents', () => {
  it('accepts a positive integer string', () => {
    assert.equal(validateMaxAgents('3'), 3);
  });

  it('accepts a positive number', () => {
    assert.equal(validateMaxAgents(5), 5);
  });

  it('rejects zero', () => {
    assert.throws(() => validateMaxAgents(0), /positive integer/);
  });

  it('rejects negative', () => {
    assert.throws(() => validateMaxAgents(-1), /positive integer/);
  });

  it('rejects non-numeric string', () => {
    assert.throws(() => validateMaxAgents('abc'), /positive integer/);
  });
});

describe('validateTask', () => {
  it('accepts a non-empty string', () => {
    assert.equal(validateTask('fix the bug'), 'fix the bug');
  });

  it('trims whitespace', () => {
    assert.equal(validateTask('  hello  '), 'hello');
  });

  it('rejects empty string', () => {
    assert.throws(() => validateTask(''), /required/);
  });

  it('rejects whitespace-only string', () => {
    assert.throws(() => validateTask('   '), /empty/);
  });

  it('rejects null', () => {
    assert.throws(() => validateTask(null), /required/);
  });
});

describe('validatePriority', () => {
  it('accepts valid priorities 0-4', () => {
    for (let i = 0; i <= 4; i++) {
      assert.equal(validatePriority(i), i);
    }
  });

  it('accepts string priorities', () => {
    assert.equal(validatePriority('2'), 2);
  });

  it('rejects out of range', () => {
    assert.throws(() => validatePriority(5), /must be 0-4/);
    assert.throws(() => validatePriority(-1), /must be 0-4/);
  });
});
