import { mkdirSync, existsSync } from 'fs';
import chalk from 'chalk';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { installRolePrompts } from '../lib/roles.js';

export function ochaInit() {
  if (existsSync(OCHA_DIR)) {
    console.log(chalk.yellow('⚠ .ocha/ already exists. Remove it first or run "ocha cord stop".'));
    return;
  }

  mkdirSync(OCHA_DIR, { recursive: true });
  mkdirSync(ROLES_DIR, { recursive: true });

  installRolePrompts();

  console.log(chalk.green('✓ Initialized .ocha/ directory'));
  console.log(chalk.gray('  .ocha/roles/coordinator.md'));
  console.log(chalk.gray('  .ocha/roles/lead.md'));
  console.log(chalk.gray('  .ocha/roles/builder.md'));
  console.log(chalk.gray('  .ocha/roles/reviewer.md'));
  console.log(chalk.blue('\nRun "ocha cord start -t \'your task\'" to begin.'));
}
