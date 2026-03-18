import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { sortAgentsForDisplay, strikethrough, slugify, elapsed, badgeText, badgeColor, truncateTask } from './tui-utils.js';

describe('sortAgentsForDisplay', () => {
  it('returns empty array for empty input', () => {
    assert.deepEqual(sortAgentsForDisplay([]), []);
  });

  it('keeps running agents before completed agents', () => {
    const agents = [
      { state: 'completed', task: 'done task' },
      { state: 'running',   task: 'active task' },
    ];
    const sorted = sortAgentsForDisplay(agents);
    assert.equal(sorted[0].agent.task, 'active task');
    assert.equal(sorted[1].agent.task, 'done task');
  });

  it('keeps running agents before failed and stopped agents', () => {
    const agents = [
      { state: 'failed',  task: 'fail task' },
      { state: 'running', task: 'run task' },
      { state: 'stopped', task: 'stop task' },
    ];
    const sorted = sortAgentsForDisplay(agents);
    assert.equal(sorted[0].agent.task, 'run task');
    assert.equal(sorted[1].agent.task, 'fail task');
    assert.equal(sorted[2].agent.task, 'stop task');
  });

  it('preserves relative order among running agents', () => {
    const agents = [
      { state: 'running', task: 'first' },
      { state: 'running', task: 'second' },
    ];
    const sorted = sortAgentsForDisplay(agents);
    assert.equal(sorted[0].agent.task, 'first');
    assert.equal(sorted[1].agent.task, 'second');
  });

  it('preserves relative order among done agents', () => {
    const agents = [
      { state: 'completed', task: 'a' },
      { state: 'failed',    task: 'b' },
      { state: 'stopped',   task: 'c' },
    ];
    const sorted = sortAgentsForDisplay(agents);
    assert.equal(sorted[0].agent.task, 'a');
    assert.equal(sorted[1].agent.task, 'b');
    assert.equal(sorted[2].agent.task, 'c');
  });

  it('tracks original indices correctly', () => {
    const agents = [
      { state: 'completed', task: 'done' },
      { state: 'running',   task: 'active' },
      { state: 'failed',    task: 'fail' },
    ];
    const sorted = sortAgentsForDisplay(agents);
    assert.equal(sorted[0].originalIndex, 1); // running was at index 1
    assert.equal(sorted[1].originalIndex, 0); // completed was at index 0
    assert.equal(sorted[2].originalIndex, 2); // failed was at index 2
  });

  it('handles all-running agents without reordering', () => {
    const agents = [
      { state: 'running', task: 'a' },
      { state: 'running', task: 'b' },
      { state: 'running', task: 'c' },
    ];
    const sorted = sortAgentsForDisplay(agents);
    assert.equal(sorted[0].originalIndex, 0);
    assert.equal(sorted[1].originalIndex, 1);
    assert.equal(sorted[2].originalIndex, 2);
  });
});

describe('strikethrough', () => {
  it('returns empty string for empty input', () => {
    assert.equal(strikethrough(''), '');
  });

  it('applies combining stroke to each character', () => {
    const result = strikethrough('abc');
    assert.equal(result, 'a\u0336b\u0336c\u0336');
  });

  it('applies combining stroke to single character', () => {
    const result = strikethrough('x');
    assert.equal(result, 'x\u0336');
  });

  it('applies combining stroke to multi-word text', () => {
    const result = strikethrough('hi there');
    assert.equal(result, 'h\u0336i\u0336 \u0336t\u0336h\u0336e\u0336r\u0336e\u0336');
  });
});
