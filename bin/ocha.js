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
  .option('-t, --task <task>', 'High-level task description (omit for interactive prompt)')
  .option('-b, --base-branch <branch>', 'Base branch to create worktrees from', 'main')
  .option('--max-agents <n>', 'Maximum parallel agents', '3')
  .option('--no-merge', 'Skip auto-merge after completion')
  .option('-r, --repo <path>', 'Repo path(s) to target — repeat for multiple repos', (v, acc) => { acc.push(v); return acc; }, [])
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

    const OCHA_REPO = 'https://github.com/appsdave/ocha.git';
    const installDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
    console.log(chalk.blue('🔄 Updating ocha…'));
    try {
      const before = execSync('git rev-parse HEAD', { cwd: installDir, encoding: 'utf-8' }).trim();
      const out = execSync(`git pull ${OCHA_REPO} main`, { cwd: installDir, encoding: 'utf-8' }).trim();
      const after = execSync('git rev-parse HEAD', { cwd: installDir, encoding: 'utf-8' }).trim();
      if (before === after) {
        console.log(chalk.green('✅ Already up to date.'));
      } else {
        console.log(chalk.gray(`   ${out}`));
        execSync('npm install --production', { cwd: installDir, stdio: 'pipe' });
        console.log(chalk.green(`✅ Updated ${before.slice(0,7)} → ${after.slice(0,7)}`));
      }
    } catch (err) {
      console.log(chalk.red(`✗ Update failed: ${err.message}`));
    }
  });

// Default action: interactive prompt when no subcommand given
if (process.argv.length === 2) {
  const { readMultilineTask } = await import('../src/lib/prompt.js');
  const task = await readMultilineTask();
  if (task) {
    const { cordStart } = await import('../src/commands/cord-start.js');
    await cordStart({ task, baseBranch: 'main', maxAgents: '3' });
  }
} else {
  program.parse();
}
