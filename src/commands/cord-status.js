/**
 * @module commands/cord-status
 * Implements the `ocha cord status` command.
 * Reads and displays the current session status and all task states.
 * Supports --watch flag for live polling every 3 seconds.
 */
import chalk from 'chalk';
import { readStatus } from '../lib/status.js';
import { getTerminalWidth, wrapText, drawBox, progressBar, badge } from '../lib/ui.js';

const stateIcon = {
  pending:   '⏳',
  running:   '🔄',
  completed: '✅',
  failed:    '❌',
  stopped:   '🛑',
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

  // Session info box
  const sessionRows = [
    [chalk.dim('Task   '), status.session.task],
    [chalk.dim('State  '), badge(status.session.state)],
    [chalk.dim('Started'), formatDate(status.session.startedAt)],
  ];
  if (status.session.completedAt) {
    sessionRows.push([chalk.dim('Ended  '), formatDate(status.session.completedAt)]);
  }
  drawBox('📊  ocha session status', sessionRows, { maxWidth: 78 });

  // Task summary counts + progress bar
  const counts = { completed: 0, running: 0, failed: 0, pending: 0 };
  for (const task of status.tasks) counts[task.state] = (counts[task.state] || 0) + 1;
  const total = status.tasks.length;
  const done  = counts.completed;

  const countParts = [
    counts.completed ? chalk.green(`${counts.completed} completed`) : null,
    counts.running   ? chalk.yellow(`${counts.running} running`)    : null,
    counts.failed    ? chalk.red(`${counts.failed} failed`)         : null,
    counts.pending   ? chalk.gray(`${counts.pending} pending`)      : null,
  ].filter(Boolean);

  console.log('\n  ' + progressBar(done, total, 24) + '   ' + countParts.join(chalk.dim('  ·  ')));
  console.log(chalk.dim('  ' + '─'.repeat(Math.max(40, Math.min(getTerminalWidth() - 4, 76)))));

  // Individual task rows
  const termWidth  = getTerminalWidth();
  const descIndent = '        '; // 8 spaces — aligns under icon + badge
  const descWidth  = Math.max(20, termWidth - descIndent.length - 2);

  for (const task of status.tasks) {
    const icon     = stateIcon[task.state] || '?';
    const rawDesc  = task.description.split('\n')[0];
    const descLines = wrapText(rawDesc, descWidth);

    console.log(`\n  ${icon}  ${badge(task.state)}  ${chalk.bold(task.id)}  ${chalk.dim(`[${task.role}]`)}`);
    for (const dLine of descLines) {
      console.log(chalk.gray(`${descIndent}${dLine}`));
    }
    console.log(chalk.dim(`${descIndent}branch: ${task.branch}`));
    if (task.worktree) console.log(chalk.dim(`${descIndent}worktree: ${task.worktree}`));
    if (task.prUrl)    console.log(chalk.cyan(`${descIndent}🔗 pr: ${task.prUrl}`));
    if (task.merged)   console.log(chalk.green(`${descIndent}✓ merged`));
  }
  console.log();

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

  // Redraw immediately when the terminal is resized.
  process.on('SIGWINCH', draw);

  process.on('SIGINT', () => {
    clearInterval(interval);
    process.stdout.write('\x1B[?25h');
    process.exit(0);
  });
}
