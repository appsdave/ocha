/**
 * @module commands/cord-start
 * Implements the `ocha cord start` command.
 * Decomposes a high-level task, creates the session status, and launches
 * the coordinator loop to spawn parallel agents.
 */
import chalk from 'chalk';
import { execSync } from 'node:child_process';
import { ensureDir, pathExists } from '../lib/files.js';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { createInitialStatus, writeStatus } from '../lib/status.js';
import { decomposeTask } from '../lib/decompose.js';
import { runCoordinator } from '../lib/coordinator.js';
import { installRolePrompts } from '../lib/roles.js';
import { ensureAuthenticated } from '../lib/agent.js';

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
  // Support comma-separated multiple tasks
  const taskList = opts.task.split(',').map(t => t.trim()).filter(Boolean);

  console.log(chalk.blue('🚀 ocha cord start'));
  console.log(chalk.gray(`   Task${taskList.length > 1 ? 's' : ''}: ${taskList.join(', ')}`));
  console.log(chalk.gray(`   Base: ${opts.baseBranch}`));

  // Auto-init if needed
  if (!pathExists(OCHA_DIR)) {
    ensureDir(OCHA_DIR);
    ensureDir(ROLES_DIR);
    installRolePrompts();
    console.log(chalk.gray('   Initialized .ocha/'));
  }

  // Check git repo is set up properly for worktrees
  console.log(chalk.blue('\n🔍 Checking git setup...'));
  try {
    execSync('git rev-parse --is-inside-work-tree', { stdio: 'pipe' });
  } catch {
    console.log(chalk.red('   ✗ Not a git repository'));
    console.log(chalk.yellow('\n   To fix this, run:'));
    console.log(chalk.white('     git init'));
    console.log(chalk.white('     git add .'));
    console.log(chalk.white('     git commit -m "initial commit"'));
    console.log(chalk.yellow('\n   Then add a remote (optional but recommended):'));
    console.log(chalk.white('     git remote add origin git@github.com:user/repo.git'));
    console.log(chalk.white('     git branch -M main'));
    console.log(chalk.white('     git push -u origin main'));
    process.exit(1);
  }

  // Check that the base branch exists
  try {
    execSync(`git rev-parse --verify ${opts.baseBranch}`, { stdio: 'pipe' });
  } catch {
    console.log(chalk.red(`   ✗ Branch "${opts.baseBranch}" does not exist`));
    console.log(chalk.yellow(`\n   Make sure you have at least one commit on "${opts.baseBranch}":`));
    console.log(chalk.white('     git add .'));
    console.log(chalk.white(`     git commit -m "initial commit"`));
    process.exit(1);
  }
  console.log(chalk.green('   ✓ Git repository ready'));

  // Ensure authentication is valid before doing anything
  console.log(chalk.blue('\n🔐 Checking authentication...'));
  try {
    await ensureAuthenticated();
    console.log(chalk.green('   ✓ Authenticated successfully'));
  } catch (err) {
    console.log(chalk.red(`   ✗ Authentication failed: ${err.message}`));
    console.log(chalk.yellow('   Run "junie" manually to log in first.'));
    process.exit(1);
  }

  // Decompose each task into subtasks (analysis only, no code changes)
  console.log(chalk.blue('\n📋 Decomposing task into subtasks...'));
  let allTasks = [];
  for (const taskItem of taskList) {
    const subtasks = await decomposeTask(taskItem);
    allTasks.push(...subtasks);
  }
  console.log(chalk.green(`   Found ${allTasks.length} subtask(s)`));
  for (const t of allTasks) {
    console.log(chalk.gray(`     └─ [${t.role}] ${t.description}`));
  }
  const tasks = allTasks;

  // Create initial status
  const status = createInitialStatus(opts.task, tasks);
  writeStatus(status);

  // Run the coordinator loop (only spawns agents, doesn't do work itself)
  await runCoordinator({ ...opts, noMerge: opts.merge === false });
}
