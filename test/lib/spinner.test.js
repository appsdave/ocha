import { describe, it, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { startSpinner, updateSpinner, stopSpinner, logWithSpinner, succeedSpinner, failSpinner } from '../../src/lib/spinner.js';

describe('spinner', () => {
  afterEach(() => {
    // Ensure spinner is stopped between tests
    stopSpinner();
  });

  it('startSpinner returns a spinner instance', () => {
    const spinner = startSpinner('loading…');
    assert.ok(spinner);
    assert.equal(spinner.text, 'loading…');
  });

  it('startSpinner updates text if already active', () => {
    const s1 = startSpinner('first');
    const s2 = startSpinner('second');
    assert.equal(s1, s2, 'should return the same spinner instance');
    assert.equal(s2.text, 'second');
  });

  it('updateSpinner changes text on active spinner', () => {
    const spinner = startSpinner('initial');
    updateSpinner('updated');
    assert.equal(spinner.text, 'updated');
  });

  it('updateSpinner is a no-op when no spinner is active', () => {
    // Should not throw
    updateSpinner('nothing');
  });

  it('stopSpinner stops the active spinner', () => {
    startSpinner('running');
    stopSpinner();
    // Starting a new one should create a fresh instance
    const s = startSpinner('new');
    assert.equal(s.text, 'new');
  });

  it('succeedSpinner stops with success', () => {
    startSpinner('working');
    succeedSpinner('done!');
    // No active spinner after succeed
    updateSpinner('should be no-op');
  });

  it('failSpinner stops with failure', () => {
    startSpinner('working');
    failSpinner('oops');
    // No active spinner after fail
    updateSpinner('should be no-op');
  });

  it('logWithSpinner logs without active spinner', () => {
    // Should not throw when no spinner is active
    logWithSpinner('hello');
  });

  it('logWithSpinner pauses and resumes active spinner', () => {
    const spinner = startSpinner('running');
    logWithSpinner('a log line');
    // Spinner should still be active
    assert.equal(spinner.text, 'running');
  });
});
