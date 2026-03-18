/**
 * @module commands/cord-start
 * Implements the `ocha cord start` command.
 * Validates the environment then hands off to runCoordinator() which handles
 * the full pipeline: enhance → lead → builders → reviewers.
 */
import chalk from 'chalk';
import { execSync } from 'node:child_process';
import { resolve } from 'node:path';
import { ensureDir, pathExists } from '../lib/files.js';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { runCoordinator } from '../lib/coordinator.js';
import { installRolePrompts } from '../lib/roles.js';
import { ensureAuthenticated } from '../lib/agent.js';

/**
 * Starts a coordinator session.
 * Auto-initializes .ocha/ if it doesn't exist, validates git + auth,
 * then delegates to runCoordinator() for the full enhance→lead→build→review pipeline.
 *
 * @param {object} opts - Command options from commander.
 * @param {string} opts.task        - High-level task description.
 * @param {string} opts.baseBranch  - Base git branch for worktrees.
 * @param {string} opts.maxAgents   - Maximum parallel agents.
 */
export async function cordStart(opts) {
  const task = opts.task.trim();

  const maxAgentsLabel = parseInt(opts.maxAgents, 10) === 1 ? '1 agent' : `${opts.maxAgents} agents (parallel)`;
  console.log(chalk.bold.blue('┌─ 🚀  ocha cord start ──────────────────────────┐'));
  console.log(`│  ${chalk.dim('Task  ')} ${task.slice(0, 43)}`);
  console.log(`│  ${chalk.dim('Branch')} ${opts.baseBranch}`);
  console.log(`│  ${chalk.dim('Agents')} ${maxAgentsLabel}`);
  console.log(chalk.bold.blue('└' + '─'.repeat(49) + '┘'));

  // Auto-init if needed
  if (!pathExists(OCHA_DIR)) {
    ensureDir(OCHA_DIR);
    ensureDir(ROLES_DIR);
    installRolePrompts();
    console.log(chalk.gray('   Initialized .ocha/'));
  }

  // Check git repo
  console.log(chalk.blue('\n  🔍 Checking prerequisites…'));
  try {
    execSync('git rev-parse --is-inside-work-tree', { stdio: 'pipe' });
  } catch {
    console.log(chalk.red('  ✗ Not a git repository'));
    console.log(chalk.yellow('\n  To fix this, run:'));
    console.log(chalk.white('    git init && git add . && git commit -m "initial commit"'));
    process.exit(1);
  }

  // Check base branch exists
  try {
    execSync(`git rev-parse --verify ${opts.baseBranch}`, { stdio: 'pipe' });
  } catch {
    console.log(chalk.red(`  ✗ Branch "${opts.baseBranch}" does not exist`));
    console.log(chalk.yellow(`\n  Make sure you have at least one commit on "${opts.baseBranch}":`));
    console.log(chalk.white('    git add . && git commit -m "initial commit"'));
    process.exit(1);
  }
  console.log(chalk.green('  ✓ git repository ready'));

  // Ensure Junie is authenticated
  try {
    await ensureAuthenticated();
    console.log(chalk.green('  ✓ authenticated'));
  } catch (err) {
    console.log(chalk.red(`  ✗ Authentication failed: ${err.message}`));
    console.log(chalk.yellow('  Run "junie" manually to log in first.'));
    process.exit(1);
  }
  console.log();

  // Hand off to coordinator — it handles enhance → lead → builders → reviewers
  await runCoordinator(task, {
    ...opts,
    projectDir: resolve(process.cwd()),
    noMerge: opts.merge === false,
  });
}
