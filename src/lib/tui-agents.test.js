import { describe, it, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, rmSync } from 'fs';
import { dirname } from 'path';
import { writeAgentLogFile } from './tui-agents.js';
import { LOGS_DIR } from './paths.js';

describe('writeAgentLogFile', () => {
  const createdFiles = [];

  afterEach(() => {
    for (const f of createdFiles) {
      try { rmSync(f, { force: true }); } catch {}
    }
    createdFiles.length = 0;
    // Clean up LOGS_DIR if empty
    try { rmSync(LOGS_DIR, { force: true, recursive: true }); } catch {}
  });

  it('writes agent logs to a file and returns the path', () => {
    const agent = {
      id: 'agent-1000',
      logs: ['[ocha] Repo   : myrepo', '[ocha] Started: now', 'some output'],
      completedAt: '2026-03-19T00:00:00.000Z',
      state: 'completed',
    };

    const logPath = writeAgentLogFile(agent);
    if (logPath) createdFiles.push(logPath);

    assert.ok(logPath, 'should return a log file path');
    assert.ok(existsSync(logPath), 'log file should exist on disk');
    const content = readFileSync(logPath, 'utf8');
    assert.ok(content.includes('[ocha] Repo   : myrepo'), 'should contain log lines');
    assert.ok(content.includes('some output'), 'should contain all log lines');
  });

  it('creates the logs directory if it does not exist', () => {
    // Ensure logs dir is clean before test
    try { rmSync(LOGS_DIR, { force: true, recursive: true }); } catch {}

    const agent = {
      id: 'agent-2000',
      logs: ['line1'],
      completedAt: '2026-03-19T01:00:00.000Z',
      state: 'completed',
    };

    assert.ok(!existsSync(LOGS_DIR), 'logs dir should not exist before write');
    const logPath = writeAgentLogFile(agent);
    if (logPath) createdFiles.push(logPath);
    assert.ok(logPath, 'should return a log file path');
    assert.ok(existsSync(LOGS_DIR), 'logs dir should be created');
  });

  it('strips ANSI escape codes from log content', () => {
    const agent = {
      id: 'agent-3000',
      logs: ['\x1B[32mgreen text\x1B[0m', 'plain text'],
      completedAt: '2026-03-19T02:00:00.000Z',
      state: 'completed',
    };

    const logPath = writeAgentLogFile(agent);
    if (logPath) createdFiles.push(logPath);
    const content = readFileSync(logPath, 'utf8');
    assert.ok(!content.includes('\x1B'), 'should not contain ANSI escape codes');
    assert.ok(content.includes('green text'), 'should contain stripped text');
  });

  it('uses current time when completedAt is null', () => {
    const agent = {
      id: 'agent-4000',
      logs: ['test line'],
      completedAt: null,
      state: 'failed',
    };

    const logPath = writeAgentLogFile(agent);
    if (logPath) createdFiles.push(logPath);
    assert.ok(logPath, 'should still return a log file path');
    assert.ok(existsSync(logPath), 'log file should exist');
  });

  it('handles empty logs array', () => {
    const agent = {
      id: 'agent-5000',
      logs: [],
      completedAt: '2026-03-19T03:00:00.000Z',
      state: 'completed',
    };

    const logPath = writeAgentLogFile(agent);
    if (logPath) createdFiles.push(logPath);
    assert.ok(logPath, 'should return a log file path');
    const content = readFileSync(logPath, 'utf8');
    assert.equal(content, '', 'file should be empty for empty logs');
  });
});
