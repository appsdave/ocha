/**
 * @module commands/cord-status
 * Implements the `ocha cord status` command.
 * Reads and displays the current session status and all task states.
 * Supports --watch flag for live polling every 3 seconds.
 */
import chalk from 'chalk';
import { readStatus } from '../lib/status.js';

const stateIcon = {
  pending:   '⏳',
  running:   '🔄',
  completed: '✅',
  failed:    '❌',
  stopped:   '🛑',
};

const stateColor = {
  pending:   chalk.gray,
  running:   chalk.yellow,
  completed: chalk.green,
  failed:    chalk.red,
  stopped:   chalk.gray,
};

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

function printStatus() {
  const status = readStatus();
  if (!status) {
    console.log(chalk.yellow('⚠  No active ocha session. Run "ocha cord start" first.'));
    return false;
  }

  const sessionColor = stateColor[status.session.state] || chalk.white;
  const divider = chalk.blue('─'.repeat(50));

  console.log(chalk.bold.blue('\n┌─ 📊  ocha session status ──────────────────────┐'));
  console.log(`│  ${chalk.dim('Task   ')} ${status.session.task.slice(0, 42)}`);
  console.log(`│  ${chalk.dim('State  ')} ${sessionColor(status.session.state)}`);
  console.log(`│  ${chalk.dim('Started')} ${formatDate(status.session.startedAt)}`);
  if (status.session.completedAt) {
    console.log(`│  ${chalk.dim('Ended  ')} ${formatDate(status.session.completedAt)}`);
  }
  console.log(chalk.bold.blue('└' + '─'.repeat(49) + '┘\n'));

  const counts = { completed: 0, running: 0, failed: 0, pending: 0 };
  for (const task of status.tasks) counts[task.state] = (counts[task.state] || 0) + 1;

  const countParts = [
    counts.completed ? chalk.green(`${counts.completed} completed`) : null,
    counts.running   ? chalk.yellow(`${counts.running} running`)   : null,
    counts.failed    ? chalk.red(`${counts.failed} failed`)        : null,
    counts.pending   ? chalk.gray(`${counts.pending} pending`)     : null,
  ].filter(Boolean);
  console.log('  ' + countParts.join(chalk.dim('  ·  ')) + '\n');

  for (const task of status.tasks) {
    const icon = stateIcon[task.state] || '?';
    const colorState = (stateColor[task.state] || chalk.white)(task.state.padEnd(9));
    const desc = task.description.split('\n')[0].slice(0, 60);
    console.log(`  ${icon}  ${colorState} ${chalk.bold(task.id)} ${chalk.dim(`[${task.role}]`)}`);
    console.log(chalk.gray(`       ${desc}`));
    console.log(chalk.dim(`       branch: ${task.branch}`));
    if (task.worktree) console.log(chalk.dim(`       worktree: ${task.worktree}`));
    if (task.prUrl)   console.log(chalk.cyan(`       pr: ${task.prUrl}`));
    if (task.merged)  console.log(chalk.green(`       ✓ merged`));
    console.log();
  }

  return status.session.state === 'running';
}

/**
 * Displays the current session status including task states, branches, and worktree paths.
 * With --watch, polls every 3 seconds until the session completes or is stopped.
 *
 * @param {object} [opts]
 * @param {boolean} [opts.watch] - If true, poll continuously until session ends.
 */
export function cordStatus(opts = {}) {
  if (!opts.watch) {
    printStatus();
    return;
  }

  // Watch mode — clear screen and redraw every 3 seconds
  process.stdout.write('\x1B[?25l'); // hide cursor

  function draw() {
    process.stdout.write('\x1B[2J\x1B[H'); // clear screen
    return printStatus();
  }

  if (!draw()) {
    process.stdout.write('\x1B[?25h');
    return;
  }

  const interval = setInterval(() => {
    if (!draw()) {
      clearInterval(interval);
      process.stdout.write('\x1B[?25h');
    }
  }, 3000);

  process.on('SIGINT', () => {
    clearInterval(interval);
    process.stdout.write('\x1B[?25h');
    process.exit(0);
  });
}
