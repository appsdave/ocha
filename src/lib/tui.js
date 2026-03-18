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
import { elapsed, badgeText, badgeColor } from './tui-utils.js';

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
      }
    });

    screen.key(['down'], () => {
      if (this.inputMode) return;
      if (this.selectedIdx < this.agents.length - 1) {
        this.selectedIdx++;
        this._renderAgentList();
        this._renderLog();
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
    spawnAgent(task, this.agents, (agent) => {
      // Select the new/updated agent if it's the last one
      if (this.agents[this.selectedIdx] === agent || agent === this.agents[this.agents.length - 1]) {
        this.selectedIdx = this.agents.indexOf(agent);
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

    const lines = this.agents.map((a, i) => {
      const selected = i === this.selectedIdx;
      const badge    = `${badgeColor(a.state)}${badgeText(a.state)}{/}`;
      const name     = a.task.length > 18 ? a.task.slice(0, 17) + '…' : a.task;
      const time     = a.state === 'running'
        ? elapsed(a.startedAt)
        : a.state === 'completed' ? '✔' : a.state === 'failed' ? '✗' : '■';
      const prefix   = selected ? '{cyan-fg}{bold}▶ {/bold}{/cyan-fg}' : '  ';
      return `${prefix}${badge} ${name}\n    {grey-fg}${a.branch.slice(0, 22)}{/grey-fg}  ${time}`;
    });

    this.agentList.setContent(lines.join('\n'));
    this._updateStatusBar();
  }

  _renderLog() {
    if (!this.logBox) return;
    const agent = this.agents[this.selectedIdx];
    if (!agent) {
      this.logBox.setLabel(' Log ');
      this.logBox.setContent('{grey-fg}No agent selected{/grey-fg}');
      return;
    }
    this.logBox.setLabel(` ${agent.task} [${agent.state}] `);
    this.logBox.setContent(agent.logs.join('\n'));
    this.logBox.setScrollPerc(100);
  }

  _updateStatusBar() {
    const running = this.agents.filter(a => a.state === 'running').length;
    const total   = this.agents.length;
    const agent   = this.agents[this.selectedIdx];
    const sel     = agent ? ` | ${agent.branch}` : '';
    this.statusBar.setContent(
      ` ocha  |  ${total} agent(s), ${running} running${sel}  |  n:new  K:kill  q:quit `
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
