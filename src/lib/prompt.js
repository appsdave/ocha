/**
 * @module prompt
 * Interactive multi-line task input for `ocha` (no -t flag).
 * Paste your task — press Enter on a blank line to submit.
 */
import readline from 'node:readline';
import chalk from 'chalk';

export async function readMultilineTask() {
  console.log(chalk.bold.blue('┌─ 🚀  ocha ─────────────────────────────────────┐'));
  console.log(`│  ${chalk.dim('Paste your task below. Press Enter twice to run.')}`);
  console.log(chalk.bold.blue('└' + '─'.repeat(49) + '┘'));
  console.log();

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });

  const lines = [];
  let consecutiveBlanks = 0;

  return new Promise((resolve) => {
    rl.on('line', (line) => {
      if (line.trim() === '') {
        consecutiveBlanks++;
        if (consecutiveBlanks >= 1 && lines.length > 0) {
          rl.close();
        } else {
          lines.push(line);
        }
      } else {
        consecutiveBlanks = 0;
        lines.push(line);
      }
    });

    rl.on('close', () => {
      const task = lines.join('\n').trim();
      if (!task) {
        console.log(chalk.yellow('  No task entered. Exiting.'));
        resolve(null);
      } else {
        resolve(task);
      }
    });

    rl.on('SIGINT', () => {
      console.log(chalk.yellow('\n  Cancelled.'));
      rl.close();
      resolve(null);
    });
  });
}
