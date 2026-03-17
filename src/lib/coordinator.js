/**
 * @module coordinator
 * Batched parallel agent coordination.
 * Reads the task list from status, creates worktrees, spawns agents in
 * batches (up to maxAgents at a time), and prints a final summary.
 */
import { spawnAgent } from './agent.js';
import { createWorktree } from './worktree.js';
import { readStatus, writeStatus } from './status.js';
import { execSync } from 'child_process';
import chalk from 'chalk';

/**
 * Runs the coordinator loop — spawns agents in batches and waits for completion.
 * Each batch runs up to maxAgents tasks in parallel before starting the next batch.
 *
 * @param {object} opts - Command options.
 * @param {string} opts.maxAgents - Maximum number of parallel agents per batch.
 * @param {string} opts.baseBranch - Git branch to create worktrees from.
 */
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

/**
 * Truncates a description to its first 6 words for display.
 * @param {string} description - Full task description.
 * @returns {string} Shortened description with ellipsis if truncated.
 */
function shortDesc(description) {
  const words = description.split(/\s+/);
  return words.slice(0, 6).join(' ') + (words.length > 6 ? '…' : '');
}

/**
 * Prints the session summary with task counts and merge commands.
 * @param {object} status - The final session status object.
 */
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
    console.log(chalk.blue('\n  Pull Requests:'));
    for (const task of completed) {
      const desc = shortDesc(task.description);
      try {
        const prUrl = execSync(
          `gh pr create --base main --head ${task.branch} --title "${desc}" --body "Auto-created by ocha for: ${task.description.replace(/"/g, '\\"')}" 2>&1`,
          { encoding: 'utf-8', stdio: 'pipe' }
        ).trim();
        console.log(chalk.green(`    ✓ PR created: ${prUrl}`));
      } catch (err) {
        const msg = err.stdout || err.stderr || '';
        if (msg.includes('already exists')) {
          console.log(chalk.yellow(`    ⚠ PR already exists for ${task.branch}`));
        } else {
          console.log(chalk.yellow(`    ⚠ Could not create PR for ${task.branch}: ${msg.split('\n')[0]}`));
          console.log(chalk.gray(`      Manual: git merge ${task.branch}  # ${desc}`));
        }
      }
    }
  }
  console.log();
}
