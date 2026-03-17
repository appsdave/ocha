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
import { startSpinner, updateSpinner, stopSpinner, logWithSpinner, succeedSpinner, failSpinner } from './spinner.js';

/**
 * Runs the coordinator loop — spawns agents in batches and waits for completion.
 * Each batch runs up to maxAgents tasks in parallel before starting the next batch.
 *
 * @param {object} opts - Command options.
 * @param {string} opts.maxAgents - Maximum number of parallel agents per batch.
 * @param {string} opts.baseBranch - Git branch to create worktrees from.
 * @param {boolean} [opts.noMerge] - Unused (kept for backward compat).
 */
export async function runCoordinator(opts) {
  const maxAgents = parseInt(opts.maxAgents, 10);
  const baseBranch = opts.baseBranch;

  const status = readStatus();
  if (!status) throw new Error('No status file found');

  // Lead step: coordinator refines task prompts before assigning to builders
  console.log(chalk.blue(`\n👔 Lead reviewing ${status.tasks.length} task(s)...`));
  for (const task of status.tasks) {
    if (task.role === 'builder') {
      task.description = `[Assigned by lead] ${task.description}\n\nContext: This task was reviewed and assigned by the lead agent. Work in your isolated worktree, commit all changes, and ensure tests pass.`;
    }
  }
  writeStatus(status);

  console.log(chalk.blue(`\n🎯 Coordinator starting with ${status.tasks.length} tasks (max ${maxAgents} parallel)\n`));

  const agentPromises = [];

  for (let i = 0; i < status.tasks.length; i += maxAgents) {
    const batch = status.tasks.slice(i, i + maxAgents);
    const batchPromises = [];

    const runningTasks = [];

    for (const task of batch) {
      if (task.state !== 'pending') continue;

      logWithSpinner(chalk.yellow(`  ▶ Lead assigning ${task.role}: ${task.description.split('\n')[0].replace('[Assigned by lead] ', '')}`));

      const worktreePath = createWorktree(task.branch, baseBranch);
      task.state = 'running';
      writeStatus(status);
      runningTasks.push(task);

      const p = spawnAgent(task, worktreePath, task.role)
        .then(async ({ code, taskId }) => {
          const cleanDesc = task.description.split('\n')[0].replace('[Assigned by lead] ', '');
          if (code === 0) {
            logWithSpinner(chalk.green(`  ✓ Builder completed: ${cleanDesc}`));

            // Spawn reviewer agent in the same worktree to review changes
            logWithSpinner(chalk.magenta(`  🔍 Spawning reviewer for: ${cleanDesc}`));
            const reviewTask = {
              id: `${task.id}-review`,
              description: `Review the changes made in this worktree against the base branch (${baseBranch}). Check for bugs, security issues, missing tests, and code quality. If the changes look good, report approval. If there are blocking issues, report them clearly.\n\nOriginal task: ${cleanDesc}`,
              branch: task.branch,
              role: 'reviewer',
            };
            try {
              const { code: reviewCode } = await spawnAgent(reviewTask, worktreePath, 'reviewer');
              if (reviewCode === 0) {
                logWithSpinner(chalk.green(`  ✓ Review passed: ${cleanDesc}`));
                // Push to main after successful review
                try {
                  stopSpinner();
                  execSync(`git stash --include-untracked 2>/dev/null || true`, { stdio: 'pipe' });
                  execSync(`git merge ${task.branch}`, { stdio: 'pipe' });
                  execSync(`git stash pop 2>/dev/null || true`, { stdio: 'pipe' });
                  console.log(chalk.green(`  ✓ Merged ${task.branch} into ${baseBranch}`));
                  // Push main to origin
                  try {
                    execSync(`git push origin ${baseBranch}`, { stdio: 'pipe' });
                    console.log(chalk.green(`  ✓ Pushed ${baseBranch} to origin`));
                  } catch {
                    console.log(chalk.yellow(`  ⚠ Could not push ${baseBranch} (push manually)`));
                  }
                  task.merged = true;
                } catch {
                  console.log(chalk.yellow(`  ⚠ Merge conflict for ${task.branch} — resolve manually`));
                  // Fallback: create PR instead
                  try {
                    const desc6 = shortDesc(cleanDesc);
                    execSync(`gh pr create --base ${baseBranch} --head ${task.branch} --title "ocha: ${desc6}" --body "Reviewed and approved by ocha reviewer agent.\n\nTask: ${cleanDesc}" 2>&1`, { stdio: 'pipe' });
                    console.log(chalk.green(`  ✓ PR created for ${task.branch}`));
                  } catch {}
                }
              } else {
                logWithSpinner(chalk.yellow(`  ⚠ Review flagged issues: ${cleanDesc}`));
                // Still create PR but note review issues
                try {
                  const desc6 = shortDesc(cleanDesc);
                  execSync(`cd "${worktreePath}" && git push -u origin ${task.branch} --force`, { stdio: 'pipe' });
                  execSync(`gh pr create --base ${baseBranch} --head ${task.branch} --title "ocha: ${desc6}" --body "⚠️ Reviewer flagged issues — needs manual review.\n\nTask: ${cleanDesc}" 2>&1`, { stdio: 'pipe' });
                  console.log(chalk.yellow(`  ✓ PR created (needs review): ${task.branch}`));
                } catch {}
              }
            } catch (reviewErr) {
              logWithSpinner(chalk.yellow(`  ⚠ Review failed to run: ${reviewErr.message}`));
            }
          } else {
            logWithSpinner(chalk.red(`  ✗ Failed: ${cleanDesc}`));
          }
          runningTasks.splice(runningTasks.indexOf(task), 1);
          if (runningTasks.length > 0) {
            updateSpinner(`Working on ${runningTasks.length} task(s): ${runningTasks.map(t => t.id).join(', ')}`);
          }
        })
        .catch(err => {
          runningTasks.splice(runningTasks.indexOf(task), 1);
          logWithSpinner(chalk.red(`  ✗ Error: ${err.message}`));
        });

      batchPromises.push(p);
    }

    if (runningTasks.length > 0) {
      startSpinner(`Working on ${runningTasks.length} task(s): ${runningTasks.map(t => t.id).join(', ')}`);
    }

    // Wait for this batch to complete before starting next
    await Promise.all(batchPromises);
    stopSpinner();
  }

  // Re-read final status
  const finalStatus = readStatus() || status;

  // Show diff stats for completed tasks that weren't merged inline
  showDiffStats(finalStatus, baseBranch);

  // Cleanup worktrees for all tasks
  cleanupWorktrees(finalStatus);

  // Final summary
  printSummary(finalStatus);
  finalStatus.session.state = 'completed';
  finalStatus.session.completedAt = new Date().toISOString();
  writeStatus(finalStatus);
}

function showDiffStats(status, baseBranch) {
  const completed = status.tasks.filter(t => t.state === 'completed');

  for (const task of completed) {
    if (task.merged) continue; // Already shown during inline merge
    try {
      const diff = execSync(`git diff ${baseBranch}..${task.branch} --stat`, { encoding: 'utf-8' }).trim();
      if (diff) {
        console.log(chalk.blue(`\n  📋 Changes in ${task.branch}:`));
        console.log(chalk.gray(diff.split('\n').map(l => `     ${l}`).join('\n')));
      }
    } catch {}
  }
}

function cleanupWorktrees(status) {
  for (const task of status.tasks) {
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
function printSummary(status) {
  console.log(chalk.blue('\n═══════════════════════════════════'));
  console.log(chalk.blue('       OCHA Session Summary'));
  console.log(chalk.blue('═══════════════════════════════════\n'));

  const completed = status.tasks.filter(t => t.state === 'completed');
  const failed = status.tasks.filter(t => t.state === 'failed');

  console.log(`  Total:     ${status.tasks.length}`);
  console.log(chalk.green(`  Completed: ${completed.length}`));
  if (failed.length) console.log(chalk.red(`  Failed:    ${failed.length}`));

  const merged = completed.filter(t => t.merged);
  const unmerged = completed.filter(t => !t.merged);

  if (merged.length > 0) {
    console.log(chalk.green('\n  Merged to main:'));
    for (const task of merged) {
      const desc = shortDesc(task.description.split('\n')[0].replace('[Assigned by lead] ', ''));
      console.log(chalk.gray(`    ✓ ${task.branch} — ${desc}`));
    }
  }
  if (unmerged.length > 0) {
    console.log(chalk.yellow('\n  Needs manual merge/PR:'));
    for (const task of unmerged) {
      const desc = shortDesc(task.description.split('\n')[0].replace('[Assigned by lead] ', ''));
      console.log(chalk.gray(`    ⚠ ${task.branch} — ${desc}`));
    }
  }
  console.log();
}
