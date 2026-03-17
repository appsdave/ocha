import { rmSync, existsSync } from 'fs';
import chalk from 'chalk';
import { OCHA_DIR, WORKTREES_DIR } from '../lib/paths.js';
import { killAllAgents } from '../lib/agent.js';
import { readStatus, writeStatus } from '../lib/status.js';
import { removeWorktree } from '../lib/worktree.js';

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
      if (task.worktree && existsSync(task.worktree)) {
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

  // Remove worktrees directory
  if (existsSync(WORKTREES_DIR)) {
    rmSync(WORKTREES_DIR, { recursive: true, force: true });
  }

  // Remove .ocha directory
  if (existsSync(OCHA_DIR)) {
    rmSync(OCHA_DIR, { recursive: true, force: true });
    console.log(chalk.green('✓ Session stopped and cleaned up.'));
  } else {
    console.log(chalk.yellow('No active session found.'));
  }
}
