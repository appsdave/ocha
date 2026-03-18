/**
 * @module prompt
 * Interactive multi-line task input for `ocha` (no -t flag).
 * Paste your task — press Enter on a blank line to submit.
 */
import readline from 'node:readline';
import chalk from 'chalk';

export async function readMultilineTask() {
  const width = 54;
  const inner = width - 2;
  const top    = chalk.cyan('╭' + '─'.repeat(inner) + '╮');
  const bottom = chalk.cyan('╰' + '─'.repeat(inner) + '╯');
  const divider = chalk.cyan('├' + '─'.repeat(inner) + '┤');

  const pad = (text, len) => {
    const visible = text.replace(/\x1b\[[0-9;]*m/g, '');
    return text + ' '.repeat(Math.max(0, len - visible.length));
  };

  const row = (content) => chalk.cyan('│') + ' ' + pad(content, inner - 1) + chalk.cyan('│');

  console.log();
  console.log(top);
  console.log(row(chalk.bold.white('  ◆ ocha') + chalk.dim.white('  —  multi-agent orchestration')));
  console.log(divider);
  console.log(row(chalk.dim('  Describe your task below.')));
  console.log(row(chalk.dim('  Press ') + chalk.white('Enter') + chalk.dim(' on a blank line to submit, ') + chalk.white('Ctrl+C') + chalk.dim(' to exit.')));
  console.log(bottom);
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
