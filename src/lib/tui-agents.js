/**
 * @module tui-agents
 * Agent lifecycle management for the TUI: spawn, kill, persist, reload.
 */
import { spawn } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { resolve, dirname, basename } from 'path';
import { fileURLToPath } from 'url';
import { readStatus, writeStatus } from './status.js';
import { OCHA_DIR, STATUS_FILE } from './paths.js';
import { formatCompletionSummary } from './tui-utils.js';
import { stripAnsi } from './ui.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
export const OCHA_ROOT = resolve(__dirname, '../..');

/**
 * Load previously persisted agents from .ocha/status.json.
 * Running agents are marked as stopped (they can't be resumed).
 * @returns {object[]} Array of agent objects.
 */
export function loadPersistedAgents() {
  const agents = [];
  try {
    if (existsSync(STATUS_FILE)) {
      const status = readStatus();
      if (status && status.tasks) {
        for (const t of status.tasks) {
          agents.push({
            id: t.id,
            task: t.displayTask || t.branch,
            branch: t.branch,
            repo: t.repo || null,
            state: t.state === 'running' ? 'stopped' : t.state,
            startedAt: t.startedAt,
            completedAt: t.completedAt,
            logs: t.logs || [],
            proc: null,
          });
        }
      }
    }
  } catch (_) {}
  return agents;
}

/**
 * Persist current agent list to .ocha/status.json.
 * @param {object[]} agents
 */
export function persistAgents(agents) {
  try {
    if (!existsSync(OCHA_DIR)) mkdirSync(OCHA_DIR, { recursive: true });
    const existing = readStatus() || {
      session: { task: 'ocha tui', startedAt: new Date().toISOString(), state: 'running' },
      tasks: [],
    };
    existing.tasks = agents.map(a => ({
      id: a.id,
      displayTask: a.task,
      branch: a.branch,
      repo: a.repo || null,
      state: a.state,
      startedAt: a.startedAt,
      completedAt: a.completedAt,
      logs: a.logs.slice(-200),
    }));
    writeStatus(existing);
  } catch (_) {}
}

/**
 * Spawn a new agent process for the given task.
 * Returns the agent object (already pushed into the agents array).
 *
 * @param {string} task - Human-readable task description.
 * @param {object[]} agents - Shared agents array (mutated in place).
 * @param {Function} onUpdate - Called whenever logs or state change.
 * @returns {object} The new agent object.
 */
export function spawnAgent(task, agents, onUpdate) {
  const now = new Date();
  const repo = basename(process.cwd());
  const id = `agent-${Date.now()}`;

  const agent = {
    id,
    task,
    branch: null,
    repo,
    state: 'running',
    startedAt: now.toISOString(),
    completedAt: null,
    logs: [
      `[ocha] Repo   : ${repo}`,
      '[ocha] Branch : (model will assign)',
      `[ocha] Started: ${now.toLocaleString()}`,
      '',
    ],
    proc: null,
  };

  agents.push(agent);

  const proc = spawn(process.execPath, [
    resolve(OCHA_ROOT, 'bin/ocha.js'),
    '--tui-agent',
    '--task', task,
  ], {
    cwd: process.cwd(),
    env: { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  agent.proc = proc;

  const appendLine = (line) => {
    if (!line) return;
    agent.logs.push(stripAnsi(line));
    if (agent.logs.length > 2000) agent.logs.shift();
    onUpdate(agent);
  };

  proc.stdout.on('data', (chunk) => {
    for (const line of chunk.toString().split('\n')) {
      // Skip lines that are only ANSI escape sequences (no readable content)
      const stripped = line.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '').trim();
      if (!stripped && line.includes('\x1B')) continue;
      appendLine(line);
    }
  });

  proc.stderr.on('data', (chunk) => {
    for (const line of chunk.toString().split('\n')) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      // Skip lines that are only ANSI escape sequences (no readable content)
      const stripped = trimmed.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '').trim();
      if (!stripped) continue;
      appendLine(`[err] ${line}`);
    }
  });

  proc.on('close', (code) => {
    agent.proc = null;
    agent.state = code === 0 ? 'completed' : 'failed';
    agent.completedAt = new Date().toISOString();
    // Extract PR URL from logs if present
    for (const line of agent.logs) {
      const m = line.match(/https:\/\/github\.com\/[^\s]+\/pull\/\d+/);
      if (m) { agent.prUrl = m[0]; break; }
    }
    // Append clean summary block
    for (const line of formatCompletionSummary(agent)) {
      agent.logs.push(line);
    }
    persistAgents(agents);
    onUpdate(agent);
  });

  return agent;
}

/**
 * Kill the agent at the given index.
 * @param {object[]} agents
 * @param {number} idx
 */
export function killAgent(agents, idx) {
  const agent = agents[idx];
  if (!agent) return;
  if (agent.proc) {
    agent.proc.kill('SIGTERM');
    agent.state = 'stopped';
    agent.logs.push('[ocha] Agent killed by user');
  }
}
