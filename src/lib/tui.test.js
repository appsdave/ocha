import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { clearCompletedAgents, escapeTags, formatOutputLines } from './tui.js';
import { sortAgentsForDisplay } from './tui-utils.js';

function agent(id, task, state = 'running') {
  return {
    id,
    task,
    state,
    branch: `ocha/${id}`,
    repo: 'repo',
    logs: [],
  };
}

describe('escapeTags', () => {
  it('escapes curly braces so blessed does not interpret them as markup', () => {
    assert.equal(escapeTags('{bold}hello{/bold}'), '\\{bold\\}hello\\{/bold\\}');
  });

  it('returns empty string for falsy input', () => {
    assert.equal(escapeTags(''), '');
    assert.equal(escapeTags(null), '');
    assert.equal(escapeTags(undefined), '');
  });

  it('passes through text without braces unchanged', () => {
    assert.equal(escapeTags('plain text'), 'plain text');
  });

  it('escapes braces in branch-like strings', () => {
    assert.equal(escapeTags('feature/{scope}/fix'), 'feature/\\{scope\\}/fix');
  });
});

describe('clearCompletedAgents', () => {
  it('keeps the same active agent selected when completed items above it are cleared', () => {
    const agents = [
      agent('agent-1', 'done first', 'completed'),
      agent('agent-2', 'keep me'),
      agent('agent-3', 'done second', 'completed'),
      agent('agent-4', 'keep me too'),
    ];

    const result = clearCompletedAgents(agents, 3);

    assert.deepEqual(result.agents.map(a => a.id), ['agent-2', 'agent-4']);
    assert.equal(result.selectedIdx, 1);
    assert.equal(result.agents[result.selectedIdx].id, 'agent-4');
  });

  it('moves selection to the next available agent when the selected completed agent is cleared', () => {
    const agents = [
      agent('agent-1', 'keep first'),
      agent('agent-2', 'done selected', 'completed'),
      agent('agent-3', 'keep next'),
    ];

    const result = clearCompletedAgents(agents, 1);

    assert.deepEqual(result.agents.map(a => a.id), ['agent-1', 'agent-3']);
    assert.equal(result.selectedIdx, 1);
    assert.equal(result.agents[result.selectedIdx].id, 'agent-3');
  });

  it('falls back to the previous agent when the selected completed agent was last', () => {
    const agents = [
      agent('agent-1', 'keep first'),
      agent('agent-2', 'done last', 'completed'),
    ];

    const result = clearCompletedAgents(agents, 1);

    assert.deepEqual(result.agents.map(a => a.id), ['agent-1']);
    assert.equal(result.selectedIdx, 0);
    assert.equal(result.agents[result.selectedIdx].id, 'agent-1');
  });

  it('returns an empty selection when clearing the final completed agent', () => {
    const agents = [agent('agent-1', 'done only', 'completed')];

    const result = clearCompletedAgents(agents, 0);

    assert.deepEqual(result.agents, []);
    assert.equal(result.selectedIdx, 0);
  });

  it('skips failed agents when searching forward for next selection', () => {
    const agents = [
      agent('agent-1', 'selected failed', 'failed'),
      agent('agent-2', 'also failed', 'failed'),
      agent('agent-3', 'keep me'),
    ];

    const result = clearCompletedAgents(agents, 0);

    assert.deepEqual(result.agents.map(a => a.id), ['agent-3']);
    assert.equal(result.selectedIdx, 0);
    assert.equal(result.agents[result.selectedIdx].id, 'agent-3');
  });

  it('skips stopped agents when searching backward for next selection', () => {
    const agents = [
      agent('agent-1', 'keep me'),
      agent('agent-2', 'also stopped', 'stopped'),
      agent('agent-3', 'selected stopped', 'stopped'),
    ];

    const result = clearCompletedAgents(agents, 2);

    assert.deepEqual(result.agents.map(a => a.id), ['agent-1']);
    assert.equal(result.selectedIdx, 0);
    assert.equal(result.agents[result.selectedIdx].id, 'agent-1');
  });

  it('clears all done states (completed, failed, stopped) together', () => {
    const agents = [
      agent('agent-1', 'completed one', 'completed'),
      agent('agent-2', 'keep running'),
      agent('agent-3', 'failed one', 'failed'),
      agent('agent-4', 'stopped one', 'stopped'),
    ];

    const result = clearCompletedAgents(agents, 0);

    assert.deepEqual(result.agents.map(a => a.id), ['agent-2']);
    assert.equal(result.selectedIdx, 0);
  });
});

describe('formatOutputLines', () => {
  it('extracts [ocha] milestone lines from logs', () => {
    const a = {
      logs: [
        '[ocha] Repo   : myrepo',
        '[ocha] Branch : (model will assign)',
        '[ocha] Started: 3/19/2026, 12:00:00 AM',
        '',
        'some random noise line',
        'another random line',
      ],
      state: 'running',
      logFile: null,
    };

    const lines = formatOutputLines(a);
    assert.ok(lines.some(l => l.includes('[ocha] Repo')), 'should include [ocha] Repo line');
    assert.ok(lines.some(l => l.includes('[ocha] Branch')), 'should include [ocha] Branch line');
    assert.ok(!lines.some(l => l.includes('random noise')), 'should not include non-milestone lines');
  });

  it('uses fixed label for prompt enhanced pattern', () => {
    const a = {
      logs: ['Prompt enhanced with extra details and project context gathered'],
      state: 'running',
      logFile: null,
    };

    const lines = formatOutputLines(a);
    assert.ok(lines.includes('✔ Prompt enhanced with project context'));
  });

  it('deduplicates identical milestone lines', () => {
    const a = {
      logs: [
        '[ocha] Repo   : myrepo',
        '[ocha] Repo   : myrepo',
      ],
      state: 'completed',
      logFile: null,
    };

    const lines = formatOutputLines(a);
    const repoLines = lines.filter(l => l.includes('[ocha] Repo'));
    assert.equal(repoLines.length, 1, 'should not duplicate identical lines');
  });

  it('shows log file path when logFile is set', () => {
    const a = {
      logs: ['[ocha] Repo   : myrepo'],
      state: 'completed',
      logFile: '/path/to/logs/agent-123.log',
    };

    const lines = formatOutputLines(a);
    assert.ok(lines.some(l => l.includes('📄 Full log: /path/to/logs/agent-123.log')));
  });

  it('shows pending message for running agents without log file', () => {
    const a = {
      logs: ['[ocha] Repo   : myrepo'],
      state: 'running',
      logFile: null,
    };

    const lines = formatOutputLines(a);
    assert.ok(lines.some(l => l.includes('Log file will be written when agent completes')));
  });

  it('returns empty array for agent with no matching logs and no logFile', () => {
    const a = {
      logs: ['totally unrelated line', 'another unrelated line'],
      state: 'completed',
      logFile: null,
    };

    const lines = formatOutputLines(a);
    assert.deepEqual(lines, []);
  });

  it('handles empty logs array', () => {
    const a = { logs: [], state: 'completed', logFile: null };
    const lines = formatOutputLines(a);
    assert.deepEqual(lines, []);
  });

  it('extracts completion summary lines', () => {
    const a = {
      logs: [
        '[ocha] Repo   : myrepo',
        '────────────────────────────────────────────────────',
        '  ✅  Agent completed successfully',
        '  Branch   : ocha/fix-123',
        '  Duration : 2m 30s',
        '────────────────────────────────────────────────────',
      ],
      state: 'completed',
      logFile: '/tmp/test.log',
    };

    const lines = formatOutputLines(a);
    assert.ok(lines.some(l => l.includes('Agent completed successfully')));
    assert.ok(lines.some(l => l.includes('Branch')));
    assert.ok(lines.some(l => l.includes('Duration')));
    assert.ok(lines.some(l => l.includes('📄 Full log:')));
  });
});

describe('display-order navigation', () => {
  /**
   * Simulate pressing down/up by walking the sorted display list,
   * exactly as the TUI _bindKeys handlers now do.
   */
  function navigateDown(agents, selectedIdx) {
    const sorted = sortAgentsForDisplay(agents);
    const displayIdx = sorted.findIndex(e => e.originalIndex === selectedIdx);
    if (displayIdx < sorted.length - 1) {
      return sorted[displayIdx + 1].originalIndex;
    }
    return selectedIdx;
  }

  function navigateUp(agents, selectedIdx) {
    const sorted = sortAgentsForDisplay(agents);
    const displayIdx = sorted.findIndex(e => e.originalIndex === selectedIdx);
    if (displayIdx > 0) {
      return sorted[displayIdx - 1].originalIndex;
    }
    return selectedIdx;
  }

  it('navigates down through display order: running agents first, then done', () => {
    const agents = [
      agent('a-done', 'completed task', 'completed'),
      agent('a-run',  'running task'),
      agent('a-fail', 'failed task', 'failed'),
    ];
    // display order: running(orig:1), completed(orig:0), failed(orig:2)
    let idx = 1; // start at running agent (display position 0)
    idx = navigateDown(agents, idx);
    assert.equal(idx, 0, 'should move to completed agent (orig:0, display:1)');
    idx = navigateDown(agents, idx);
    assert.equal(idx, 2, 'should move to failed agent (orig:2, display:2)');
  });

  it('navigates up through display order consistently', () => {
    const agents = [
      agent('a-done', 'completed task', 'completed'),
      agent('a-run',  'running task'),
      agent('a-fail', 'failed task', 'failed'),
    ];
    // display order: running(orig:1), completed(orig:0), failed(orig:2)
    let idx = 2; // start at failed agent (display position 2)
    idx = navigateUp(agents, idx);
    assert.equal(idx, 0, 'should move to completed agent (orig:0, display:1)');
    idx = navigateUp(agents, idx);
    assert.equal(idx, 1, 'should move to running agent (orig:1, display:0)');
  });

  it('down then up returns to the same agent', () => {
    const agents = [
      agent('a-done', 'completed task', 'completed'),
      agent('a-run1', 'running task 1'),
      agent('a-run2', 'running task 2'),
    ];
    // display order: run1(orig:1), run2(orig:2), done(orig:0)
    let idx = 1; // running task 1 (display:0)
    idx = navigateDown(agents, idx);
    assert.equal(idx, 2, 'down moves to run2');
    idx = navigateUp(agents, idx);
    assert.equal(idx, 1, 'up returns to run1');
  });

  it('stays at top when pressing up at first display item', () => {
    const agents = [
      agent('a-done', 'completed task', 'completed'),
      agent('a-run',  'running task'),
    ];
    // display order: running(orig:1), completed(orig:0)
    const idx = navigateUp(agents, 1);
    assert.equal(idx, 1, 'should stay at running agent (already at display top)');
  });

  it('stays at bottom when pressing down at last display item', () => {
    const agents = [
      agent('a-done', 'completed task', 'completed'),
      agent('a-run',  'running task'),
    ];
    // display order: running(orig:1), completed(orig:0)
    const idx = navigateDown(agents, 0);
    assert.equal(idx, 0, 'should stay at completed agent (already at display bottom)');
  });
});