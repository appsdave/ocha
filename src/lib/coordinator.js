/**
 * @module coordinator
 * Full pipeline: enhance prompt → lead agent plans → builders execute → reviewer per builder.
 *
 * Flow:
 *   1. enhanceTask()     — coordinator enriches the raw user prompt with project context
 *   2. runLeadAgent()    — lead analyzes project, outputs a JSON task plan
 *   3. createInitialStatus() — writes .ocha/status.json with the planned tasks
 *   4. Rolling loop      — up to maxAgents concurrent, each task:
 *        createWorktree → spawnAgent(builder, up to 2 retries) → spawnAgent(reviewer) → merge/PR
 *   5. showDiffStats / cleanupWorktrees / printSummary
 */
import { spawnAgent } from './agent.js';
import { createWorktree, removeWorktree } from './worktree.js';
import { readStatus, writeStatus, createInitialStatus } from './status.js';
import { enhanceTask } from './enhance.js';
import { runLeadAgent } from './lead.js';
import { execSync } from 'child_process';
import { safeDelete } from './files.js';
import { WORKTREES_DIR } from './paths.js';
import chalk from 'chalk';
import { startSpinner, succeedSpinner, failSpinner, stopSpinner, logWithSpinner } from './spinner.js';
import { isBeadsInitialized, ensureDoltServer, createBeadsIssue, claimBeadsIssue, closeBeadsIssue, pushBeadsData } from './beads.js';
import {
  initTree,
  setLeadNode,
  setBuilderNode,
  setReviewerNode,
  setCoordinatorState,
  finalizeTree,
} from './tree.js';

/**
 * Runs the full coordinator pipeline.
 *
 * @param {string} task    - Raw user task description.
 * @param {object} opts    - Command options.
 * @param {string} opts.maxAgents   - Maximum parallel builder agents.
 * @param {string} opts.baseBranch  - Git branch to create worktrees from.
 * @param {string} opts.projectDir  - Absolute path to the project root.
 * @param {boolean} [opts.noMerge]  - Skip auto-merge (kept for compat).
 */
/** Strip markdown headers/context block — return just the human task line. */
function extractRawTask(enhanced, original) {
  // Enhanced format: "## Task\n<original>\n\n---\n## Project Context..."
  const m = enhanced.match(/^##\s*Task\s*\n([\s\S]*?)(?:\n---\n|$)/);
  if (m) return m[1].trim();
  return original;
}

export async function runCoordinator(task, opts) {
  const maxAgents = parseInt(opts.maxAgents, 10);
  const baseBranch = opts.baseBranch;
  const projectDir = opts.projectDir || process.cwd();
  const repoDirs = (opts.repoDirs && opts.repoDirs.length > 0) ? opts.repoDirs : [projectDir];

  // ── Step 0: Start beads if available ─────────────────────────────────────
  let beadsEnabled = false;
  try {
    ensureDoltServer(projectDir);
    beadsEnabled = isBeadsInitialized(projectDir);
    if (beadsEnabled) {
      console.log(chalk.green('✔ 🔗 Beads (bd) issue tracking active'));
    }
  } catch {
    // Beads not available — continue without it
  }

  // ── Step 1: Coordinator enhances the prompt ──────────────────────────────
  initTree(task);

  let enhancedTask = task;
  {
    enhancedTask = await enhanceTask(task, projectDir, repoDirs.slice(1));
    if (enhancedTask !== task) {
      console.log(chalk.green('✔ 🧠 Prompt enhanced with project context'));
      // Show the raw task portion (before the --- context block)
      const rawTask = extractRawTask(enhancedTask, task);
      const contextAdded = enhancedTask.length - task.length;
      console.log(chalk.white(`   ${rawTask}`));
      console.log(chalk.dim(`   (+${contextAdded} chars of project context appended)`));
    } else {
      console.log(chalk.yellow('⚠ 🧠 No project context found — using original prompt'));
    }
  }

  // ── Step 2: Lead agent analyzes project and produces task plan ────────────
  setLeadNode('running', 'Analyzing project & planning tasks');

  let tasks;
  {
    const leadStart = Date.now();
    const leadSpinner = startSpinner('👔 Lead agent analyzing project and planning tasks…');
    const leadTimer = setInterval(() => {
      const secs = Math.floor((Date.now() - leadStart) / 1000);
      leadSpinner.text = `👔 Lead agent analyzing project and planning tasks… (${secs}s)`;
    }, 1000);
    try {
      tasks = await runLeadAgent(enhancedTask, projectDir);
      clearInterval(leadTimer);
      setLeadNode('completed', `Planned ${tasks.length} task(s)`);
      succeedSpinner(`👔 Lead planned ${tasks.length} task(s) (${Math.floor((Date.now() - leadStart) / 1000)}s)`);
      for (const t of tasks) {
        const tDesc = extractRawTask(t.description, t.description).split('\n')[0].slice(0, 80);
        console.log(chalk.gray(`   • [${t.branch}] ${tDesc}${t.description.length > 80 ? '…' : ''}`));
      }
    } catch (err) {
      clearInterval(leadTimer);
      setLeadNode('failed', 'Planning failed — using fallback');
      failSpinner(`👔 Lead agent failed: ${err.message} — falling back to single task`);
      const ts = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 15).replace(/(\d{8})(\d{6})/, '$1-$2');
      tasks = [{ description: enhancedTask, role: 'builder', branch: `ocha/task-${ts}`, displayDesc: task, repoDir: repoDirs[0] }];
    }
  }

  // ── Step 3: Assign repoDir round-robin & create beads issues ────────────
  tasks.forEach((t, i) => { if (!t.repoDir) t.repoDir = repoDirs[i % repoDirs.length]; });

  if (beadsEnabled) {
    for (const t of tasks) {
      const title = shortDesc(t.description.split('\n')[0]);
      const issueId = createBeadsIssue(title, t.description, { cwd: projectDir });
      if (issueId) {
        t.beadsId = issueId;
        logWithSpinner(chalk.dim(`  🔗 Beads issue ${issueId} → ${t.branch}`));
      }
    }
  }

  // ── Step 4: Write initial status ─────────────────────────────────────────
  const status = createInitialStatus(enhancedTask, tasks);

  console.log(chalk.blue(`\n🎯 Coordinator dispatching ${status.tasks.length} builder(s) (max ${maxAgents} parallel)\n`));

  // ── Step 5: Rolling concurrency builder loop ──────────────────────────────
  const pending = status.tasks.filter(t => t.state === 'pending');
  let active = 0;
  let idx = 0;

  await new Promise((resolveAll) => {
    function tryStart() {
      while (active < maxAgents && idx < pending.length) {
        const task = pending[idx++];
        active++;
        runBuilderWithReview(task, status, baseBranch).finally(() => {
          active--;
          tryStart();
          if (active === 0 && idx >= pending.length) resolveAll();
        });
      }
      if (pending.length === 0) resolveAll();
    }
    tryStart();
  });

  stopSpinner();

  // ── Step 6: Wrap up ───────────────────────────────────────────────────────
  const finalStatus = readStatus() || status;

  setCoordinatorState('completed');
  finalizeTree();

  showDiffStats(finalStatus, baseBranch);
  cleanupWorktrees(finalStatus);
  safeDelete(WORKTREES_DIR, { recursive: true });

  // Push beads data if active
  if (beadsEnabled) {
    // Close completed task issues
    for (const t of finalStatus.tasks) {
      if (t.state === 'completed' && t.beadsId) {
        closeBeadsIssue(t.beadsId, `Completed — PR: ${t.prUrl || 'none'}`, projectDir);
      }
    }
    pushBeadsData(projectDir);
    logWithSpinner(chalk.dim('  🔗 Beads data synced'));
  }

  // Auto-stop: mark session completed
  finalStatus.session.state = 'completed';
  finalStatus.session.completedAt = new Date().toISOString();
  writeStatus(finalStatus);

  printSummary(finalStatus);
}

// ─── Builder + Reviewer runner (with retry) ───────────────────────────────────

const MAX_RETRIES = 2;

async function runBuilderWithReview(task, status, baseBranch) {
  const cleanDesc = task.displayDesc ? shortDesc(task.displayDesc) : shortDesc(task.description.split('\n')[0]);
  setBuilderNode(task.id, 'pending', cleanDesc);

  // Claim beads issue atomically before starting work
  if (task.beadsId) {
    claimBeadsIssue(task.beadsId, task.repoDir || process.cwd());
  }

  const taskRepoDir = task.repoDir || process.cwd();
  const worktreePath = createWorktree(task.branch, baseBranch, taskRepoDir);
  task.state = 'running';
  writeStatus(status);
  setBuilderNode(task.id, 'running', cleanDesc);

  let code = -1;
  for (let attempt = 1; attempt <= MAX_RETRIES + 1; attempt++) {
    try {
      ({ code } = await spawnAgent(task, worktreePath, 'builder'));
    } catch (err) {
      logWithSpinner(chalk.red(`  ✗ Builder error (attempt ${attempt}): ${err.message}`));
      code = -1;
    }
    if (code === 0) break;
    if (attempt <= MAX_RETRIES) {
      logWithSpinner(chalk.yellow(`  ↺ Builder failed (attempt ${attempt}/${MAX_RETRIES + 1}), retrying: ${cleanDesc}`));
      setBuilderNode(task.id, 'running', `${cleanDesc} [retry ${attempt}]`);
    }
  }

  if (code !== 0) {
    setBuilderNode(task.id, 'failed', cleanDesc);
    logWithSpinner(chalk.red(`  ✗ Builder failed after ${MAX_RETRIES + 1} attempts: ${cleanDesc}`));
    task.state = 'failed';
    if (task.beadsId) {
      closeBeadsIssue(task.beadsId, `Failed after ${MAX_RETRIES + 1} attempts`, task.repoDir || process.cwd());
    }
    writeStatus(status);
    return;
  }

  setBuilderNode(task.id, 'completed', cleanDesc);
  logWithSpinner(chalk.green(`  ✓ Builder done: ${cleanDesc}`));
  task.state = 'completed';
  writeStatus(status);

  // ── Spawn reviewer ──────────────────────────────────────────────────────────
  setReviewerNode(task.id, 'running');
  logWithSpinner(chalk.magenta(`  🔍 Reviewer checking: ${cleanDesc}`));

  const reviewTask = {
    id: `${task.id}-review`,
    description: `Review the changes made in this worktree against the base branch (${baseBranch}). Check for bugs, security issues, missing tests, and code quality. If the changes look good, report approval. If there are blocking issues, report them clearly.\n\nOriginal task: ${cleanDesc}`,
    branch: task.branch,
    role: 'reviewer',
  };

  try {
    const { code: reviewCode } = await spawnAgent(reviewTask, worktreePath, 'reviewer');

    const reviewPassed = reviewCode === 0;
    if (reviewPassed) {
      setReviewerNode(task.id, 'completed');
      logWithSpinner(chalk.green(`  ✓ Review passed: ${cleanDesc}`));
    } else {
      setReviewerNode(task.id, 'failed');
      logWithSpinner(chalk.yellow(`  ⚠ Review flagged issues: ${cleanDesc}`));
    }

    // Always push branch and open a PR — never auto-merge
    try {
      execSync(`cd "${worktreePath}" && git push -u origin ${task.branch} --force`, { stdio: 'pipe' });
      logWithSpinner(chalk.green(`  ✓ Pushed branch ${task.branch} to origin`));
    } catch (pushErr) {
      logWithSpinner(chalk.yellow(`  ⚠ Could not push ${task.branch}: ${pushErr.message}`));
    }

    try {
      const prTitle = `ocha: ${shortDesc(cleanDesc)}`;

      // Build a git log summary of what changed vs base branch
      let diffSummary = '';
      try {
        const logLines = execSync(
          `git log --oneline ${baseBranch}..${task.branch}`,
          { cwd: worktreePath, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
        ).trim();
        const statLines = execSync(
          `git diff --stat ${baseBranch}..${task.branch}`,
          { cwd: worktreePath, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
        ).trim();
        if (logLines) diffSummary = `\n\n### Commits\n\`\`\`\n${logLines}\n\`\`\``;
        if (statLines) diffSummary += `\n\n### Files changed\n\`\`\`\n${statLines}\n\`\`\``;
      } catch {}

      const reviewStatus = reviewPassed
        ? '✅ Reviewed and approved by ocha reviewer.'
        : '⚠️ Reviewer flagged issues — needs manual review.';
      const prBody = `${reviewStatus}\n\n**Task:** ${cleanDesc}${diffSummary}`;
      const prOutput = execSync(
        `gh pr create --base ${baseBranch} --head ${task.branch} --title "${prTitle}" --body "${prBody}"`,
        { cwd: taskRepoDir, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
      );
      // gh pr create prints the URL as the last line
      const prUrl = prOutput.trim().split('\n').filter(l => l.startsWith('http')).pop()
        || prOutput.trim().split('\n').pop();
      task.prUrl = prUrl;
      writeStatus(status);
      console.log(chalk.cyan(`  🔗 PR created: ${prUrl}`));
    } catch (prErr) {
      // PR may already exist — try to get the URL
      try {
        const prUrl = execSync(`gh pr view ${task.branch} --json url -q .url`, { cwd: taskRepoDir, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
        task.prUrl = prUrl;
        writeStatus(status);
        console.log(chalk.cyan(`  🔗 PR already exists: ${prUrl}`));
      } catch {
        console.log(chalk.yellow(`  ⚠ Could not create PR for ${task.branch}: ${prErr.message.split('\n')[0]}`));
      }
    }
  } catch (reviewErr) {
    setReviewerNode(task.id, 'failed');
    logWithSpinner(chalk.yellow(`  ⚠ Reviewer failed to run: ${reviewErr.message}`));
  }

  writeStatus(status);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function showDiffStats(status, baseBranch) {
  const completed = status.tasks.filter(t => t.state === 'completed');
  for (const task of completed) {
    if (task.merged) continue;
    try {
      const repoDir = task.repoDir || process.cwd();
      const diff = execSync(`git diff ${baseBranch}..${task.branch} --stat`, { cwd: repoDir, encoding: 'utf-8' }).trim();
      if (diff) {
        console.log(chalk.blue(`\n  📋 Changes in ${task.branch}:`));
        console.log(chalk.gray(diff.split('\n').map(l => `     ${l}`).join('\n')));
      }
    } catch {}
  }
}

function cleanupWorktrees(status) {
  for (const task of status.tasks) {
    if (task.worktree) {
      try { removeWorktree(task.worktree); } catch {}
    }
  }
}

function shortDesc(description) {
  // Strip leading markdown header lines (e.g. "## Task") before summarising
  const clean = description.replace(/^(##?\s*\w+\s*\n)+/, '').trim();
  const words = clean.split(/\s+/);
  return words.slice(0, 6).join(' ') + (words.length > 6 ? '…' : '');
}

function printSummary(status) {
  const completed = status.tasks.filter(t => t.state === 'completed');
  const failed    = status.tasks.filter(t => t.state === 'failed');
  const withPR    = completed.filter(t => t.prUrl);
  const noPR      = completed.filter(t => !t.prUrl);

  console.log(chalk.bold.blue('\n┌─ 🏁  ocha session complete ────────────────────┐'));
  console.log(`│  ${chalk.dim('Total    ')} ${status.tasks.length}`);
  console.log(`│  ${chalk.dim('Completed')} ${chalk.green(completed.length)}`);
  if (failed.length) console.log(`│  ${chalk.dim('Failed   ')} ${chalk.red(failed.length)}`);
  if (withPR.length) console.log(`│  ${chalk.dim('Open PRs ')} ${chalk.cyan(withPR.length)}`);
  console.log(chalk.bold.blue('└' + '─'.repeat(49) + '┘'));

  if (withPR.length > 0) {
    console.log(chalk.cyan('\n  Open pull requests:'));
    for (const task of withPR) {
      const desc = (task.displayDesc || task.description).replace(/^##\s*Task\s*\n/, '').split('\n')[0].slice(0, 60);
      console.log(chalk.cyan(`    🔗 ${task.prUrl}`));
      console.log(chalk.dim(`       ${task.branch} — ${desc}`));
    }
  }

  if (noPR.length > 0) {
    console.log(chalk.yellow('\n  Completed (no PR):'));
    for (const task of noPR) {
      const desc = (task.displayDesc || task.description).replace(/^##\s*Task\s*\n/, '').split('\n')[0].slice(0, 60);
      console.log(chalk.yellow(`    ⚠  ${task.branch} — ${desc}`));
    }
  }

  if (failed.length > 0) {
    console.log(chalk.red('\n  Failed tasks:'));
    for (const task of failed) {
      const desc = task.displayDesc ? shortDesc(task.displayDesc) : shortDesc(task.description.split('\n')[0]);
      console.log(chalk.red(`    ✗  ${task.branch} — ${desc}`));
    }
  }

  console.log();
}
