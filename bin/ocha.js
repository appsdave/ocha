#!/usr/bin/env node
import { program } from 'commander';
import { cordStart } from '../src/commands/cord-start.js';
import { cordStatus } from '../src/commands/cord-status.js';
import { cordStop } from '../src/commands/cord-stop.js';
import { ochaInit } from '../src/commands/init.js';

program
  .name('ocha')
  .description('Orchestrate Junie agents across git worktrees')
  .version('1.0.0');

program
  .command('init')
  .description('Initialize .ocha/ directory with role prompts and config')
  .action(ochaInit);

const cord = program.command('cord').description('Coordinator commands');

cord
  .command('start')
  .description('Start a coordinator session')
  .requiredOption('-t, --task <task>', 'High-level task description')
  .option('-b, --base-branch <branch>', 'Base branch to create worktrees from', 'main')
  .option('--max-agents <n>', 'Maximum parallel agents', '3')
  .action(cordStart);

cord
  .command('status')
  .description('Check coordinator progress')
  .action(cordStatus);

cord
  .command('stop')
  .description('Stop the coordinator and all agents')
  .action(cordStop);

program.parse();
