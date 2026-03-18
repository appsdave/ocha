/**
 * @module tui
 * Persistent TUI shell using blessed — btop/lazygit style layout.
 *
 * Layout:
 *   ┌─ Agents ──────┬─ Log ──────────────────────────────┐
 *   │ [agent list]  │ [selected agent live log]           │
 *   │               │                                     │
 *   └───────────────┴─────────────────────────────────────┘
 *   [ > command input bar                              [q] ]
 */
import blessed from 'blessed';
import { readStatus, writeStatus } from './status.js';
import { OCHA_DIR, STATUS_FILE } from './paths.js';
import { execSync, spawn } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import chalk from 'chalk';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OCHA_ROOT = resolve(__dirname, '../..');

/** Slugify a task description for use in branch/worktree names */
function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

/** Format elapsed seconds as mm:ss */
function elapsed(startedAt) {
  if (!startedAt) return '--:--';
  const secs = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  const m = Math.floor(secs / 60).toString().padStart(2, '0');
  const s = (secs % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

/** Status badge text */
function badgeText(state) {
  switch (state) {
    case 'running':   return ' ● ';
    case 'completed': return ' ✔ ';
    case 'failed':    return ' ✗ ';
    case 'stopped':   return ' ■ ';
    default:          return ' ○ ';
  }
}

/** Status badge color */
function badgeColor(state) {
  switch (state) {
    case 'running':   return '{yellow-fg}';
    case 'completed': return '{green-fg}';
    case 'failed':    return '{red-fg}';
    case 'stopped':   return '{grey-fg}';
    default:          return '{white-fg}';
  }
}

export class OchaTUI {
  constructor() {
    this.agents = [];       // { id, task, branch, state, startedAt, logs: [], proc }
    this.selectedIdx = 0;
    this.screen = null;
    this.agentList = null;
    this.logBox = null;
    this.inputBar = null;
    this.statusBar = null;
    this.inputMode = false;
    this.inputBuffer = '';
    this.tickInterval = null;

    // Load persisted agents from status.json if present
    this._loadPersistedAgents();
  }

  _loadPersistedAgents() {
    try {
      if (existsSync(STATUS_FILE)) {
        const status = readStatus();
        if (status && status.tasks) {
          for (const t of status.tasks) {
            if (!this.agents.find(a => a.id === t.id)) {
              this.agents.push({
                id: t.id,
                task: t.displayTask || t.branch,
                branch: t.branch,
                state: t.state === 'running' ? 'stopped' : t.state,
                startedAt: t.startedAt,
                completedAt: t.completedAt,
                logs: t.logs || [],
                proc: null,
              });
            }
          }
        }
      }
    } catch (_) {}
  }

  _persistAgents() {
    try {
      if (!existsSync(OCHA_DIR)) mkdirSync(OCHA_DIR, { recursive: true });
      const existing = readStatus() || { session: { task: 'ocha tui', startedAt: new Date().toISOString(), state: 'running' }, tasks: [] };
      existing.tasks = this.agents.map(a => ({
        id: a.id,
        displayTask: a.task,
        branch: a.branch,
        state: a.state,
        startedAt: a.startedAt,
        completedAt: a.completedAt,
        logs: a.logs.slice(-200), // keep last 200 log lines
      }));
      writeStatus(existing);
    } catch (_) {}
  }

  launch() {
    const screen = blessed.screen({
      smartCSR: true,
      title: 'ocha',
      fullUnicode: true,
      forceUnicode: true,
    });
    this.screen = screen;

    // ── Left sidebar: agent list ──────────────────────────────────────────
    this.agentList = blessed.box({
      top: 0,
      left: 0,
      width: '25%',
      height: '100%-3',
      border: { type: 'line' },
      style: {
        border: { fg: 'blue' },
        focus: { border: { fg: 'cyan' } },
      },
      label: ' Agents ',
      tags: true,
      scrollable: true,
      alwaysScroll: true,
      keys: true,
      vi: true,
    });

    // ── Right pane: log output ────────────────────────────────────────────
    this.logBox = blessed.log({
      top: 0,
      left: '25%',
      width: '75%',
      height: '100%-3',
      border: { type: 'line' },
      style: { border: { fg: 'blue' } },
      label: ' Log ',
      tags: false,
      scrollable: true,
      alwaysScroll: true,
      scrollbar: { ch: '│', style: { fg: 'grey' } },
      keys: true,
      vi: true,
    });

    // ── Bottom command bar ────────────────────────────────────────────────
    this.inputBar = blessed.box({
      bottom: 1,
      left: 0,
      width: '100%',
      height: 1,
      style: { fg: 'white', bg: 'black' },
      tags: true,
      content: '{grey-fg}  Press {bold}n{/bold} to start a new task, {bold}↑↓{/bold} to navigate, {bold}k{/bold} kill, {bold}q{/bold} quit{/grey-fg}',
    });

    // ── Status bar ────────────────────────────────────────────────────────
    this.statusBar = blessed.box({
      bottom: 0,
      left: 0,
      width: '100%',
      height: 1,
      style: { fg: 'black', bg: 'blue' },
      tags: true,
      content: ' ocha  |  0 agents ',
    });

    screen.append(this.agentList);
    screen.append(this.logBox);
    screen.append(this.inputBar);
    screen.append(this.statusBar);

    this._bindKeys();
    this._renderAgentList();
    this._startTick();

    screen.render();
    this.agentList.focus();
  }

  _bindKeys() {
    const screen = this.screen;

    // Global quit
    screen.key(['q', 'C-c'], () => this._quit());

    // Navigate agents
    screen.key(['up', 'k'], () => {
      if (this.inputMode) return;
      if (this.selectedIdx > 0) {
        this.selectedIdx--;
        this._renderAgentList();
        this._renderLog();
      }
    });
    screen.key(['down', 'j'], () => {
      if (this.inputMode) return;
      if (this.selectedIdx < this.agents.length - 1) {
        this.selectedIdx++;
        this._renderAgentList();
        this._renderLog();
      }
    });

    // New task
    screen.key(['n'], () => {
      if (!this.inputMode) this._openInput();
    });

    // Kill selected agent
    screen.key(['K'], () => {
      if (this.inputMode) return;
      this._killSelected();
    });

    // Focus log pane for scrolling
    screen.key(['l', 'right'], () => {
      if (this.inputMode) return;
      this.logBox.focus();
    });
    screen.key(['h', 'left'], () => {
      if (this.inputMode) return;
      this.agentList.focus();
    });
  }

  _openInput() {
    this.inputMode = true;
    this.inputBuffer = '';

    const inputWidget = blessed.textbox({
      bottom: 1,
      left: 0,
      width: '100%',
      height: 1,
      style: { fg: 'white', bg: 'black' },
      inputOnFocus: true,
    });

    this.screen.append(inputWidget);
    this.inputBar.setContent('{cyan-fg}  New task: {/cyan-fg}');
    this.screen.render();
    inputWidget.focus();
    inputWidget.readInput((err, value) => {
      this.screen.remove(inputWidget);
      this.inputMode = false;
      this.inputBar.setContent('{grey-fg}  Press {bold}n{/bold} to start a new task, {bold}↑↓{/bold} to navigate, {bold}k{/bold} kill, {bold}q{/bold} quit{/grey-fg}');
      if (!err && value && value.trim()) {
        this._spawnAgent(value.trim());
      }
      this.agentList.focus();
      this.screen.render();
    });
  }

  _spawnAgent(task) {
    const now = new Date();
    const ts = now.toISOString().replace(/[-:T]/g, '').slice(0, 15).replace(/(\d{8})(\d{6})/, '$1-$2');
    const slug = slugify(task);
    const branch = `ocha/${slug}-${ts}`;
    const id = `agent-${Date.now()}`;

    const agent = {
      id,
      task,
      branch,
      state: 'running',
      startedAt: now.toISOString(),
      completedAt: null,
      logs: [],
      proc: null,
    };

    this.agents.push(agent);
    this.selectedIdx = this.agents.length - 1;

    // Log startup
    agent.logs.push(`[ocha] Starting agent for: ${task}`);
    agent.logs.push(`[ocha] Branch: ${branch}`);
    agent.logs.push(`[ocha] Time: ${now.toLocaleString()}`);
    agent.logs.push('');

    // Spawn the ocha cord-start process
    const proc = spawn(process.execPath, [
      resolve(OCHA_ROOT, 'bin/ocha.js'),
      '--tui-agent',
      '--task', task,
      '--branch', branch,
    ], {
      cwd: process.cwd(),
      env: { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1' },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    agent.proc = proc;

    proc.stdout.on('data', (chunk) => {
      const lines = chunk.toString().split('\n');
      for (const line of lines) {
        if (line) {
          agent.logs.push(line);
          if (agent.logs.length > 2000) agent.logs.shift();
        }
      }
      if (this.agents[this.selectedIdx] === agent) {
        this._renderLog();
        this.screen.render();
      }
    });

    proc.stderr.on('data', (chunk) => {
      const lines = chunk.toString().split('\n');
      for (const line of lines) {
        if (line) {
          agent.logs.push(`[err] ${line}`);
          if (agent.logs.length > 2000) agent.logs.shift();
        }
      }
      if (this.agents[this.selectedIdx] === agent) {
        this._renderLog();
        this.screen.render();
      }
    });

    proc.on('close', (code) => {
      agent.proc = null;
      agent.state = code === 0 ? 'completed' : 'failed';
      agent.completedAt = new Date().toISOString();
      agent.logs.push('');
      agent.logs.push(`[ocha] Agent exited with code ${code}`);
      this._persistAgents();
      this._renderAgentList();
      if (this.agents[this.selectedIdx] === agent) {
        this._renderLog();
      }
      this.screen.render();
    });

    this._persistAgents();
    this._renderAgentList();
    this._renderLog();
    this.screen.render();
  }

  _killSelected() {
    const agent = this.agents[this.selectedIdx];
    if (!agent) return;
    if (agent.proc) {
      agent.proc.kill('SIGTERM');
      agent.state = 'stopped';
      agent.logs.push('[ocha] Agent killed by user');
    }
    this._renderAgentList();
    this._renderLog();
    this.screen.render();
  }

  _renderAgentList() {
    if (!this.agentList) return;
    if (this.agents.length === 0) {
      this.agentList.setContent('{grey-fg}\n  No agents yet.\n  Press {bold}n{/bold} to start one.{/grey-fg}');
      this._updateStatusBar();
      return;
    }

    const lines = this.agents.map((a, i) => {
      const selected = i === this.selectedIdx;
      const badge = `${badgeColor(a.state)}${badgeText(a.state)}{/}`;
      const name = a.task.length > 18 ? a.task.slice(0, 17) + '…' : a.task;
      const time = a.state === 'running' ? elapsed(a.startedAt) : (a.state === 'completed' ? '✔' : a.state === 'failed' ? '✗' : '■');
      const prefix = selected ? '{cyan-fg}{bold}▶ {/bold}{/cyan-fg}' : '  ';
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
    const total = this.agents.length;
    const agent = this.agents[this.selectedIdx];
    const sel = agent ? ` | selected: ${agent.branch}` : '';
    this.statusBar.setContent(` ocha  |  ${total} agent(s), ${running} running${sel}  |  n:new  k:kill  q:quit `);
  }

  _startTick() {
    this.tickInterval = setInterval(() => {
      const hasRunning = this.agents.some(a => a.state === 'running');
      if (hasRunning) {
        this._renderAgentList();
        this.screen.render();
      }
    }, 1000);
  }

  _quit() {
    const running = this.agents.filter(a => a.state === 'running');
    if (running.length > 0) {
      // Show confirmation
      const confirm = blessed.question({
        top: 'center',
        left: 'center',
        width: 50,
        height: 7,
        border: { type: 'line' },
        style: { border: { fg: 'red' }, fg: 'white', bg: 'black' },
        label: ' Quit? ',
        tags: true,
      });
      this.screen.append(confirm);
      confirm.ask(`${running.length} agent(s) still running. Kill all and quit? (y/n)`, (err, value) => {
        if (value === true || value === 'y' || value === 'yes') {
          for (const a of running) {
            if (a.proc) a.proc.kill('SIGTERM');
          }
          this._persistAgents();
          this._cleanup();
        } else {
          this.screen.remove(confirm);
          this.screen.render();
        }
      });
    } else {
      this._persistAgents();
      this._cleanup();
    }
  }

  _cleanup() {
    if (this.tickInterval) clearInterval(this.tickInterval);
    this.screen.destroy();
    process.exit(0);
  }
}
