import { spawnAgent } from './agent.js';
import { createWorktree } from './worktree.js';
import { readStatus, writeStatus } from './status.js';
import chalk from 'chalk';

export async function runCoordinator(opts) {
  const maxAgents = parseInt(opts.maxAgents, 10);
  const baseBranch = opts.baseBranch;

  const status = readStatus();
  if (!status) throw new Error('No status file found');

  const pending = () => status.tasks.filter(t => t.state === 'pending');
  const running = () => status.tasks.filter(t => t.state === 'running');

  console.log(chalk.blue(`\n🎯 Coordinator starting with ${status.tasks.length} tasks (max ${maxAgents} parallel)\n`));

  while (pending().length > 0 || running().length > 0) {
    // Launch agents up to max concurrency
    while (pending().length > 0 && running().length < maxAgents) {
      const task = pending()[0];
      console.log(chalk.yellow(`▶ Spawning ${task.role} agent for ${task.id}: ${task.description}`));

      const worktreePath = createWorktree(task.branch, baseBranch);
      task.state = 'running';
      writeStatus(status);

      spawnAgent(task, worktreePath, task.role)
        .then(({ code, taskId }) => {
          if (code === 0) {
            console.log(chalk.green(`✓ ${taskId} completed successfully`));
          } else {
            console.log(chalk.red(`✗ ${taskId} failed with exit code ${code}`));
          }
        })
        .catch(err => {
          console.log(chalk.red(`✗ ${task.id} error: ${err.message}`));
        });

      // Small delay to avoid race conditions on status file
      await sleep(1000);
    }

    // Poll until a slot opens or all done
    await sleep(3000);

    // Re-read status from disk (agents update it)
    const fresh = readStatus();
    if (fresh) {
      status.tasks = fresh.tasks;
    }
  }

  // Final summary
  printSummary(status);
  status.session.state = 'completed';
  status.session.completedAt = new Date().toISOString();
  writeStatus(status);
}

function printSummary(status) {
  console.log(chalk.blue('\n═══════════════════════════════════'));
  console.log(chalk.blue('       OCHA Session Summary'));
  console.log(chalk.blue('═══════════════════════════════════\n'));

  const completed = status.tasks.filter(t => t.state === 'completed');
  const failed = status.tasks.filter(t => t.state === 'failed');

  console.log(`Total tasks: ${status.tasks.length}`);
  console.log(chalk.green(`Completed:   ${completed.length}`));
  if (failed.length) console.log(chalk.red(`Failed:      ${failed.length}`));

  console.log('\nBranches created:');
  for (const task of status.tasks) {
    const icon = task.state === 'completed' ? '✓' : '✗';
    const color = task.state === 'completed' ? chalk.green : chalk.red;
    console.log(color(`  ${icon} ${task.branch} — ${task.description}`));
  }

  if (completed.length > 0) {
    console.log(chalk.blue('\nTo merge branches back into main:'));
    for (const task of completed) {
      console.log(`  git merge ${task.branch}`);
    }
  }
  console.log();
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
