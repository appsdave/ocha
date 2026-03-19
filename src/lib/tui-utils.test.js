import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { sortAgentsForDisplay, strikethrough, slugify, elapsed, badgeText, badgeColor, truncateTask, parseWorkflowEvents, renderWorkflowOutput } from './tui-utils.js';

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

  it('preserves blessed escape sequences without strikethrough', () => {
    const result = strikethrough('a\\{b\\}c');
    assert.equal(result, 'a\u0336\\{b\u0336\\}c\u0336');
  });

  it('handles text with only blessed escape sequences', () => {
    const result = strikethrough('\\{\\}');
    assert.equal(result, '\\{\\}');
  });
});

describe('parseWorkflowEvents', () => {
  it('returns empty array for empty logs', () => {
    assert.deepEqual(parseWorkflowEvents([]), []);
  });

  it('returns empty array for logs with no matching patterns', () => {
    const logs = ['some random output', 'another line', ''];
    assert.deepEqual(parseWorkflowEvents(logs), []);
  });

  it('extracts coordinator phase event', () => {
    const logs = ['\u2714 \ud83e\udde0 Prompt enhanced with project context'];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 1);
    assert.equal(events[0].phase, 'coordinator');
    assert.ok(events[0].message.includes('Prompt enhanced with project context'));
  });

  it('extracts lead phase event with task count', () => {
    const logs = ['\u2714 \ud83d\udc54 Lead planned 3 task(s) (12s)'];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 1);
    assert.equal(events[0].phase, 'lead');
    assert.ok(events[0].message.includes('Lead planned'));
  });

  it('extracts builder done event', () => {
    const logs = ['  \u2713 Builder done: update readme'];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 1);
    assert.equal(events[0].phase, 'builder');
    assert.ok(events[0].message.includes('Builder done'));
  });

  it('extracts reviewer event', () => {
    const logs = ['  \u2713 Review passed: update readme'];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 1);
    assert.equal(events[0].phase, 'reviewer');
  });

  it('extracts PR created event', () => {
    const logs = ['  \ud83d\udd17 PR created: https://github.com/org/repo/pull/42'];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 1);
    assert.equal(events[0].phase, 'PR');
    assert.ok(events[0].message.includes('https://github.com'));
  });

  it('extracts multiple events in order', () => {
    const logs = [
      '\u2714 \ud83e\udde0 Prompt enhanced with project context',
      'random noise line',
      '\u2714 \ud83d\udc54 Lead planned 2 task(s) (5s)',
      '  \u2713 Builder done: fix tests',
      '  \u2713 Review passed: fix tests',
      '  \ud83d\udd17 PR created: https://github.com/org/repo/pull/1',
    ];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 5);
    assert.equal(events[0].phase, 'coordinator');
    assert.equal(events[1].phase, 'lead');
    assert.equal(events[2].phase, 'builder');
    assert.equal(events[3].phase, 'reviewer');
    assert.equal(events[4].phase, 'PR');
  });

  it('strips ANSI escape codes before matching', () => {
    const logs = ['\x1B[32m\u2714 \ud83e\udde0 Prompt enhanced with project context\x1B[0m'];
    const events = parseWorkflowEvents(logs);
    assert.equal(events.length, 1);
    assert.equal(events[0].phase, 'coordinator');
  });
});

describe('renderWorkflowOutput', () => {
  it('returns empty output with no events for running agent', () => {
    const lines = renderWorkflowOutput([], { state: 'running', logs: [] });
    assert.equal(lines.length, 0);
  });

  it('includes workflow events as timeline entries', () => {
    const logs = [
      '\u2714 \ud83e\udde0 Prompt enhanced with project context',
      '\u2714 \ud83d\udc54 Lead planned 2 task(s) (5s)',
    ];
    const lines = renderWorkflowOutput(logs, { state: 'running' });
    const joined = lines.join('\n');
    assert.ok(joined.includes('Prompt enhanced'));
    assert.ok(joined.includes('Lead planned'));
  });

  it('shows spinner for running agents with events', () => {
    const logs = ['\u2714 \ud83e\udde0 Prompt enhanced with project context'];
    const lines = renderWorkflowOutput(logs, { state: 'running' });
    const joined = lines.join('\n');
    assert.ok(joined.includes('in progress'));
  });

  it('shows completion summary for completed agents', () => {
    const logs = ['\u2714 \ud83e\udde0 Prompt enhanced with project context'];
    const agent = {
      state: 'completed',
      startedAt: '2026-01-01T00:00:00Z',
      completedAt: '2026-01-01T00:05:30Z',
      prUrl: 'https://github.com/org/repo/pull/42',
    };
    const lines = renderWorkflowOutput(logs, agent);
    const joined = lines.join('\n');
    assert.ok(joined.includes('completed successfully'));
    assert.ok(joined.includes('pull/42'));
    assert.ok(joined.includes('5m 30s'));
  });

  it('shows failure summary for failed agents', () => {
    const logs = ['  \u2717 Builder failed after 3 attempts: fix bug'];
    const agent = { state: 'failed' };
    const lines = renderWorkflowOutput(logs, agent);
    const joined = lines.join('\n');
    assert.ok(joined.includes('Agent failed'));
  });

  it('does not show spinner for completed agents', () => {
    const logs = ['\u2714 \ud83e\udde0 Prompt enhanced with project context'];
    const agent = { state: 'completed' };
    const lines = renderWorkflowOutput(logs, agent);
    const joined = lines.join('\n');
    assert.ok(!joined.includes('in progress'));
  });
});
