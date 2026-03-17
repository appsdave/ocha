/**
 * @module commands/cord-start
 * Implements the `ocha cord start` command.
 * Decomposes a high-level task, creates the session status, and launches
 * the coordinator loop to spawn parallel agents.
 */
import { mkdirSync, existsSync } from 'fs';
import chalk from 'chalk';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { createInitialStatus, writeStatus } from '../lib/status.js';
import { decomposeTask } from '../lib/decompose.js';
import { runCoordinator } from '../lib/coordinator.js';
import { installRolePrompts } from '../lib/roles.js';

/**
 * Starts a coordinator session: decomposes the task, creates status, and runs agents.
 * Auto-initializes .ocha/ if it doesn't exist.
 *
 * @param {object} opts - Command options from commander.
 * @param {string} opts.task - High-level task description.
 * @param {string} opts.baseBranch - Base git branch for worktrees.
 * @param {string} opts.maxAgents - Maximum parallel agents.
 */
export async function cordStart(opts) {
  console.log(chalk.blue('🚀 ocha cord start'));
  console.log(chalk.gray(`   Task: ${opts.task}`));
  console.log(chalk.gray(`   Base: ${opts.baseBranch}`));

  // Auto-init if needed
  if (!existsSync(OCHA_DIR)) {
    mkdirSync(OCHA_DIR, { recursive: true });
    mkdirSync(ROLES_DIR, { recursive: true });
    installRolePrompts();
    console.log(chalk.gray('   Initialized .ocha/'));
  }

  // Decompose the task into subtasks (analysis only, no code changes)
  console.log(chalk.blue('\n📋 Decomposing task into subtasks...'));
  const tasks = await decomposeTask(opts.task);
  console.log(chalk.green(`   Found ${tasks.length} subtask(s)`));
  for (const t of tasks) {
    console.log(chalk.gray(`     └─ [${t.role}] ${t.description}`));
  }

  // Create initial status
  const status = createInitialStatus(opts.task, tasks);
  writeStatus(status);

  // Run the coordinator loop (only spawns agents, doesn't do work itself)
  await runCoordinator(opts);
}
