/**
 * @module cord-resolve
 * Resolve merge conflicts on an agent's PR branch by rebasing onto the base branch.
 *
 * Usage:
 *   ocha cord resolve --pr <number>
 *   ocha cord resolve --branch <branch-name>
 *
 * Flow:
 *   1. Identify the PR branch (from --pr or --branch)
 *   2. Fetch latest base branch and PR branch
 *   3. Check out the PR branch in a temporary worktree
 *   4. Rebase onto the base branch
 *   5. If conflicts arise, spawn a Junie agent to resolve them
 *   6. Force-push the rebased branch
 *   7. Clean up the worktree
 */
import chalk from 'chalk';
import { git, exec } from '../lib/exec.js';
import { createWorktree, removeWorktree } from '../lib/worktree.js';
import { spawnAgent } from '../lib/agent.js';
import { startSpinner, succeedSpinner, failSpinner, stopSpinner } from '../lib/spinner.js';

/**
 * Resolve merge conflicts on a PR branch.
 *
 * @param {object} opts
 * @param {string} [opts.pr]         - PR number to resolve.
 * @param {string} [opts.branch]     - Branch name to resolve (alternative to --pr).
 * @param {string} [opts.baseBranch] - Base branch to rebase onto (default: main).
 */
export async function cordResolve(opts) {
  const baseBranch = opts.baseBranch || 'main';
  const projectDir = process.cwd();
  let branchName = opts.branch || null;

  // ── Step 1: Resolve branch name from PR number if needed ────────────────
  if (opts.pr && !branchName) {
    const spinner = startSpinner(`Looking up PR #${opts.pr}…`);
    try {
      const prJson = exec('gh', [
        'pr', 'view', opts.pr,
        '--json', 'headRefName,state,mergeable',
      ], { cwd: projectDir }).trim();
      const pr = JSON.parse(prJson);
      branchName = pr.headRefName;
      succeedSpinner(`PR #${opts.pr} → branch ${branchName} (${pr.mergeable})`);
    } catch (err) {
      failSpinner(`Could not look up PR #${opts.pr}: ${err.message}`);
      return;
    }
  }

  if (!branchName) {
    console.log(chalk.red('✗ Provide --pr <number> or --branch <name>'));
    return;
  }

  // ── Step 2: Fetch latest refs ───────────────────────────────────────────
  const fetchSpinner = startSpinner(`Fetching ${baseBranch} and ${branchName}…`);
  try {
    git(['fetch', 'origin', baseBranch, branchName], { cwd: projectDir });
    succeedSpinner('Fetched latest refs');
  } catch (err) {
    failSpinner(`Fetch failed: ${err.message}`);
    return;
  }

  // ── Step 3: Create a temporary worktree for the PR branch ───────────────
  let worktreePath;
  const wtSpinner = startSpinner(`Creating worktree for ${branchName}…`);
  try {
    worktreePath = createWorktree(branchName, baseBranch, projectDir);
    // Check out the remote PR branch content
    git(['checkout', branchName], { cwd: worktreePath });
    succeedSpinner(`Worktree ready at ${worktreePath}`);
  } catch (err) {
    // Branch may already be checked out locally
    try {
      worktreePath = createWorktree(`resolve-${branchName}`, baseBranch, projectDir);
      git(['reset', '--hard', `origin/${branchName}`], { cwd: worktreePath });
      succeedSpinner(`Worktree ready at ${worktreePath}`);
    } catch (err2) {
      failSpinner(`Could not create worktree: ${err2.message}`);
      return;
    }
  }

  // ── Step 4: Attempt rebase ──────────────────────────────────────────────
  const rebaseSpinner = startSpinner(`Rebasing ${branchName} onto origin/${baseBranch}…`);
  let rebaseClean = false;
  try {
    git(['rebase', `origin/${baseBranch}`], { cwd: worktreePath });
    rebaseClean = true;
    succeedSpinner(`Rebase succeeded — no conflicts`);
  } catch {
    failSpinner('Rebase has conflicts — spawning agent to resolve');
  }

  // ── Step 5: If conflicts, spawn a Junie agent to resolve them ───────────
  if (!rebaseClean) {
    // Get list of conflicted files
    let conflictFiles = '';
    try {
      conflictFiles = git(['diff', '--name-only', '--diff-filter=U'], { cwd: worktreePath }).trim();
    } catch {
      try {
        conflictFiles = exec('grep', ['-rl', '<<<<<<<', '.'], { cwd: worktreePath }).trim();
      } catch {}
    }

    const resolveTask = {
      id: 'resolve-conflicts',
      description: [
        `Resolve the git merge conflicts in this worktree.`,
        ``,
        `The branch \`${branchName}\` is being rebased onto \`origin/${baseBranch}\`.`,
        `Git has paused the rebase because of conflicts.`,
        ``,
        `Conflicted files:`,
        conflictFiles || '(run `git diff --name-only --diff-filter=U` to find them)',
        ``,
        `Instructions:`,
        `1. Open each conflicted file and resolve the <<<<<<< / ======= / >>>>>>> markers`,
        `2. Keep the intent of BOTH sides — the base branch changes AND the PR branch changes`,
        `3. Run \`git add <file>\` for each resolved file`,
        `4. Run \`GIT_EDITOR=true git rebase --continue\` to finish the rebase`,
        `5. If the rebase has more conflicts, repeat steps 1-4`,
        `6. Do NOT run git push — that will be handled automatically`,
      ].join('\n'),
      branch: branchName,
      role: 'builder',
    };

    const agentSpinner = startSpinner('🔧 Agent resolving merge conflicts…');
    try {
      const { code } = await spawnAgent(resolveTask, worktreePath, 'builder');
      if (code === 0) {
        succeedSpinner('🔧 Agent resolved conflicts');
        rebaseClean = true;
      } else {
        failSpinner('🔧 Agent could not resolve conflicts');
      }
    } catch (err) {
      failSpinner(`🔧 Agent error: ${err.message}`);
    }
  }

  // ── Step 6: Force-push the rebased branch ───────────────────────────────
  if (rebaseClean) {
    const pushSpinner = startSpinner(`Pushing rebased ${branchName}…`);
    try {
      git(['push', '--force-with-lease', 'origin', branchName], { cwd: worktreePath });
      succeedSpinner(`Pushed ${branchName} — PR should now be mergeable`);
    } catch {
      try {
        git(['push', '--force', 'origin', branchName], { cwd: worktreePath });
        succeedSpinner(`Force-pushed ${branchName} — PR should now be mergeable`);
      } catch (err) {
        failSpinner(`Could not push: ${err.message}`);
      }
    }
  } else {
    console.log(chalk.yellow('\n  ⚠ Conflicts could not be resolved automatically.'));
    console.log(chalk.yellow('    Resolve manually in the worktree and push:'));
    console.log(chalk.dim(`    cd ${worktreePath}`));
    console.log(chalk.dim(`    # resolve conflicts, then:`));
    console.log(chalk.dim(`    git add -A && GIT_EDITOR=true git rebase --continue`));
    console.log(chalk.dim(`    git push --force-with-lease origin ${branchName}`));
  }

  // ── Step 7: Clean up worktree ───────────────────────────────────────────
  if (rebaseClean) {
    try {
      removeWorktree(worktreePath);
    } catch {}
  }

  stopSpinner();
}
