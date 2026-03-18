import { existsSync, mkdirSync, rmSync } from 'fs';
import { resolve } from 'path';
import { spawn } from 'child_process';
import chalk from 'chalk';
import { ensureAuthenticated } from '../lib/agent.js';
import { git } from '../lib/exec.js';

const DEV_DIR = resolve(process.cwd(), '.ocha-dev');
const DEV_BRANCH = 'ocha-dev-session';

export async function ochaDev(opts) {
  const task = opts.task;
  const baseBranch = opts.baseBranch || 'main';
  const worktreePath = resolve(DEV_DIR, 'ocha-dev');

  console.log(chalk.blue('🔧 ocha dev'));
  console.log(chalk.gray(`   Task: ${task}`));
  console.log(chalk.gray(`   Base: ${baseBranch}`));

  // Auth check
  console.log(chalk.blue('\n🔐 Checking authentication...'));
  try {
    await ensureAuthenticated();
    console.log(chalk.green('   ✓ Authenticated successfully'));
  } catch (err) {
    console.log(chalk.red(`   ✗ Authentication failed: ${err.message}`));
    process.exit(1);
  }

  // Create dev worktree
  console.log(chalk.blue('\n📂 Creating dev worktree...'));
  if (!existsSync(DEV_DIR)) {
    mkdirSync(DEV_DIR, { recursive: true });
  }

  if (existsSync(worktreePath)) {
    console.log(chalk.yellow('   Cleaning up existing dev worktree...'));
    try {
      git(['worktree', 'remove', worktreePath, '--force']);
    } catch {}
  }

  // Delete branch if it exists from a previous session
  try {
    git(['branch', '-D', DEV_BRANCH]);
  } catch {}

  try {
    git(['worktree', 'add', '-b', DEV_BRANCH, worktreePath, baseBranch]);
    console.log(chalk.green(`   ✓ Worktree created at ${worktreePath}`));
    console.log(chalk.gray(`   Branch: ${DEV_BRANCH}`));
  } catch (err) {
    console.log(chalk.red(`   ✗ Failed to create worktree: ${err.message}`));
    process.exit(1);
  }

  // Spawn Junie in the dev worktree
  console.log(chalk.blue('\n🤖 Spawning Junie in dev worktree...\n'));

  const exitCode = await runJunieInWorktree(worktreePath, task);

  if (exitCode === 0) {
    console.log(chalk.green('\n✓ Junie completed successfully'));

    // Check if there are changes to merge
    try {
      const diff = git(['diff', baseBranch, '--stat'], { cwd: worktreePath }).trim();
      if (diff) {
        console.log(chalk.blue('\n📋 Changes made:'));
        console.log(chalk.gray(diff.split('\n').map(l => `   ${l}`).join('\n')));

        // Push branch
        try {
          git(['push', '-u', 'origin', DEV_BRANCH, '--force'], { cwd: worktreePath });
          console.log(chalk.green('\n   ✓ Branch pushed'));
        } catch {}

        // Merge back into base
        if (!opts.noMerge) {
          console.log(chalk.blue(`\n🔀 Merging ${DEV_BRANCH} into ${baseBranch}...`));
          try {
            git(['merge', DEV_BRANCH]);
            console.log(chalk.green('   ✓ Merged successfully'));
          } catch (err) {
            console.log(chalk.red('   ✗ Merge conflict — resolve manually:'));
            console.log(chalk.gray(`     git merge ${DEV_BRANCH}`));
          }
        } else {
          console.log(chalk.yellow(`\n   Skipping merge (--no-merge). To merge manually:`));
          console.log(chalk.gray(`     git merge ${DEV_BRANCH}`));
        }
      } else {
        console.log(chalk.yellow('   No changes were made'));
      }
    } catch {
      console.log(chalk.yellow('   Could not determine changes'));
    }
  } else {
    console.log(chalk.red(`\n✗ Junie exited with code ${exitCode}`));
  }

  // Cleanup worktree
  console.log(chalk.blue('\n🧹 Cleaning up...'));
  try {
    git(['worktree', 'remove', worktreePath, '--force']);
    console.log(chalk.green('   ✓ Worktree removed'));
  } catch {}

  if (existsSync(DEV_DIR)) {
    rmSync(DEV_DIR, { recursive: true, force: true });
  }

  // Clean up branch if merged
  if (exitCode === 0 && !opts.noMerge) {
    try {
      git(['branch', '-D', DEV_BRANCH]);
      console.log(chalk.green('   ✓ Branch cleaned up'));
    } catch {}
  }
}

function runJunieInWorktree(worktreePath, task) {
  return new Promise((resolveP) => {
    const proc = spawn('junie', [
      '--project', worktreePath,
      '--task', task,
      '--brave',
    ], {
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
    });

    const prefix = chalk.gray('  │ ');
    let lastLine = '';

    const handleData = (data) => {
      for (const line of data.toString().split('\n')) {
        const t = line.trim();
        if (!t || t === lastLine) continue;
        if (t.startsWith('[Junie]') || t.startsWith('Enter passphrase')) continue;

        // Show auth confirmation
        if (t.includes('Authenticated successfully')) {
          console.log(prefix + chalk.green('Authenticated'));
          lastLine = t;
          continue;
        }

        // Show meaningful lines
        if (
          t.startsWith('● TASK RESULT') ||
          t.startsWith('TASK RESULT') ||
          (t.length > 20 && /^[A-Z]/.test(t) && !t.startsWith('●') && !t.startsWith('│'))
        ) {
          const display = t.replace(/^●?\s*TASK RESULT:\s*/, '');
          const truncated = display.length > 120 ? display.slice(0, 117) + '...' : display;
          console.log(prefix + chalk.white(truncated));
          lastLine = t;
        }
      }
    };

    proc.stdout.on('data', handleData);
    proc.stderr.on('data', handleData);

    proc.on('close', (code) => resolveP(code));
    proc.on('error', () => resolveP(1));
  });
}
