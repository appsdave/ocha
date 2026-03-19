import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { clearCompletedAgents, escapeTags } from './tui.js';

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
});