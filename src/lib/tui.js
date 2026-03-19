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
 *   k        — kill selected agent
 *   c        — clear completed/failed agents
 *   v        — toggle workflow / raw log view
 *   l / →   — focus log pane
 *   h / ←   — focus agent list
 *   q / C-c — quit (confirms if agents running)
 *
 *  Inside the new-task prompt:
 *   Enter    — newline (multi-line input)
 *   Ctrl-S   — submit the task
 *   Escape   — cancel
 */
import { basename } from 'path';
import blessed from 'blessed';
import { buildLayout, openPromptDialog } from './tui-layout.js';
import { loadPersistedAgents, persistAgents, spawnAgent, killAgent } from './tui-agents.js';
import { elapsed, badgeText, badgeColor, truncateTask, sortAgentsForDisplay, strikethrough, renderWorkflowOutput } from './tui-utils.js';

/**
 * Escape blessed tag characters in user-supplied text so `{` and `}` are
 * rendered literally instead of being interpreted as markup.
 */
export function escapeTags(str) {
  if (!str) return '';
  return str.replace(/\{/g, '\\{').replace(/\}/g, '\\}');
}

/**
 * Milestone patterns used to extract key output lines from raw agent logs.
 * Each entry has a regex `pattern` and an optional fixed `label`.
 * When `label` is null the original log line is shown as-is.
 */
export const MILESTONE_PATTERNS = [
  { pattern: /^\[ocha\]/, label: null },
  { pattern: /Prompt enhanced|project context/, label: '✔ Prompt enhanced with project context' },
  { pattern: /Planned\s+\d+|Planning tasks|Lead agent/, label: null },
  { pattern: /Builder|builder|createWorktree|Dispatching/, label: null },
  { pattern: /Reviewer|reviewer|Review/, label: null },
  { pattern: /pull\/\d+/, label: null },
  { pattern: /✅|❌|completed|failed|Agent completed|Agent failed/, label: null },
  { pattern: /─{4,}/, label: null },
  { pattern: /Branch\s*:/, label: null },
  { pattern: /Duration\s*:/, label: null },
  { pattern: /PR\s*:/, label: null },
  { pattern: /Repo\s*:/, label: null },
];

/**
 * Extract formatted output lines from agent logs.
 * Shows key milestone events instead of raw log output.
 * @param {object} agent
 * @returns {string[]}
 */
export function formatOutputLines(agent) {
  const lines = [];
  const seen = new Set();

  for (const log of agent.logs) {
    const stripped = log.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '').trim();
    if (!stripped) continue;

    for (const mp of MILESTONE_PATTERNS) {
      if (mp.pattern.test(stripped)) {
        const display = mp.label || stripped;
        if (!seen.has(display)) {
          seen.add(display);
          lines.push(display);
        }
        break;
      }
    }
  }

  if (agent.logFile) {
    lines.push('');
    lines.push(`📄 Full log: ${agent.logFile}`);
  } else if (agent.state === 'running') {
    lines.push('');
    lines.push('{grey-fg}Log file will be written when agent completes.{/grey-fg}');
  }

  return lines;
}

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

/**
 * Remove completed agents while keeping selection aligned to a stable agent.
 * If the selected agent is removed, selection moves to the next remaining
 * agent, or the previous one when there is no next agent.
 *
 * @param {object[]} agents
 * @param {number} selectedIdx
 * @returns {{ agents: object[], selectedIdx: number }}
 */
export function clearCompletedAgents(agents, selectedIdx) {
  const remainingAgents = agents.filter(agent => agent.state !== 'completed' && agent.state !== 'stopped' && agent.state !== 'failed');
  if (remainingAgents.length === 0) return { agents: remainingAgents, selectedIdx: 0 };

  const clampedIdx = Math.min(Math.max(selectedIdx, 0), Math.max(0, agents.length - 1));
  const selectedAgent = agents[clampedIdx];

  const doneStates = new Set(['completed', 'stopped', 'failed']);
  if (selectedAgent && !doneStates.has(selectedAgent.state)) {
    const nextIdx = remainingAgents.findIndex(agent => agent.id === selectedAgent.id);
    if (nextIdx >= 0) return { agents: remainingAgents, selectedIdx: nextIdx };
  }

  for (let idx = clampedIdx + 1; idx < agents.length; idx++) {
    if (doneStates.has(agents[idx].state)) continue;
    const nextIdx = remainingAgents.findIndex(agent => agent.id === agents[idx].id);
    if (nextIdx >= 0) return { agents: remainingAgents, selectedIdx: nextIdx };
  }

  for (let idx = clampedIdx - 1; idx >= 0; idx--) {
    if (doneStates.has(agents[idx].state)) continue;
    const nextIdx = remainingAgents.findIndex(agent => agent.id === agents[idx].id);
    if (nextIdx >= 0) return { agents: remainingAgents, selectedIdx: nextIdx };
  }

  return { agents: remainingAgents, selectedIdx: 0 };
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
    this.rawLogView = false;
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

    // Ensure child agent processes are killed when ocha exits unexpectedly
    this._installSignalHandlers();

    this._bindKeys();
    this._renderAgentList();
    this._clearAndRenderLog();
    this._startTick();

    // Re-render all panes on terminal resize to prevent text bleaching/overlap.
    // screen.alloc() reallocates the internal line buffer for the new
    // dimensions, ensuring no stale pixels survive the resize.
    screen.on('resize', () => {
      this._renderAgentList();
      this._clearAndRenderLog();
      screen.alloc();
      screen.render();
    });

    screen.render();
    agentList.focus();
  }

  // ── Keyboard bindings ─────────────────────────────────────────────────────

  _bindKeys() {
    const screen = this.screen;

    screen.key(['q', 'C-c'], () => this._quit());

    screen.key(['up'], () => {
      if (this.inputMode) return;
      const sorted = sortAgentsForDisplay(this.agents);
      const displayIdx = sorted.findIndex(e => e.originalIndex === this.selectedIdx);
      if (displayIdx > 0) {
        this.selectedIdx = sorted[displayIdx - 1].originalIndex;
        this._renderAgentList();
        this._clearAndRenderLog();
        this.screen.render();
      }
    });

    screen.key(['down'], () => {
      if (this.inputMode) return;
      const sorted = sortAgentsForDisplay(this.agents);
      const displayIdx = sorted.findIndex(e => e.originalIndex === this.selectedIdx);
      if (displayIdx < sorted.length - 1) {
        this.selectedIdx = sorted[displayIdx + 1].originalIndex;
        this._renderAgentList();
        this._clearAndRenderLog();
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

    screen.key(['k'], () => {
      if (this.inputMode) return;
      killAgent(this.agents, this.selectedIdx);
      persistAgents(this.agents);
      this._renderAgentList();
      this._clearAndRenderLog();
      this.screen.render();
    });

    const clearDone = () => {
      if (this.inputMode) return;
      const nextState = clearCompletedAgents(this.agents, this.selectedIdx);
      this.agents = nextState.agents;
      this.selectedIdx = nextState.selectedIdx;
      persistAgents(this.agents);
      this._renderAgentList();
      this._clearAndRenderLog();
      this.screen.render();
    };
    // Bind 'c' for clear done (lowercase to avoid conflict with C-c)
    screen.key(['c'], clearDone);
    this.agentList.key(['c'], clearDone);
    this.logBox.key(['c'], clearDone);

    screen.key(['l', 'right'], () => {
      if (this.inputMode) return;
      this.logBox.focus();
    });

    screen.key(['h', 'left'], () => {
      if (this.inputMode) return;
      this.agentList.focus();
    });

    screen.key(['v'], () => {
      if (this.inputMode) return;
      this.rawLogView = !this.rawLogView;
      this._clearAndRenderLog();
      this.screen.render();
    });
  }

  // ── Agent management ──────────────────────────────────────────────────────

  _spawnAgent(task) {
    // Clear log content — do NOT render here to avoid a blank-screen flash
    this.logBox.setContent('');
    this.taskHeader.setContent('');

    spawnAgent(task, this.agents, (agent) => {
      // Only re-render log if this agent is currently selected
      if (this.agents[this.selectedIdx] === agent) {
        this._clearAndRenderLog();
      }
      this._renderAgentList();
      this.screen.render();
    });

    this.selectedIdx = this.agents.length - 1;
    persistAgents(this.agents);
    this._renderAgentList();
    this._clearAndRenderLog();
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
        ? strikethrough(escapeTags(truncateTask(a.task, maxName)))
        : escapeTags(truncateTask(a.task, maxName));
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
        ? escapeTags((a.repo ? `${a.repo}/${a.branch}` : a.branch).slice(-34))
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

    const rawTask = agent.task.length > 70 ? agent.task.slice(0, 69) + '…' : agent.task;
    const taskLine = escapeTags(rawTask);
    const phases = _detectPhases(agent.logs);
    const phaseBar = phases.map(p =>
      p.active   ? `{cyan-fg}{bold}[${p.name}]{/bold}{/cyan-fg}`
      : p.done   ? `{green-fg}[${p.name}]{/green-fg}`
      : `{grey-fg}[${p.name}]{/grey-fg}`
    ).join(' → ');

    const branchDisplay = agent.branch ? escapeTags(agent.branch) : '';
    this.taskHeader.setContent(
      `  {bold}{white-fg}${taskLine}{/white-fg}{/bold}  ${stateColor}${stateLabel}{/}\n` +
      `  ${phaseBar}\n` +
      (branchDisplay ? `  {grey-fg}⎇ ${branchDisplay}{/grey-fg}` : '')
    );

    // ── Log pane: structured workflow output or raw log ────────────────
    if (this.rawLogView) {
      this.logBox.setLabel(' Output (raw) — press v for workflow view ');
      this.logBox.setContent(agent.logs.join('\n'));
    } else {
      this.logBox.setLabel(' Output — press v for raw log ');
      const workflowLines = renderWorkflowOutput(agent.logs, agent);
      this.logBox.setContent(workflowLines.join('\n'));
    }
    this.logBox.setScrollPerc(100);
  }

  /**
   * Clear log and task header before rendering to prevent stale content
   * from bleeding through when switching between agents.
   */
  _clearAndRenderLog() {
    this.logBox.setContent('');
    this.taskHeader.setContent('');
    this._renderLog();
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
        ? ` | PR: ${escapeTags(agent.prUrl)}`
        : agent.branch ? ` | ${escapeTags(repoPrefix + agent.branch)}` : '';
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
        this._clearAndRenderLog();
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
      this.screen.alloc();
      this.screen.render();
      confirm.ask(
        `${running.length} agent(s) still running. Kill all and quit? (y/n)`,
        (err, value) => {
          if (value === true || value === 'y' || value === 'yes') {
            persistAgents(this.agents);
            this._cleanup();
          } else {
            this.screen.remove(confirm);
            this.screen.alloc();
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
    this._killAllChildProcesses();
    this.screen.destroy();
    process.exit(0);
  }

  /**
   * Kill all running agent child processes and their entire process trees.
   */
  _killAllChildProcesses() {
    for (const agent of this.agents) {
      if (agent.proc) {
        try {
          // Kill the entire process group (negative PID)
          process.kill(-agent.proc.pid, 'SIGKILL');
        } catch {
          try { agent.proc.kill('SIGKILL'); } catch {}
        }
        agent.proc = null;
        agent.state = 'stopped';
      }
    }
    persistAgents(this.agents);
  }

  /**
   * Install signal handlers so child processes are cleaned up
   * when ocha is killed externally (SIGINT, SIGTERM, SIGHUP).
   */
  _installSignalHandlers() {
    const cleanup = (signal) => {
      this._killAllChildProcesses();
      if (this.tickInterval) clearInterval(this.tickInterval);
      try { this.screen.destroy(); } catch {}
      process.exit(signal === 'SIGINT' ? 130 : 143);
    };

    // Override blessed's default C-c handling with our cleanup
    process.on('SIGTERM', () => cleanup('SIGTERM'));
    process.on('SIGHUP', () => cleanup('SIGHUP'));

    // Handle uncaught exceptions and unhandled rejections
    process.on('uncaughtException', (err) => {
      this._killAllChildProcesses();
      process.stderr.write(`[ocha] Fatal: ${err.message}\n`);
      process.exit(1);
    });
  }
}
