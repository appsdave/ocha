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
 * Warns and exits if .ocha/ already exists.
 */
export function ochaInit() {
  if (pathExists(OCHA_DIR)) {
    console.log(chalk.yellow('⚠ .ocha/ already exists. Remove it first or run "ocha cord stop".'));
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
