import chalk from 'chalk';
import { readStatus } from '../lib/status.js';

export function cordStatus() {
  const status = readStatus();
  if (!status) {
    console.log(chalk.yellow('No active ocha session. Run "ocha cord start" first.'));
    return;
  }

  console.log(chalk.blue('\n📊 OCHA Session Status\n'));
  console.log(`Task:    ${status.session.task}`);
  console.log(`State:   ${status.session.state}`);
  console.log(`Started: ${status.session.startedAt}\n`);

  const stateIcon = { pending: '⏳', running: '🔄', completed: '✅', failed: '❌' };

  for (const task of status.tasks) {
    const icon = stateIcon[task.state] || '?';
    console.log(`  ${icon} ${task.id} [${task.role}] ${task.state}`);
    console.log(chalk.gray(`     ${task.description}`));
    console.log(chalk.gray(`     branch: ${task.branch}`));
    if (task.worktree) console.log(chalk.gray(`     worktree: ${task.worktree}`));
    console.log();
  }
}
