import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { randomBytes } from 'crypto';

import { enhanceTask } from './enhance.js';

/** Create a unique temp directory for each test suite run */
const TEST_ROOT = join(tmpdir(), 'ocha-enhance-test-' + randomBytes(4).toString('hex'));

function makeProject(files = {}) {
  const dir = join(TEST_ROOT, randomBytes(4).toString('hex'));
  mkdirSync(dir, { recursive: true });
  for (const [rel, content] of Object.entries(files)) {
    const full = join(dir, rel);
    mkdirSync(join(full, '..'), { recursive: true });
    writeFileSync(full, content);
  }
  return dir;
}

beforeEach(() => {
  mkdirSync(TEST_ROOT, { recursive: true });
});

afterEach(() => {
  rmSync(TEST_ROOT, { recursive: true, force: true });
});

describe('enhanceTask', () => {
  it('returns original task when projectDir has no context files', async () => {
    const dir = makeProject({});
    const result = await enhanceTask('my task', dir);
    assert.equal(result, 'my task');
  });

  it('returns enhanced string when package.json exists', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'test-app', version: '1.2.3', description: 'A test app' }),
    });
    const result = await enhanceTask('do something', dir);
    assert.ok(result.includes('## Task'));
    assert.ok(result.includes('do something'));
    assert.ok(result.includes('Project Context'));
    assert.ok(result.includes('test-app'));
    assert.ok(result.includes('1.2.3'));
    assert.ok(result.includes('A test app'));
  });

  it('wraps task under ## Task header', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'x', version: '0.1.0' }),
    });
    const result = await enhanceTask('fix the bug', dir);
    assert.ok(result.startsWith('## Task\nfix the bug'));
  });

  it('includes scripts from package.json', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({
        name: 'app', version: '1.0.0',
        scripts: { test: 'node --test', build: 'tsc' },
      }),
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('`test`'));
    assert.ok(result.includes('`build`'));
  });

  it('includes dependencies from package.json', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({
        name: 'app', version: '1.0.0',
        dependencies: { chalk: '^5.0.0', commander: '^11.0.0' },
      }),
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('chalk'));
    assert.ok(result.includes('commander'));
  });

  it('includes devDependencies from package.json', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({
        name: 'app', version: '1.0.0',
        devDependencies: { eslint: '^8.0.0', jest: '^29.0.0' },
      }),
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('eslint'));
    assert.ok(result.includes('jest'));
  });

  it('includes README excerpt', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      'README.md': '# My Project\n\nThis is a great project.\n',
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('README'));
    assert.ok(result.includes('# My Project'));
    assert.ok(result.includes('This is a great project.'));
  });

  it('truncates README beyond 80 lines and shows remaining line count', async () => {
    const lines = Array.from({ length: 100 }, (_, i) => `line ${i + 1}`);
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      'README.md': lines.join('\n'),
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('… (20 more lines)'));
    assert.ok(!result.includes('line 81'));
  });

  it('includes directory structure', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      'src/index.js': 'console.log("hi");',
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('Directory structure'));
    assert.ok(result.includes('src/'));
  });

  it('includes .junie guidelines when present', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      '.junie/guidelines.md': 'Always use tabs for indentation.\nNo semicolons.',
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('guidelines.md'));
    assert.ok(result.includes('Always use tabs for indentation.'));
  });

  it('includes .junie memory files when present', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      '.junie/memory/tasks.md': 'Task 1: done\nTask 2: in progress',
      '.junie/memory/errors.md': 'Error: foo was broken',
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('tasks.md'));
    assert.ok(result.includes('Task 1: done'));
    assert.ok(result.includes('errors.md'));
    assert.ok(result.includes('Error: foo was broken'));
  });

  it('skips empty .junie memory files', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      '.junie/memory/tasks.md': '   ',
    });
    const result = await enhanceTask('task', dir);
    // Should not include the memory section for empty files
    assert.ok(!result.includes('Memory (tasks.md)'));
  });

  it('includes key source file snippets', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      'src/index.js': Array.from({ length: 40 }, (_, i) => `// line ${i + 1}`).join('\n'),
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('Key source files'));
    assert.ok(result.includes('src/index.js'));
    assert.ok(result.includes('// line 1'));
    assert.ok(!result.includes('// line 31')); // capped at 30 lines
  });

  it('includes key config files when present', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({ name: 'app', version: '1.0.0' }),
      'tsconfig.json': '{"compilerOptions":{"strict":true}}',
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('tsconfig.json'));
    assert.ok(result.includes('"strict":true'));
  });

  it('falls back gracefully when projectDir does not exist', async () => {
    const result = await enhanceTask('my task', '/nonexistent/path/xyz');
    assert.equal(result, 'my task');
  });

  it('handles malformed package.json gracefully', async () => {
    const dir = makeProject({
      'package.json': '{invalid json!!!',
    });
    // Should not throw; falls back to original task or partial context
    const result = await enhanceTask('task', dir);
    assert.ok(typeof result === 'string');
  });

  it('handles missing package.json name/version gracefully', async () => {
    const dir = makeProject({
      'package.json': JSON.stringify({}),
    });
    const result = await enhanceTask('task', dir);
    assert.ok(result.includes('unknown'));
    assert.ok(result.includes('v?'));
  });
});
