/**
 * @module test-reporter
 * A custom Node.js test reporter that renders colourful, readable output
 * using chalk. Wire it up via:  --test-reporter=./src/lib/test-reporter.js
 */
import chalk from 'chalk';

const PASS  = chalk.bgGreen.black(' PASS ');
const FAIL  = chalk.bgRed.white(' FAIL ');
const SKIP  = chalk.bgYellow.black(' SKIP ');
const TODO  = chalk.bgCyan.black(' TODO ');

const icon = {
  pass: chalk.green('✔'),
  fail: chalk.red('✖'),
  skip: chalk.yellow('⊘'),
  todo: chalk.cyan('☐'),
};

let suiteDepth   = 0;
let totalPass    = 0;
let totalFail    = 0;
let totalSkip    = 0;
let totalTodo    = 0;
const startTime  = Date.now();

/**
 * Indentation helper.
 * @param {number} depth
 * @returns {string}
 */
function indent(depth) {
  return '  '.repeat(depth);
}

/**
 * Format milliseconds into a readable string.
 * @param {number} ms
 * @returns {string}
 */
function formatDuration(ms) {
  if (ms < 1000) return chalk.gray(`${ms}ms`);
  return chalk.gray(`${(ms / 1000).toFixed(2)}s`);
}

/**
 * The reporter is an async generator that receives TestEvent objects from the
 * Node.js test runner and yields strings to stdout.
 *
 * @param {AsyncIterable<object>} source
 */
export default async function* reporter(source) {
  yield '\n';

  for await (const event of source) {
    const { type, data } = event;

    switch (type) {
      case 'test:start': {
        if (data.name && suiteDepth === 0) {
          // top-level suite or test file heading
        }
        break;
      }

      case 'test:pass': {
        const depth = data.nesting ?? 0;
        if (data.skip) {
          totalSkip++;
          yield `${indent(depth)}${icon.skip} ${chalk.yellow(data.name)} ${SKIP}\n`;
        } else if (data.todo) {
          totalTodo++;
          yield `${indent(depth)}${icon.todo} ${chalk.cyan(data.name)} ${TODO}\n`;
        } else {
          totalPass++;
          const dur = data.details?.duration_ms !== null && data.details?.duration_ms !== undefined
            ? ` ${formatDuration(Math.round(data.details.duration_ms))}`
            : '';
          yield `${indent(depth)}${icon.pass} ${chalk.green(data.name)}${dur}\n`;
        }
        break;
      }

      case 'test:fail': {
        const depth = data.nesting ?? 0;
        totalFail++;
        const dur = data.details?.duration_ms !== null && data.details?.duration_ms !== undefined
          ? ` ${formatDuration(Math.round(data.details.duration_ms))}`
          : '';
        yield `${indent(depth)}${icon.fail} ${chalk.red.bold(data.name)}${dur} ${FAIL}\n`;

        // Print error details
        const err = data.details?.error;
        if (err) {
          const msg = err.message ?? String(err);
          for (const line of msg.split('\n')) {
            yield `${indent(depth + 1)}${chalk.red(line)}\n`;
          }
          if (err.cause?.stack) {
            const stackLines = String(err.cause.stack).split('\n').slice(0, 5);
            for (const line of stackLines) {
              yield `${indent(depth + 2)}${chalk.gray(line)}\n`;
            }
          }
        }
        break;
      }

      case 'test:plan': {
        suiteDepth = Math.max(0, suiteDepth - 1);
        break;
      }

      case 'test:diagnostic': {
        // suppress built-in summary lines (they start with "tests ", "pass ", etc.)
        const msg = String(data.message ?? '');
        if (/^(tests|pass|fail|cancelled|skipped|todo)\s+\d/.test(msg)) break;
        yield `${chalk.gray('  # ' + msg)}\n`;
        break;
      }

      case 'test:stderr': {
        yield chalk.red(data.message);
        break;
      }

      case 'test:stdout': {
        yield chalk.gray(data.message);
        break;
      }

      default:
        break;
    }
  }

  // ── Summary ─────────────────────────────────────────────────────────────
  const elapsed = Date.now() - startTime;
  const divider = chalk.gray('─'.repeat(50));

  yield `\n${divider}\n`;

  const parts = [
    totalPass > 0 ? chalk.green(`${totalPass} passed`) : null,
    totalFail > 0 ? chalk.red(`${totalFail} failed`) : null,
    totalSkip > 0 ? chalk.yellow(`${totalSkip} skipped`) : null,
    totalTodo > 0 ? chalk.cyan(`${totalTodo} todo`) : null,
  ].filter(Boolean);

  const overallBadge = totalFail > 0 ? FAIL : PASS;
  yield `${overallBadge}  ${parts.join(chalk.gray('  ·  '))}  ${formatDuration(elapsed)}\n\n`;
}
