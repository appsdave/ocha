import { mkdirSync, existsSync } from 'fs';
import chalk from 'chalk';
import { OCHA_DIR, ROLES_DIR } from '../lib/paths.js';
import { createInitialStatus, writeStatus } from '../lib/status.js';
import { decomposeTask } from '../lib/decompose.js';
import { runCoordinator } from '../lib/coordinator.js';
import { installRolePrompts } from '../lib/roles.js';

export async function cordStart(opts) {
  console.log(chalk.blue('🚀 ocha cord start'));
  console.log(chalk.gray(`Task: ${opts.task}`));
  console.log(chalk.gray(`Base branch: ${opts.baseBranch}`));

  // Initialize .ocha directory
  if (existsSync(OCHA_DIR)) {
    console.log(chalk.yellow('⚠ .ocha/ already exists. Use "ocha cord stop" first to reset.'));
    process.exit(1);
  }

  mkdirSync(OCHA_DIR, { recursive: true });
  mkdirSync(ROLES_DIR, { recursive: true });

  // Install default role prompts
  installRolePrompts();

  // Decompose the task into subtasks
  console.log(chalk.blue('\n📋 Decomposing task into subtasks...'));
  const tasks = await decomposeTask(opts.task);
  console.log(chalk.green(`   Found ${tasks.length} subtask(s)\n`));

  // Create initial status
  const status = createInitialStatus(opts.task, tasks);
  writeStatus(status);

  // Run the coordinator loop
  await runCoordinator(opts);
}
