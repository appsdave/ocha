#!/usr/bin/env node
import { program } from 'commander';
import { ochaInit } from '../src/commands/init.js';
import { ochaDev } from '../src/commands/dev.js';
import { cordStart } from '../src/commands/cord-start.js';
import { cordStatus } from '../src/commands/cord-status.js';
import { cordStop } from '../src/commands/cord-stop.js';
import { cordResolve } from '../src/commands/cord-resolve.js';

program
  .name('ocha')
  .description('Orchestrate Junie agents across git worktrees')
  .version('1.0.0');

program
  .command('init')
  .description('Initialize .ocha/ directory with role prompts and config')
  .option('-y, --yes', 'Reinitialize even if .ocha/ already exists')
  .action(ochaInit);

const cord = program.command('cord').description('(deprecated) Use top-level commands instead: ocha status, ocha stop, ocha resolve');

cord
  .command('start')
  .description('Decompose a task and run it across parallel agents')
  .option('-t, --task <task>', 'High-level task description')
  .option('-b, --base-branch <branch>', 'Base git branch for worktrees', 'main')
  .option('-n, --max-agents <n>', 'Maximum parallel agents', '3')
  .option('-r, --repo <path...>', 'Repo path(s) to operate on (defaults to cwd)')
  .option('--no-merge', 'Skip auto-merge after completion')
  .action(cordStart);

cord
  .command('status')
  .description('Show current session status and task states')
  .option('-w, --watch', 'Poll and redraw every 3 seconds until done')
  .action(cordStatus);

cord
  .command('stop')
  .description('Stop all running agents and clean up worktrees')
  .action(cordStop);

cord
  .command('resolve')
  .description('Resolve merge conflicts on a PR branch (rebase + agent)')
  .option('-p, --pr <number>', 'PR number to resolve')
  .option('--branch <name>', 'Branch name to resolve (alternative to --pr)')
  .option('-b, --base-branch <branch>', 'Base branch to rebase onto', 'main')
  .action(cordResolve);

// ── Top-level commands (preferred) ──────────────────────────────────────────

program
  .command('status')
  .description('Show current session status and task states')
  .option('-w, --watch', 'Poll and redraw every 3 seconds until done')
  .action(cordStatus);

program
  .command('stop')
  .description('Stop all running agents and clean up worktrees')
  .action(cordStop);

program
  .command('resolve')
  .description('Resolve merge conflicts on a PR branch (rebase + agent)')
  .option('-p, --pr <number>', 'PR number to resolve')
  .option('--branch <name>', 'Branch name to resolve (alternative to --pr)')
  .option('-b, --base-branch <branch>', 'Base branch to rebase onto', 'main')
  .action(cordResolve);

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
  const task = taskIdx !== -1 ? process.argv[taskIdx + 1] : null;

  if (!task) {
    console.error('--tui-agent requires --task <task>');
    process.exit(1);
  }

  // Suppress CLI tree rendering — the TUI has its own display
  const { silenceTree } = await import('../src/lib/tree.js');
  silenceTree();

  const { cordStart } = await import('../src/commands/cord-start.js');
  await cordStart({ task, baseBranch: 'main', maxAgents: '1' });
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
