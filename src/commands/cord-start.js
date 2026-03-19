/**
 * @module commands/cord-start
 * Implements the `ocha cord start` command.
 * Validates the environment then hands off to runCoordinator() which handles
 * the full pipeline: enhance → lead → builders → reviewers.
 */
import chalk from 'chalk';
import { resolve } from 'node:path';
import { git } from '../lib/exec.js';
import { ensureDir, pathExists } from '../lib/files.js';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { runCoordinator } from '../lib/coordinator.js';
import { installRolePrompts } from '../lib/roles.js';
import { ensureAuthenticated } from '../lib/agent.js';
import { readMultilineTask } from '../lib/prompt.js';
import { drawBox } from '../lib/ui.js';

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
  // If no -t given, open interactive prompt
  let task = opts.task ? opts.task.trim() : null;
  if (!task) {
    task = await readMultilineTask();
    if (!task) process.exit(0);
  }

  // Resolve repo dirs — default to cwd if none given
  const repoDirs = (opts.repo && opts.repo.length > 0)
    ? opts.repo.map(r => resolve(r))
    : [resolve(process.cwd())];

  const maxAgentsLabel = parseInt(opts.maxAgents, 10) === 1 ? '1 agent' : `${opts.maxAgents} agents (parallel)`;

  const rows = [
    [chalk.dim('Task  '), task],
    [chalk.dim('Branch'), opts.baseBranch],
    [chalk.dim('Agents'), maxAgentsLabel],
  ];
  if (repoDirs.length > 1) {
    rows.push([chalk.dim('Repos '), `${repoDirs.length} repos`]);
    for (const r of repoDirs) rows.push([chalk.dim('  →'), r]);
  }
  drawBox('🚀  ocha cord start', rows, { maxWidth: 80 });

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
    git(['rev-parse', '--is-inside-work-tree']);
  } catch {
    console.log(chalk.red('  ✗ Not a git repository'));
    console.log(chalk.yellow('\n  To fix this, run:'));
    console.log(chalk.white('    git init && git add . && git commit -m "initial commit"'));
    process.exit(1);
  }

  // Check base branch exists
  try {
    git(['rev-parse', '--verify', opts.baseBranch]);
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
    projectDir: repoDirs[0],
    repoDirs,
    noMerge: opts.merge === false,
  });
}
