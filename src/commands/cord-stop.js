/**
 * @module commands/cord-stop
 * Implements the `ocha cord stop` command.
 * Stops all running agents, removes worktrees, and cleans up the .ocha/ directory.
 */
import chalk from 'chalk';
import { pathExists, safeDelete } from '../lib/files.js';
import { OCHA_DIR, WORKTREES_DIR } from '../lib/paths.js';
import { killAllAgents } from '../lib/agent.js';
import { readStatus, writeStatus } from '../lib/status.js';
import { removeWorktree } from '../lib/worktree.js';

/**
 * Stops the ocha session: kills agent processes, removes worktrees,
 * and deletes the .ocha/ and .ocha-worktrees/ directories.
 * Safe to call from a different process than the one that started the session.
 */
export function cordStop() {
  console.log(chalk.blue('🛑 Stopping ocha session...'));

  // Kill in-memory agents (if called from same process)
  killAllAgents();

  // Also kill agents by PID from status file (if called from different process)
  const status = readStatus();
  if (status) {
    for (const task of status.tasks) {
      if (task.state === 'running' && task.pid) {
        try {
          process.kill(task.pid, 'SIGTERM');
          console.log(chalk.gray(`  Killed agent PID ${task.pid} (${task.id})`));
        } catch {
          // Already dead
        }
        task.state = 'stopped';
      }
    }

    // Clean up worktrees
    for (const task of status.tasks) {
      if (task.worktree && pathExists(task.worktree)) {
        try {
          removeWorktree(task.worktree);
          console.log(chalk.gray(`  Removed worktree: ${task.branch}`));
        } catch {
          console.log(chalk.yellow(`  Could not remove worktree: ${task.branch}`));
        }
      }
    }

    // Mark session as stopped
    status.session.state = 'stopped';
    status.session.stoppedAt = new Date().toISOString();
    writeStatus(status);
  }

  // Remove worktrees directory (temp working dirs only, not .ocha/)
  safeDelete(WORKTREES_DIR, { recursive: true });

  console.log(chalk.green('✓ Session stopped. Run "ocha cord status" to review, or "ocha init" to start fresh.'));
}
