#!/usr/bin/env node
import { program } from 'commander';
import { cordStart } from '../src/commands/cord-start.js';
import { cordStatus } from '../src/commands/cord-status.js';
import { cordStop } from '../src/commands/cord-stop.js';
import { ochaInit } from '../src/commands/init.js';
import { ochaDev } from '../src/commands/dev.js';

program
  .name('ocha')
  .description('Orchestrate Junie agents across git worktrees')
  .version('1.0.0');

program
  .command('init')
  .description('Initialize .ocha/ directory with role prompts and config')
  .option('-y, --yes', 'Reinitialize even if .ocha/ already exists')
  .action(ochaInit);

const cord = program.command('cord').description('Coordinator commands');

cord
  .command('start')
  .description('Start a coordinator session')
  .requiredOption('-t, --task <task>', 'High-level task description')
  .option('-b, --base-branch <branch>', 'Base branch to create worktrees from', 'main')
  .option('--max-agents <n>', 'Maximum parallel agents', '3')
  .option('--no-merge', 'Skip auto-merge after completion')
  .action(cordStart);

cord
  .command('status')
  .description('Check coordinator progress')
  .option('-w, --watch', 'Poll and redraw every 3 seconds until session ends')
  .action((opts) => cordStatus(opts));

cord
  .command('stop')
  .description('Stop the coordinator and all agents')
  .action(cordStop);

program
  .command('dev')
  .description('Run a task in an isolated dev worktree (safe for self-development)')
  .requiredOption('-t, --task <task>', 'Task description')
  .option('-b, --base-branch <branch>', 'Base branch', 'main')
  .option('--no-merge', 'Skip auto-merge after completion')
  .action(ochaDev);

program
  .command('self-update')
  .description('Update ocha to the latest version from git')
  .action(async () => {
    const { execSync } = await import('child_process');
    const { dirname, resolve } = await import('path');
    const { fileURLToPath } = await import('url');
    const chalk = (await import('chalk')).default;

    const installDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
    console.log(chalk.blue('🔄 Updating ocha...'));
    try {
      const out = execSync('git pull origin main', { cwd: installDir, encoding: 'utf-8' });
      console.log(chalk.gray(`   ${out.trim()}`));
      execSync('npm install --production', { cwd: installDir, stdio: 'pipe' });
      console.log(chalk.green('✅ ocha updated!'));
    } catch (err) {
      console.log(chalk.red(`✗ Update failed: ${err.message}`));
    }
  });

program.parse();
