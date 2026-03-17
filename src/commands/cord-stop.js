import { rmSync, existsSync } from 'fs';
import chalk from 'chalk';
import { OCHA_DIR, WORKTREES_DIR } from '../lib/paths.js';
import { killAllAgents } from '../lib/agent.js';
import { readStatus } from '../lib/status.js';
import { removeWorktree } from '../lib/worktree.js';

export function cordStop() {
  console.log(chalk.blue('🛑 Stopping ocha session...'));

  // Kill running agents
  killAllAgents();

  // Clean up worktrees
  const status = readStatus();
  if (status) {
    for (const task of status.tasks) {
      if (task.worktree && existsSync(task.worktree)) {
        try {
          removeWorktree(task.worktree);
          console.log(chalk.gray(`  Removed worktree: ${task.worktree}`));
        } catch {
          console.log(chalk.yellow(`  Could not remove worktree: ${task.worktree}`));
        }
      }
    }
  }

  // Remove worktrees directory
  if (existsSync(WORKTREES_DIR)) {
    rmSync(WORKTREES_DIR, { recursive: true, force: true });
  }

  // Remove .ocha directory
  if (existsSync(OCHA_DIR)) {
    rmSync(OCHA_DIR, { recursive: true, force: true });
    console.log(chalk.green('✓ Session cleaned up.'));
  } else {
    console.log(chalk.yellow('No active session found.'));
  }
}
