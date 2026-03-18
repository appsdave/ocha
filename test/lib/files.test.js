import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { randomBytes } from 'crypto';

import {
  ensureDir,
  ensureParentDir,
  readText,
  writeText,
  readJSON,
  writeJSON,
  safeDelete,
  cleanDir,
  pathExists,
  listFiles,
  fileInfo,
} from '../../src/lib/files.js';

/** Create a unique temp directory for each test suite run */
const TEST_ROOT = join(tmpdir(), 'ocha-files-test-' + randomBytes(4).toString('hex'));

beforeEach(() => {
  mkdirSync(TEST_ROOT, { recursive: true });
});

afterEach(() => {
  rmSync(TEST_ROOT, { recursive: true, force: true });
});

describe('ensureDir', () => {
  it('creates a directory that does not exist', () => {
    const dir = join(TEST_ROOT, 'new-dir');
    ensureDir(dir);
    assert.ok(existsSync(dir));
  });

  it('creates nested directories', () => {
    const dir = join(TEST_ROOT, 'a', 'b', 'c');
    ensureDir(dir);
    assert.ok(existsSync(dir));
  });

  it('does nothing if directory already exists', () => {
    const dir = join(TEST_ROOT, 'existing');
    mkdirSync(dir);
    ensureDir(dir); // should not throw
    assert.ok(existsSync(dir));
  });
});

describe('ensureParentDir', () => {
  it('creates parent directory for a file path', () => {
    const filePath = join(TEST_ROOT, 'parent', 'child', 'file.txt');
    ensureParentDir(filePath);
    assert.ok(existsSync(join(TEST_ROOT, 'parent', 'child')));
    assert.ok(!existsSync(filePath)); // file itself should not be created
  });
});

describe('readText', () => {
  it('reads a text file', () => {
    const file = join(TEST_ROOT, 'hello.txt');
    writeFileSync(file, 'hello world');
    assert.equal(readText(file), 'hello world');
  });

  it('returns null for missing file', () => {
    assert.equal(readText(join(TEST_ROOT, 'missing.txt')), null);
  });

  it('returns custom fallback for missing file', () => {
    assert.equal(readText(join(TEST_ROOT, 'missing.txt'), 'default'), 'default');
  });
});

describe('writeText', () => {
  it('writes text to a file', () => {
    const file = join(TEST_ROOT, 'out.txt');
    writeText(file, 'content');
    assert.equal(readFileSync(file, 'utf-8'), 'content');
  });

  it('auto-creates parent directories', () => {
    const file = join(TEST_ROOT, 'deep', 'nested', 'file.txt');
    writeText(file, 'nested content');
    assert.equal(readFileSync(file, 'utf-8'), 'nested content');
  });
});

describe('readJSON', () => {
  it('reads and parses valid JSON', () => {
    const file = join(TEST_ROOT, 'data.json');
    writeFileSync(file, JSON.stringify({ key: 'value' }));
    assert.deepEqual(readJSON(file), { key: 'value' });
  });

  it('returns null for missing file', () => {
    assert.equal(readJSON(join(TEST_ROOT, 'missing.json')), null);
  });

  it('returns fallback for missing file', () => {
    assert.deepEqual(readJSON(join(TEST_ROOT, 'missing.json'), {}), {});
  });

  it('returns fallback for corrupt JSON', () => {
    const file = join(TEST_ROOT, 'bad.json');
    writeFileSync(file, '{invalid json!!!');
    assert.equal(readJSON(file), null);
  });

  it('returns custom fallback for corrupt JSON', () => {
    const file = join(TEST_ROOT, 'bad2.json');
    writeFileSync(file, 'not json');
    assert.deepEqual(readJSON(file, { fallback: true }), { fallback: true });
  });
});

describe('writeJSON', () => {
  it('writes valid JSON to a file', () => {
    const file = join(TEST_ROOT, 'out.json');
    writeJSON(file, { hello: 'world' });
    const content = JSON.parse(readFileSync(file, 'utf-8'));
    assert.deepEqual(content, { hello: 'world' });
  });

  it('writes pretty-printed JSON', () => {
    const file = join(TEST_ROOT, 'pretty.json');
    writeJSON(file, { a: 1 });
    const raw = readFileSync(file, 'utf-8');
    assert.ok(raw.includes('\n')); // should be formatted
  });

  it('auto-creates parent directories', () => {
    const file = join(TEST_ROOT, 'sub', 'dir', 'data.json');
    writeJSON(file, [1, 2, 3]);
    assert.deepEqual(JSON.parse(readFileSync(file, 'utf-8')), [1, 2, 3]);
  });

  it('does not leave temp files on success', () => {
    const file = join(TEST_ROOT, 'clean.json');
    writeJSON(file, { clean: true });
    const files = listFiles(TEST_ROOT);
    const tmpFiles = files.filter(f => f.includes('.tmp.'));
    assert.equal(tmpFiles.length, 0);
  });

  it('overwrites existing file atomically', () => {
    const file = join(TEST_ROOT, 'overwrite.json');
    writeJSON(file, { version: 1 });
    writeJSON(file, { version: 2 });
    assert.deepEqual(readJSON(file), { version: 2 });
  });
});

describe('safeDelete', () => {
  it('deletes a file', () => {
    const file = join(TEST_ROOT, 'delete-me.txt');
    writeFileSync(file, 'bye');
    safeDelete(file);
    assert.ok(!existsSync(file));
  });

  it('does nothing for missing path', () => {
    safeDelete(join(TEST_ROOT, 'nonexistent'));
    // should not throw
  });

  it('deletes a directory recursively', () => {
    const dir = join(TEST_ROOT, 'dir-to-delete');
    mkdirSync(join(dir, 'sub'), { recursive: true });
    writeFileSync(join(dir, 'sub', 'file.txt'), 'data');
    safeDelete(dir, { recursive: true });
    assert.ok(!existsSync(dir));
  });
});

describe('cleanDir', () => {
  it('removes contents but keeps the directory', () => {
    const dir = join(TEST_ROOT, 'clean-me');
    mkdirSync(dir);
    writeFileSync(join(dir, 'a.txt'), 'a');
    writeFileSync(join(dir, 'b.txt'), 'b');
    mkdirSync(join(dir, 'sub'));
    writeFileSync(join(dir, 'sub', 'c.txt'), 'c');
    cleanDir(dir);
    assert.ok(existsSync(dir));
    assert.deepEqual(listFiles(dir), []);
  });

  it('does nothing for missing directory', () => {
    cleanDir(join(TEST_ROOT, 'nonexistent'));
    // should not throw
  });
});

describe('pathExists', () => {
  it('returns true for existing file', () => {
    const file = join(TEST_ROOT, 'exists.txt');
    writeFileSync(file, '');
    assert.ok(pathExists(file));
  });

  it('returns true for existing directory', () => {
    assert.ok(pathExists(TEST_ROOT));
  });

  it('returns false for missing path', () => {
    assert.ok(!pathExists(join(TEST_ROOT, 'nope')));
  });
});

describe('listFiles', () => {
  it('lists files in a directory', () => {
    writeFileSync(join(TEST_ROOT, 'x.txt'), '');
    writeFileSync(join(TEST_ROOT, 'y.txt'), '');
    const files = listFiles(TEST_ROOT);
    assert.ok(files.includes('x.txt'));
    assert.ok(files.includes('y.txt'));
  });

  it('returns empty array for missing directory', () => {
    assert.deepEqual(listFiles(join(TEST_ROOT, 'missing')), []);
  });
});

describe('fileInfo', () => {
  it('returns info for a file', () => {
    const file = join(TEST_ROOT, 'info.txt');
    writeFileSync(file, 'hello');
    const info = fileInfo(file);
    assert.ok(info.exists);
    assert.ok(info.isFile);
    assert.ok(!info.isDirectory);
    assert.equal(info.size, 5);
  });

  it('returns info for a directory', () => {
    const info = fileInfo(TEST_ROOT);
    assert.ok(info.exists);
    assert.ok(!info.isFile);
    assert.ok(info.isDirectory);
  });

  it('returns exists:false for missing path', () => {
    const info = fileInfo(join(TEST_ROOT, 'missing'));
    assert.ok(!info.exists);
  });
});
