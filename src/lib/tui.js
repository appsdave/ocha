/**
 * @module tui
 * Persistent TUI shell — btop/lazygit style layout.
 *
 * Layout:
 *   ┌─ Agents ──────┬─ Log ──────────────────────────────┐
 *   │ [agent list]  │ [selected agent live log]           │
 *   └───────────────┴─────────────────────────────────────┘
 *   [ hint bar                                            ]
 *   [ status bar                                          ]
 *
 * Keyboard shortcuts:
 *   n        — open new task prompt
 *   ↑ / ↓   — navigate agent list
 *   K        — kill selected agent
 *   l / →   — focus log pane
 *   h / ←   — focus agent list
 *   q / C-c — quit (confirms if agents running)
 */
import { basename } from 'path';
import blessed from 'blessed';
import { buildLayout, openPromptDialog } from './tui-layout.js';
import { loadPersistedAgents, persistAgents, spawnAgent, killAgent } from './tui-agents.js';
import { elapsed, badgeText, badgeColor, truncateTask, sortAgentsForDisplay, strikethrough } from './tui-utils.js';

/**
 * Detect which pipeline phases have started/completed from log lines.
 * Returns an array of { name, done, active } in pipeline order.
 * @param {string[]} logs
 * @returns {{ name: string, done: boolean, active: boolean }[]}
 */
function _detectPhases(logs) {
  const joined = logs.join('\n');
  const phases = [
    { name: 'coordinator', patterns: ['Prompt enhanced', 'project context', 'ocha cord start', 'Checking prerequisites'] },
    { name: 'lead',        patterns: ['Lead agent', 'Planned ', 'Planning tasks'] },
    { name: 'builder',     patterns: ['Builder', 'builder', 'createWorktree', 'Dispatching'] },
    { name: 'reviewer',    patterns: ['Reviewer', 'reviewer', 'Review'] },
    { name: 'PR',          patterns: ['pull/'] },
  ];

  let lastActive = -1;
  const result = phases.map((p, i) => {
    const seen = p.patterns.some(pat => joined.includes(pat));
    if (seen) lastActive = i;
    return { name: p.name, seen };
  });

  return result.map((p, i) => ({
    name: p.name,
    done:   p.seen && i < lastActive,
    active: p.seen && i === lastActive,
  }));
}

export class OchaTUI {
  constructor() {
    this.agents = loadPersistedAgents();
    this.selectedIdx = 0;
    this.screen = null;
    this.agentList = null;
    this.taskHeader = null;
    this.logBox = null;
    this.inputBar = null;
    this.statusBar = null;
    this.inputMode = false;
    this.tickInterval = null;
  }

  // ── Public entry point ────────────────────────────────────────────────────

  launch() {
    const { screen, agentList, taskHeader, logBox, inputBar, statusBar } = buildLayout();
    this.screen     = screen;
    this.agentList  = agentList;
    this.taskHeader = taskHeader;
    this.logBox     = logBox;
    this.inputBar   = inputBar;
    this.statusBar  = statusBar;

    screen.on('error', (err) => {
      screen.destroy();
      process.stderr.write(`[ocha] TUI error: ${err.message}\n${err.stack}\n`);
      process.exit(1);
    });

    this._bindKeys();
    this._renderAgentList();
    this._renderLog();
    this._startTick();

    screen.render();
    agentList.focus();
  }

  // ── Keyboard bindings ─────────────────────────────────────────────────────

  _bindKeys() {
    const screen = this.screen;

    screen.key(['q', 'C-c'], () => this._quit());

    screen.key(['up'], () => {
      if (this.inputMode) return;
      if (this.selectedIdx > 0) {
        this.selectedIdx--;
        this._renderAgentList();
        this._renderLog();
        this.screen.render();
      }
    });

    screen.key(['down'], () => {
      if (this.inputMode) return;
      if (this.selectedIdx < this.agents.length - 1) {
        this.selectedIdx++;
        this._renderAgentList();
        this._renderLog();
        this.screen.render();
      }
    });

    screen.key(['n'], () => {
      if (this.inputMode) return;
      this.inputMode = true;
      openPromptDialog(this.screen, (task) => {
        this.inputMode = false;
        if (task) this._spawnAgent(task);
        this.agentList.focus();
        this.screen.render();
      });
    });

    screen.key(['K'], () => {
      if (this.inputMode) return;
      killAgent(this.agents, this.selectedIdx);
      this._renderAgentList();
      this._renderLog();
      this.screen.render();
    });

    const clearDone = () => {
      if (this.inputMode) return;
      this.agents = this.agents.filter(a => a.state === 'running');
      this.selectedIdx = Math.min(this.selectedIdx, Math.max(0, this.agents.length - 1));
      persistAgents(this.agents);
      this._renderAgentList();
      this._renderLog();
      this.screen.render();
    };
    // Bind all forms: 'C' (uppercase), 'S-c' (shift+c), and 'x' as fallback
    screen.key(['C', 'S-c', 'x'], clearDone);
    this.agentList.key(['C', 'S-c', 'x'], clearDone);
    this.logBox.key(['C', 'S-c', 'x'], clearDone);

    screen.key(['l', 'right'], () => {
      if (this.inputMode) return;
      this.logBox.focus();
    });

    screen.key(['h', 'left'], () => {
      if (this.inputMode) return;
      this.agentList.focus();
    });
  }

  // ── Agent management ──────────────────────────────────────────────────────

  _spawnAgent(task) {
    // Clear log immediately so no previous agent's text shows before new logs arrive
    this.logBox.setContent('');
    this.taskHeader.setContent('');
    this.screen.render();

    spawnAgent(task, this.agents, (agent) => {
      // Only re-render log if this agent is currently selected
      if (this.agents[this.selectedIdx] === agent) {
        this._renderLog();
      }
      this._renderAgentList();
      this.screen.render();
    });

    this.selectedIdx = this.agents.length - 1;
    persistAgents(this.agents);
    this._renderAgentList();
    this._renderLog();
    this.screen.render();
  }

  // ── Render helpers ────────────────────────────────────────────────────────

  _renderAgentList() {
    if (!this.agentList) return;

    if (this.agents.length === 0) {
      this.agentList.setContent(
        '{grey-fg}\n  No agents yet.\n  Press {bold}n{/bold} to start one.{/grey-fg}'
      );
      this._updateStatusBar();
      return;
    }

    const total  = this.agents.length;
    const repoName = basename(process.cwd());
    const header = `{bold}{blue-fg}ocha/{/blue-fg}{white-fg}${repoName}{/white-fg}{/bold} {grey-fg}(${total}){/grey-fg}`;

    const sorted = sortAgentsForDisplay(this.agents);

    const lines = sorted.map((entry, displayIdx) => {
      const a = entry.agent;
      const i = entry.originalIndex;
      const selected  = i === this.selectedIdx;
      const isLast    = displayIdx === sorted.length - 1;
      const connector = isLast ? '└─' : '├─';
      const indent    = isLast ? '  ' : '│ ';
      const isDone    = a.state !== 'running';
      const badge     = `${badgeColor(a.state)}${badgeText(a.state)}{/}`;
      const maxName   = 24;
      const name      = isDone
        ? strikethrough(truncateTask(a.task, maxName))
        : truncateTask(a.task, maxName);
      const num       = `{grey-fg}#${String(i + 1).padStart(2, '0')}{/grey-fg}`;
      const time      = a.state === 'running'
        ? `{yellow-fg}${elapsed(a.startedAt)}{/yellow-fg}`
        : a.state === 'completed' ? '{green-fg}✔ done{/green-fg}'
        : a.state === 'failed'    ? '{red-fg}✗ fail{/red-fg}'
        : '{grey-fg}■ stop{/grey-fg}';
      const selOpen   = selected ? '{cyan-fg}{bold}' : '';
      const selClose  = selected ? '{/bold}{/cyan-fg}' : '';
      const rowStyle  = selected ? '{cyan-fg}' : isDone ? '{grey-fg}' : '{grey-fg}';
      const branchDisplay = a.branch
        ? (a.repo ? `${a.repo}/${a.branch}` : a.branch).slice(-34)
        : null;
      const branchLine = branchDisplay
        ? `\n${rowStyle}${indent}{/}  {grey-fg}⎇ ${branchDisplay}{/grey-fg}`
        : '';
      const prLine    = a.prUrl
        ? `\n${rowStyle}${indent}{/}  {cyan-fg}↗ ${a.prUrl}{/cyan-fg}`
        : '';
      return `${rowStyle}${connector}{/}${badge} ${num} ${selOpen}${name}${selClose}  ${time}${branchLine}${prLine}`;
    });

    this.agentList.setContent([header, ...lines].join('\n'));
    this._updateStatusBar();
  }

  _renderLog() {
    if (!this.logBox) return;
    const agent = this.agents[this.selectedIdx];
    if (!agent) {
      this.taskHeader.setContent('{grey-fg}  No agent selected{/grey-fg}');
      this.logBox.setLabel(' Output ');
      this.logBox.setContent('');
      return;
    }

    // ── Task header: task name + phase pipeline ──────────────────────────
    const stateColor = agent.state === 'running' ? '{yellow-fg}'
      : agent.state === 'completed' ? '{green-fg}'
      : agent.state === 'failed'    ? '{red-fg}'
      : '{grey-fg}';
    const stateLabel = agent.state === 'running' ? '⟳ running'
      : agent.state === 'completed' ? '✔ done'
      : agent.state === 'failed'    ? '✗ failed'
      : agent.state === 'stopped'   ? '■ stopped' : agent.state;

    const taskLine = agent.task.length > 70 ? agent.task.slice(0, 69) + '…' : agent.task;
    const phases = _detectPhases(agent.logs);
    const phaseBar = phases.map(p =>
      p.active   ? `{cyan-fg}{bold}[${p.name}]{/bold}{/cyan-fg}`
      : p.done   ? `{green-fg}[${p.name}]{/green-fg}`
      : `{grey-fg}[${p.name}]{/grey-fg}`
    ).join(' → ');

    this.taskHeader.setContent(
      `  {bold}{white-fg}${taskLine}{/white-fg}{/bold}  ${stateColor}${stateLabel}{/}\n` +
      `  ${phaseBar}\n` +
      (agent.branch ? `  {grey-fg}⎇ ${agent.branch}{/grey-fg}` : '')
    );

    // ── Log pane: raw output ─────────────────────────────────────────────
    this.logBox.setContent(agent.logs.join('\n'));
    this.logBox.setScrollPerc(100);
  }

  _updateStatusBar() {
    const running = this.agents.filter(a => a.state === 'running').length;
    const done    = this.agents.filter(a => a.state === 'completed').length;
    const total   = this.agents.length;
    const agent   = this.agents[this.selectedIdx];
    let right = '';
    if (agent) {
      const repoPrefix = agent.repo ? `${agent.repo}/` : '';
      right = agent.prUrl
        ? ` | PR: ${agent.prUrl}`
        : ` | ${repoPrefix}${agent.branch}`;
    }
    this.statusBar.setContent(
      ` ocha  |  ${total} task(s)  ${running} running  ${done} done${right} `
    );
  }

  // ── Tick (live elapsed timer) ─────────────────────────────────────────────

  _startTick() {
    this.tickInterval = setInterval(() => {
      if (this.agents.some(a => a.state === 'running')) {
        this._renderAgentList();
        this.screen.render();
      }
    }, 1000);
  }

  // ── Quit ──────────────────────────────────────────────────────────────────

  _quit() {
    const running = this.agents.filter(a => a.state === 'running');
    if (running.length > 0) {
      const confirm = blessed.question({
        top: 'center',
        left: 'center',
        width: 52,
        height: 7,
        border: { type: 'line' },
        style: { border: { fg: 'red' }, fg: 'white', bg: 'black' },
        label: ' Quit? ',
        tags: true,
      });
      this.screen.append(confirm);
      confirm.ask(
        `${running.length} agent(s) still running. Kill all and quit? (y/n)`,
        (err, value) => {
          if (value === true || value === 'y' || value === 'yes') {
            for (const a of running) if (a.proc) a.proc.kill('SIGTERM');
            persistAgents(this.agents);
            this._cleanup();
          } else {
            this.screen.remove(confirm);
            this.screen.render();
          }
        }
      );
    } else {
      persistAgents(this.agents);
      this._cleanup();
    }
  }

  _cleanup() {
    if (this.tickInterval) clearInterval(this.tickInterval);
    this.screen.destroy();
    process.exit(0);
  }
}
