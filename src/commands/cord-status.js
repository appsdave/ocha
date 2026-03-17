/**
 * @module commands/cord-status
 * Implements the `ocha cord status` command.
 * Reads and displays the current session status and all task states.
 * Supports --watch flag for live polling every 3 seconds.
 */
import chalk from 'chalk';
import { readStatus } from '../lib/status.js';

const stateIcon = { pending: '⏳', running: '🔄', completed: '✅', failed: '❌', stopped: '🛑' };

function printStatus() {
  const status = readStatus();
  if (!status) {
    console.log(chalk.yellow('No active ocha session. Run "ocha cord start" first.'));
    return false;
  }

  console.log(chalk.blue('\n📊 OCHA Session Status\n'));
  console.log(`Task:    ${status.session.task}`);
  console.log(`State:   ${status.session.state}`);
  console.log(`Started: ${status.session.startedAt}`);
  if (status.session.completedAt) console.log(`Ended:   ${status.session.completedAt}`);
  console.log();

  for (const task of status.tasks) {
    const icon = stateIcon[task.state] || '?';
    console.log(`  ${icon} ${task.id} [${task.role}] ${task.state}`);
    console.log(chalk.gray(`     ${task.description.split('\n')[0]}`));
    console.log(chalk.gray(`     branch: ${task.branch}`));
    if (task.worktree) console.log(chalk.gray(`     worktree: ${task.worktree}`));
    if (task.merged) console.log(chalk.green(`     ✓ merged`));
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
