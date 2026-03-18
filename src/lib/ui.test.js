import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { stripAnsi, wrapText } from './ui.js';

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
