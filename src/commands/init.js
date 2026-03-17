/**
 * @module commands/init
 * Implements the `ocha init` command.
 * Creates the .ocha/ directory structure and installs agent role prompts.
 */
import chalk from 'chalk';
import { ensureDir, pathExists } from '../lib/files.js';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { installRolePrompts } from '../lib/roles.js';

/**
 * Initializes the .ocha/ directory with role prompt files.
 * If .ocha/ already exists, requires --yes flag to reinitialize.
 * @param {object} opts - Command options from commander.
 */
export function ochaInit(opts) {
  if (pathExists(OCHA_DIR) && !opts.yes) {
    console.log(chalk.yellow('⚠ .ocha/ already exists. Use "ocha init --yes" to reinitialize.'));
    return;
  }

  ensureDir(OCHA_DIR);
  ensureDir(ROLES_DIR);

  installRolePrompts();

  console.log(chalk.green('✓ Initialized .ocha/ directory'));
  console.log(chalk.gray('  .ocha/roles/coordinator.md'));
  console.log(chalk.gray('  .ocha/roles/lead.md'));
  console.log(chalk.gray('  .ocha/roles/builder.md'));
  console.log(chalk.gray('  .ocha/roles/reviewer.md'));
  console.log(chalk.blue('\nRun "ocha cord start -t \'your task\'" to begin.'));
}
