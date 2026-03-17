/**
 * @module coordinator
 * Batched parallel agent coordination.
 * Reads the task list from status, creates worktrees, spawns agents in
 * batches (up to maxAgents at a time), and prints a final summary.
 */
import { spawnAgent } from './agent.js';
import { createWorktree, removeWorktree } from './worktree.js';
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

      console.log(chalk.yellow(`  ▶ Assigning ${task.role}: ${task.description}`));

      const worktreePath = createWorktree(task.branch, baseBranch);
      task.state = 'running';
      writeStatus(status);

      const p = spawnAgent(task, worktreePath, task.role)
        .then(({ code, taskId }) => {
          if (code === 0) {
            console.log(chalk.green(`  ✓ Completed: ${task.description}`));
          } else {
            console.log(chalk.red(`  ✗ Failed: ${task.description}`));
          }
        })
        .catch(err => {
          console.log(chalk.red(`  ✗ Error: ${err.message}`));
        });

      batchPromises.push(p);
    }

    // Wait for this batch to complete before starting next
    await Promise.all(batchPromises);
  }

  // Re-read final status
  const finalStatus = readStatus() || status;

  // Merge completed branches back and cleanup worktrees
  await mergeAndCleanup(finalStatus, baseBranch, opts.noMerge);

  // Final summary
  printSummary(finalStatus, opts.noMerge);
  finalStatus.session.state = 'completed';
  finalStatus.session.completedAt = new Date().toISOString();
  writeStatus(finalStatus);
}

async function mergeAndCleanup(status, baseBranch, noMerge) {
  const completed = status.tasks.filter(t => t.state === 'completed');

  for (const task of completed) {
    // Show diff stats
    try {
      const diff = execSync(`git diff ${baseBranch}..${task.branch} --stat`, { encoding: 'utf-8' }).trim();
      if (diff) {
        console.log(chalk.blue(`\n  📋 Changes in ${task.branch}:`));
        console.log(chalk.gray(diff.split('\n').map(l => `     ${l}`).join('\n')));
      }
    } catch {}

    // Merge branch back into base
    if (!noMerge) {
      try {
        // Stash any uncommitted local changes to avoid conflicts
        let stashed = false;
        try {
          const stashOut = execSync('git stash --include-untracked', { encoding: 'utf-8' }).trim();
          stashed = !stashOut.includes('No local changes');
        } catch {}

        try {
          execSync(`git merge ${task.branch} -m "ocha: merge ${task.branch}"`, { stdio: 'pipe' });
          console.log(chalk.green(`  ✓ Merged ${task.branch} into ${baseBranch}`));
        } catch {
          // Merge conflict — abort and try with theirs strategy
          try { execSync('git merge --abort', { stdio: 'pipe' }); } catch {}
          try {
            execSync(`git merge -X theirs ${task.branch} -m "ocha: merge ${task.branch}"`, { stdio: 'pipe' });
            console.log(chalk.green(`  ✓ Merged ${task.branch} into ${baseBranch} (auto-resolved)`));
          } catch {
            try { execSync('git merge --abort', { stdio: 'pipe' }); } catch {}
            console.log(chalk.red(`  ✗ Merge conflict for ${task.branch} — resolve manually:`));
            console.log(chalk.gray(`     git merge ${task.branch}`));
          }
        }

        // Restore stashed changes
        if (stashed) {
          try { execSync('git stash pop', { stdio: 'pipe' }); } catch {
            console.log(chalk.yellow(`  ⚠ Stashed changes could not be auto-restored: git stash pop`));
          }
        }
      } catch {
        console.log(chalk.red(`  ✗ Merge failed for ${task.branch}`));
      }
    }

    // Cleanup worktree
    if (task.worktree) {
      try {
        removeWorktree(task.worktree);
      } catch {}
    }

    // Cleanup branch if merged
    if (!noMerge) {
      try {
        execSync(`git branch -D ${task.branch}`, { stdio: 'pipe' });
      } catch {}
    }
  }

  // Also cleanup worktrees for failed tasks
  const failed = status.tasks.filter(t => t.state === 'failed');
  for (const task of failed) {
    if (task.worktree) {
      try { removeWorktree(task.worktree); } catch {}
    }
  }
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
 * @param {boolean} noMerge - Whether auto-merge was skipped.
 */
function printSummary(status, noMerge) {
  console.log(chalk.blue('\n═══════════════════════════════════'));
  console.log(chalk.blue('       OCHA Session Summary'));
  console.log(chalk.blue('═══════════════════════════════════\n'));

  const completed = status.tasks.filter(t => t.state === 'completed');
  const failed = status.tasks.filter(t => t.state === 'failed');

  console.log(`  Total:     ${status.tasks.length}`);
  console.log(chalk.green(`  Completed: ${completed.length}`));
  if (failed.length) console.log(chalk.red(`  Failed:    ${failed.length}`));

  if (completed.length > 0 && noMerge) {
    console.log(chalk.yellow('\n  Branches (not merged):'));
    for (const task of completed) {
      const desc = shortDesc(task.description);
      console.log(chalk.gray(`    git merge ${task.branch}  # ${desc}`));
    }
  } else if (completed.length > 0) {
    console.log(chalk.green('\n  All completed branches merged into ' + status.tasks[0]?.branch?.split('/')[0] || 'main'));
  }
  console.log();
}
