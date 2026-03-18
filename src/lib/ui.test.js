import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { stripAnsi, wrapText, progressBar, badge } from './ui.js';

describe('stripAnsi', () => {
  it('passes plain strings through unchanged', () => {
    assert.equal(stripAnsi('hello world'), 'hello world');
  });

  it('removes ANSI colour codes', () => {
    assert.equal(stripAnsi('\x1B[33mhello\x1B[0m'), 'hello');
  });

  it('removes multiple ANSI sequences', () => {
    assert.equal(stripAnsi('\x1B[1m\x1B[34mblue bold\x1B[0m'), 'blue bold');
  });

  it('returns empty string for empty input', () => {
    assert.equal(stripAnsi(''), '');
  });

  it('removes cursor movement and erase sequences', () => {
    assert.equal(stripAnsi('\x1B[2Jhello\x1B[H'), 'hello');
  });

});

describe('wrapText', () => {
  it('returns the text unchanged when it fits on one line', () => {
    assert.deepEqual(wrapText('hello world', 20), ['hello world']);
  });

  it('wraps at word boundaries when text exceeds width', () => {
    // 'one two' = 7, 'three four' = 9 — both fit within width 10.
    const result = wrapText('one two three four', 10);
    assert.deepEqual(result, ['one two', 'three four']);
  });

  it('handles exactly-fitting lines without adding a break', () => {
    assert.deepEqual(wrapText('hello', 5), ['hello']);
  });

  it('puts each word on its own line when width is very small', () => {
    const result = wrapText('a b c', 1);
    assert.deepEqual(result, ['a', 'b', 'c']);
  });

  it('returns [""] for empty string', () => {
    assert.deepEqual(wrapText('', 40), ['']);
  });

  it('returns the full text as one line when width is 0', () => {
    assert.deepEqual(wrapText('hello world', 0), ['hello world']);
  });

  it('collapses internal whitespace between words', () => {
    const result = wrapText('one   two   three', 20);
    assert.deepEqual(result, ['one two three']);
  });

  it('produces multiple lines for a long sentence', () => {
    const text = 'implement user authentication with OAuth2 and session management';
    const lines = wrapText(text, 30);
    for (const line of lines) {
      assert.ok(line.length <= 30, `line too long: "${line}"`);
    }
    assert.equal(lines.join(' '), text);
  });
});

describe('progressBar', () => {
  it('returns a zero-total placeholder when total is 0', () => {
    const result = stripAnsi(progressBar(0, 0, 10));
    assert.ok(result.includes('0/0'), `expected "0/0" in "${result}"`);
  });

  it('returns a fully-filled bar when done equals total', () => {
    const result = stripAnsi(progressBar(5, 5, 10));
    assert.ok(result.includes('5/5'), `expected "5/5" in "${result}"`);
    // no empty blocks expected
    assert.ok(!result.includes('░'), `expected no empty blocks in "${result}"`);
  });

  it('returns a fully-empty bar when done is 0', () => {
    const result = stripAnsi(progressBar(0, 5, 10));
    assert.ok(result.includes('0/5'), `expected "0/5" in "${result}"`);
    assert.ok(!result.includes('█'), `expected no filled blocks in "${result}"`);
  });

  it('produces a partial bar with correct counts', () => {
    const result = stripAnsi(progressBar(3, 10, 10));
    assert.ok(result.includes('3/10'), `expected "3/10" in "${result}"`);
  });

  it('clamps done above total to a full bar', () => {
    const result = stripAnsi(progressBar(99, 5, 10));
    assert.ok(!result.includes('░'), `expected no empty blocks for over-full bar in "${result}"`);
  });
});

describe('badge', () => {
  it('contains the state text for each known state', () => {
    for (const state of ['pending', 'running', 'completed', 'failed', 'stopped']) {
      const result = stripAnsi(badge(state));
      assert.ok(result.includes(state), `badge for "${state}" should contain the state text`);
    }
  });

  it('falls back gracefully for unknown states', () => {
    const result = stripAnsi(badge('unknown'));
    assert.ok(result.includes('unknown'), 'badge should contain the unknown state text');
  });
});
