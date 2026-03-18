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
import blessed from 'blessed';
import { buildLayout, openPromptDialog } from './tui-layout.js';
import { loadPersistedAgents, persistAgents, spawnAgent, killAgent } from './tui-agents.js';
import { elapsed, badgeText, badgeColor, truncateTask } from './tui-utils.js';

export class OchaTUI {
  constructor() {
    this.agents = loadPersistedAgents();
    this.selectedIdx = 0;
    this.screen = null;
    this.agentList = null;
    this.logBox = null;
    this.inputBar = null;
    this.statusBar = null;
    this.inputMode = false;
    this.tickInterval = null;
  }

  // ── Public entry point ────────────────────────────────────────────────────

  launch() {
    const { screen, agentList, logBox, inputBar, statusBar } = buildLayout();
    this.screen    = screen;
    this.agentList = agentList;
    this.logBox    = logBox;
    this.inputBar  = inputBar;
    this.statusBar = statusBar;

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
    screen.key(['C'], clearDone);
    // Also bind on agentList directly so vi-mode doesn't swallow the key
    this.agentList.key(['C'], clearDone);

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
    const header = `{bold}{blue-fg}ocha/{/blue-fg}{/bold} {grey-fg}(${total}){/grey-fg}`;

    const lines = this.agents.map((a, i) => {
      const selected  = i === this.selectedIdx;
      const isLast    = i === this.agents.length - 1;
      const connector = isLast ? '└─' : '├─';
      const indent    = isLast ? '  ' : '│ ';
      const badge     = `${badgeColor(a.state)}${badgeText(a.state)}{/}`;
      const maxName   = 24;
      const name      = truncateTask(a.task, maxName);
      const num       = `{grey-fg}#${String(i + 1).padStart(2, '0')}{/grey-fg}`;
      const time      = a.state === 'running'
        ? `{yellow-fg}${elapsed(a.startedAt)}{/yellow-fg}`
        : a.state === 'completed' ? '{green-fg}✔ done{/green-fg}'
        : a.state === 'failed'    ? '{red-fg}✗ fail{/red-fg}'
        : '{grey-fg}■ stop{/grey-fg}';
      const selOpen   = selected ? '{cyan-fg}{bold}' : '';
      const selClose  = selected ? '{/bold}{/cyan-fg}' : '';
      const rowStyle  = selected ? '{cyan-fg}' : '{grey-fg}';
      const prLine    = a.prUrl
        ? `\n${rowStyle}${indent}{/}  {cyan-fg}↗ PR{/cyan-fg}`
        : '';
      return `${rowStyle}${connector}{/}${badge} ${num} ${selOpen}${name}${selClose}  ${time}${prLine}`;
    });

    this.agentList.setContent([header, ...lines].join('\n'));
    this._updateStatusBar();
  }

  _renderLog() {
    if (!this.logBox) return;
    const agent = this.agents[this.selectedIdx];
    if (!agent) {
      this.logBox.setLabel(' Log ');
      this.logBox.setContent('No agent selected');
      return;
    }
    const stateLabel = agent.state === 'running' ? '⟳ running'
      : agent.state === 'completed' ? '✔ done'
      : agent.state === 'failed'    ? '✗ failed'
      : agent.state === 'stopped'   ? '■ stopped' : agent.state;

    // Truncate task label to fit the pane header cleanly
    const taskLabel = agent.task.length > 50 ? agent.task.slice(0, 49) + '…' : agent.task;
    this.logBox.setLabel(` ${taskLabel} [${stateLabel}] `);

    // Force full content replacement so switching agents always clears previous output
    this.logBox.setContent('');
    this.screen.clearRegion(0, this.screen.width, 0, this.screen.height);
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
