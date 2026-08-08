#!/usr/bin/env node

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

function readFlag(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && index + 1 < process.argv.length ? process.argv[index + 1] : fallback;
}

function fail(message) {
  console.error(`caption timing error: ${message}`);
  process.exit(1);
}

function roundTime(value) {
  return Number(value.toFixed(3));
}

function parseScript(markdown) {
  const lines = [];
  let current = null;

  const flush = () => {
    if (current?.text.trim()) {
      lines.push({ frame: current.frame, text: current.text.trim() });
    }
    current = null;
  };

  for (const line of markdown.split(/\r?\n/)) {
    const heading = line.match(/^#{2,3}\s+.*?\(frame\s+(\d+)\)/i);
    if (heading) {
      flush();
      current = { frame: Number(heading[1]), text: "" };
      continue;
    }
    if (!current || /^\s*\*\*/.test(line)) continue;
    const spoken = line.match(/^(?: {4,}|\t)(.+)$/);
    if (spoken) current.text += `${current.text ? " " : ""}${spoken[1].trim()}`;
  }
  flush();
  return lines;
}

function splitLongPhrase(phrase, maximumCharacters = 18) {
  const trimmed = phrase.trim();
  if (Array.from(trimmed).length <= maximumCharacters) return [trimmed];

  // Keep Latin product names such as AutoFlow and Frappe intact when a long
  // Chinese phrase has to wrap into multiple subtitle units.
  const tokens = trimmed.match(/[A-Za-z0-9][A-Za-z0-9._+-]*|\s+|./gu) ?? [];
  const parts = [];
  let current = "";
  let currentLength = 0;
  for (const token of tokens) {
    const tokenLength = Array.from(token).length;
    if (current && currentLength + tokenLength > maximumCharacters) {
      parts.push(current.trim());
      current = token.trimStart();
      currentLength = Array.from(current).length;
      continue;
    }
    current += token;
    currentLength += tokenLength;
  }
  if (current.trim()) parts.push(current.trim());
  return parts.filter(Boolean);
}

function splitIntoPhrases(text) {
  const normalized = text.replace(/\s+/g, " ").trim();
  const clauses = normalized.match(/[^，。！？；：,.!?;:]+[，。！？；：,.!?;:]?/g) ?? [];
  return clauses.flatMap((clause) => splitLongPhrase(clause)).filter(Boolean);
}

function phraseWeight(text) {
  return Math.max(1, Array.from(text.replace(/[\s，。！？；：、,.!?;:]/g, "")).length);
}

function buildTimings(text, durationSeconds) {
  const phrases = splitIntoPhrases(text);
  if (!phrases.length) fail("script line contains no usable spoken text");
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    fail(`invalid voice duration: ${durationSeconds}`);
  }

  const leadSeconds = Math.min(0.12, durationSeconds * 0.05);
  const tailSeconds = Math.min(0.12, durationSeconds * 0.05);
  const preferredGap = 0.22;
  const maximumGapTotal = Math.max(0, durationSeconds - leadSeconds - tailSeconds - 0.4 * phrases.length);
  const gapSeconds = phrases.length > 1
    ? Math.min(preferredGap, maximumGapTotal / (phrases.length - 1))
    : 0;
  const speakingSeconds = durationSeconds - leadSeconds - tailSeconds - gapSeconds * (phrases.length - 1);
  if (speakingSeconds <= 0) fail(`voice duration is too short for ${phrases.length} subtitle phrases`);

  const weights = phrases.map(phraseWeight);
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  let cursor = leadSeconds;

  return phrases.map((phrase, index) => {
    const phraseDuration = speakingSeconds * (weights[index] / totalWeight);
    const start = roundTime(cursor);
    const end = roundTime(Math.min(durationSeconds - tailSeconds, cursor + phraseDuration));
    cursor += phraseDuration + gapSeconds;
    return { id: `w${index}`, text: phrase, start, end };
  });
}

const scriptPath = resolve(readFlag("script", "./SCRIPT.md"));
const audioMetaPath = resolve(readFlag("audio-meta", "./audio_meta.json"));

if (!existsSync(scriptPath)) fail(`SCRIPT.md not found: ${scriptPath}`);
if (!existsSync(audioMetaPath)) fail(`audio_meta.json not found: ${audioMetaPath}`);

const scriptLines = parseScript(readFileSync(scriptPath, "utf8"));
const audioMeta = JSON.parse(readFileSync(audioMetaPath, "utf8"));
if (!Array.isArray(audioMeta.voices) || audioMeta.voices.length === 0) {
  fail("audio metadata contains no voice entries");
}

const scriptByFrame = new Map(scriptLines.map((line) => [line.frame, line.text]));
let phraseCount = 0;

for (const voice of audioMeta.voices) {
  const text = scriptByFrame.get(Number(voice.frame));
  if (!text) fail(`missing locked narration for frame ${voice.frame}`);
  voice.words = buildTimings(text, Number(voice.duration_s));
  phraseCount += voice.words.length;
}

const missingFrames = scriptLines.filter(
  (line) => !audioMeta.voices.some((voice) => Number(voice.frame) === line.frame),
);
if (missingFrames.length) {
  fail(`audio metadata is missing frames: ${missingFrames.map((line) => line.frame).join(", ")}`);
}

writeFileSync(audioMetaPath, `${JSON.stringify(audioMeta, null, 2)}\n`, "utf8");
console.log(`caption timings: ${phraseCount} phrase(s) across ${audioMeta.voices.length} frame(s)`);
