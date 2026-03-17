import { spawnAgent } from './agent.js';
import { createWorktree } from './worktree.js';
import { readStatus, writeStatus } from './status.js';
import chalk from 'chalk';

export async function runCoordinator(opts) {
  const maxAgents = parseInt(opts.maxAgents, 10);
  const baseBranch = opts.baseBranch;

  const status = readStatus();
  if (!status) throw new Error('No status file found');

  console.log(chalk.blue(`\n🎯 Coordinator starting with ${status.tasks.length} tasks (max ${maxAgents} parallel)\n`));

  const agentPromises = [];

  for (let i = 0; i < status.tasks.length; i += maxAgents) {
    const batch = status.tasks.slice(i, i + maxAgents);
    const batchPromises = [];

    for (const task of batch) {
      if (task.state !== 'pending') continue;

      console.log(chalk.yellow(`  ▶ [${task.id}] Spawning ${task.role}: ${task.description}`));

      const worktreePath = createWorktree(task.branch, baseBranch);
      task.state = 'running';
      writeStatus(status);

      const p = spawnAgent(task, worktreePath, task.role)
        .then(({ code, taskId }) => {
          if (code === 0) {
            console.log(chalk.green(`  ✓ [${taskId}] Done`));
          } else {
            console.log(chalk.red(`  ✗ [${taskId}] Failed (exit ${code})`));
          }
        })
        .catch(err => {
          console.log(chalk.red(`  ✗ [${task.id}] Error: ${err.message}`));
        });

      batchPromises.push(p);
    }

    // Wait for this batch to complete before starting next
    await Promise.all(batchPromises);
  }

  // Re-read final status
  const finalStatus = readStatus() || status;

  // Final summary
  printSummary(finalStatus);
  finalStatus.session.state = 'completed';
  finalStatus.session.completedAt = new Date().toISOString();
  writeStatus(finalStatus);
}

function shortDesc(description) {
  const words = description.split(/\s+/);
  return words.slice(0, 6).join(' ') + (words.length > 6 ? '…' : '');
}

function printSummary(status) {
  console.log(chalk.blue('\n═══════════════════════════════════'));
  console.log(chalk.blue('       OCHA Session Summary'));
  console.log(chalk.blue('═══════════════════════════════════\n'));

  const completed = status.tasks.filter(t => t.state === 'completed');
  const failed = status.tasks.filter(t => t.state === 'failed');

  console.log(`  Total:     ${status.tasks.length}`);
  console.log(chalk.green(`  Completed: ${completed.length}`));
  if (failed.length) console.log(chalk.red(`  Failed:    ${failed.length}`));

  if (completed.length > 0) {
    console.log(chalk.blue('\n  To merge branches back into main:'));
    for (const task of completed) {
      const desc = shortDesc(task.description);
      console.log(chalk.gray(`    git merge ${task.branch}`) + chalk.white(`  # ${desc}`));
    }
  }
  console.log();
}
