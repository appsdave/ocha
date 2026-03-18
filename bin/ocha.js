#!/usr/bin/env node
import { program } from 'commander';
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
      execSync(`git pull --rebase ${OCHA_REPO} main`, { cwd: installDir, encoding: 'utf-8' });
      const after = execSync('git rev-parse HEAD', { cwd: installDir, encoding: 'utf-8' }).trim();
      if (before === after) {
        console.log(chalk.green('✅ Already up to date.'));
      } else {
        // Show what changed
        const log = execSync(
          `git log --oneline ${before}..${after}`,
          { cwd: installDir, encoding: 'utf-8' }
        ).trim();
        console.log(chalk.bold('\n  What changed:'));
        for (const line of log.split('\n')) {
          console.log(chalk.gray(`    • ${line}`));
        }
        console.log();
        execSync('npm install --production', { cwd: installDir, stdio: 'pipe' });
        // Re-link so the global `ocha` command picks up any bin changes
        try {
          execSync('npm link', { cwd: installDir, stdio: 'pipe' });
        } catch {
          // npm link may fail if not installed globally — not fatal
        }
        console.log(chalk.green(`✅ Updated ${before.slice(0,7)} → ${after.slice(0,7)}`));
      }
    } catch (err) {
      console.log(chalk.red(`✗ Update failed: ${err.message}`));
    }
  });

// --tui-agent mode: spawned by TUI to run a single task, streaming output
if (process.argv.includes('--tui-agent')) {
  const taskIdx = process.argv.indexOf('--task');
  const branchIdx = process.argv.indexOf('--branch');
  const task = taskIdx !== -1 ? process.argv[taskIdx + 1] : null;
  const ts = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 15).replace(/(\d{8})(\d{6})/, '$1-$2');
  const branch = branchIdx !== -1 ? process.argv[branchIdx + 1] : `ocha/task-${ts}`;

  if (!task) {
    console.error('--tui-agent requires --task <task>');
    process.exit(1);
  }

  const { cordStart } = await import('../src/commands/cord-start.js');
  await cordStart({ task, baseBranch: 'main', maxAgents: '1', branch });
  process.exit(0);
}

// Default action: launch TUI when no subcommand given
if (process.argv.length === 2) {
  try {
    const { OchaTUI } = await import('../src/lib/tui.js');
    const tui = new OchaTUI();
    tui.launch();
  } catch (err) {
    process.stderr.write(`[ocha] TUI failed to launch: ${err.message}\n${err.stack}\n`);
    process.exit(1);
  }
} else {
  program.parse();
}
