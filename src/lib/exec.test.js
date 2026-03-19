import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { shellEscape, git, gitSafe, exec, execSafe, shell, shellSafe } from './exec.js';

describe('shellEscape', () => {
  it('wraps a simple string in single quotes', () => {
    assert.equal(shellEscape('hello'), "'hello'");
  });

  it('escapes embedded single quotes', () => {
    assert.equal(shellEscape("it's"), "'it'\\''s'");
  });

  it('handles empty string', () => {
    assert.equal(shellEscape(''), "''");
  });

  it('handles strings with spaces and special chars', () => {
    assert.equal(shellEscape('a b; rm -rf /'), "'a b; rm -rf /'");
  });
});

describe('git', () => {
  it('runs a simple git command', () => {
    const out = git(['rev-parse', '--is-inside-work-tree']);
    assert.equal(out.trim(), 'true');
  });

  it('throws on invalid git command', () => {
    assert.throws(() => git(['not-a-real-command']), /error/i);
  });
});

describe('gitSafe', () => {
  it('returns output on success', () => {
    const out = gitSafe(['rev-parse', '--is-inside-work-tree']);
    assert.equal(out.trim(), 'true');
  });

  it('returns null on failure', () => {
    const out = gitSafe(['not-a-real-command']);
    assert.equal(out, null);
  });
});

describe('exec', () => {
  it('runs a command and returns stdout', () => {
    const out = exec('echo', ['hello']);
    assert.equal(out.trim(), 'hello');
  });

  it('throws on non-existent command', () => {
    assert.throws(() => exec('nonexistent-cmd-xyz', []), /ENOENT/);
  });

  it('respects cwd option', () => {
    const out = exec('pwd', [], { cwd: '/tmp' });
    assert.equal(out.trim(), '/tmp');
  });
});

describe('execSafe', () => {
  it('returns output on success', () => {
    const out = execSafe('echo', ['world']);
    assert.equal(out.trim(), 'world');
  });

  it('returns null on failure', () => {
    const out = execSafe('nonexistent-cmd-xyz', []);
    assert.equal(out, null);
  });
});

describe('shell', () => {
  it('runs a shell command string', () => {
    const out = shell('echo hello');
    assert.equal(out.trim(), 'hello');
  });

  it('supports pipes', () => {
    const out = shell('echo "hello world" | tr a-z A-Z');
    assert.equal(out.trim(), 'HELLO WORLD');
  });

  it('throws on failing command', () => {
    assert.throws(() => shell('exit 1'));
  });
});

describe('shellSafe', () => {
  it('returns output on success', () => {
    const out = shellSafe('echo ok');
    assert.equal(out.trim(), 'ok');
  });

  it('returns null on failure', () => {
    const out = shellSafe('exit 1');
    assert.equal(out, null);
  });
});
