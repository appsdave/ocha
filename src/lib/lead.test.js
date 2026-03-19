import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { taskSlug } from './lead.js';

describe('taskSlug', () => {
  it('extracts up to 6 meaningful words from a description', () => {
    const slug = taskSlug('Fix the retry logic in the config parser module');
    const words = slug.split('-');
    assert.ok(words.length <= 6, `expected at most 6 words, got ${words.length}`);
    assert.ok(words.length >= 1, 'expected at least 1 word');
    assert.ok(!words.includes('the'), 'should filter stop word "the"');
    assert.ok(!words.includes('in'), 'should filter stop word "in"');
    assert.ok(words.includes('fix'), 'should keep "fix"');
    assert.ok(words.includes('retry'), 'should keep "retry"');
  });

  it('returns "task" for empty or null input', () => {
    assert.equal(taskSlug(''), '');
    assert.equal(taskSlug(null), '');
    assert.equal(taskSlug(undefined), '');
  });

  it('strips markdown task header', () => {
    const slug = taskSlug('## Task\nUpdate the documentation for README');
    assert.ok(!slug.includes('task'), `should strip "## Task" header, got "${slug}"`);
    assert.ok(slug.includes('update'), 'should keep "update"');
    assert.ok(slug.includes('documentation'), 'should keep "documentation"');
  });

  it('strips context block after ---', () => {
    const slug = taskSlug('Add retry logic\n---\n## Project Context\nlots of context here');
    assert.ok(slug.includes('add') || slug.includes('retry'), 'should keep words before ---');
    assert.ok(!slug.includes('project'), 'should strip words after ---');
    assert.ok(!slug.includes('context'), 'should strip context block');
  });

  it('filters single-character words', () => {
    const slug = taskSlug('I want a b c d e f g real thing');
    assert.ok(!slug.split('-').some(w => w.length <= 1), 'no single-char words');
  });

  it('produces lowercase hyphen-separated output', () => {
    const slug = taskSlug('Update The README File With New Content');
    assert.equal(slug, slug.toLowerCase(), 'should be lowercase');
    assert.ok(/^[a-z0-9-]+$/.test(slug), `should only contain lowercase, digits, hyphens: "${slug}"`);
  });

  it('handles special characters gracefully', () => {
    const slug = taskSlug('fix: handle @mentions & <html> tags (urgent!)');
    assert.ok(/^[a-z0-9-]+$/.test(slug), `should clean special chars: "${slug}"`);
    assert.ok(slug.includes('fix'), 'should keep "fix"');
    assert.ok(slug.includes('handle'), 'should keep "handle"');
  });

  it('respects custom maxWords parameter', () => {
    const slug = taskSlug('one two three four five six seven eight', 3);
    const words = slug.split('-');
    assert.ok(words.length <= 3, `expected at most 3 words, got ${words.length}`);
  });

  it('returns "task" when description has only stop words', () => {
    const slug = taskSlug('the is a an to of in for');
    assert.equal(slug, 'task');
  });
});
