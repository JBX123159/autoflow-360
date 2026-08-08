#!/usr/bin/env node

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

function readFlag(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && index + 1 < process.argv.length ? process.argv[index + 1] : fallback;
}

function fail(message) {
  console.error(`storyboard retime error: ${message}`);
  process.exit(1);
}

function formatTime(value) {
  return value.toFixed(3).replace(/\.0+$/, ".0").replace(/(\.\d*?)0+$/, "$1");
}

const storyboardPath = resolve(readFlag("storyboard", "./STORYBOARD.md"));
if (!existsSync(storyboardPath)) fail(`STORYBOARD.md not found: ${storyboardPath}`);

const source = readFileSync(storyboardPath, "utf8");
const frameHeading = /^## Frame (\d+)\b.*$/gm;
const headings = [...source.matchAll(frameHeading)];
if (!headings.length) fail("no frame headings found");

let output = "";
let cursor = 0;
let retimedFrames = 0;

for (let index = 0; index < headings.length; index += 1) {
  const heading = headings[index];
  const blockStart = heading.index;
  const blockEnd = index + 1 < headings.length ? headings[index + 1].index : source.length;
  const block = source.slice(blockStart, blockEnd);
  const durationMatch = block.match(/^- duration:\s*([0-9.]+)s\s*$/m);
  if (!durationMatch) fail(`frame ${heading[1]} has no duration`);
  const duration = Number(durationMatch[1]);
  if (!Number.isFinite(duration) || duration <= 0) fail(`frame ${heading[1]} has invalid duration`);

  const scenePattern = /(Scene\s+\d+\s+\()([0-9.]+)(\s*[–-]\s*)([0-9.]+)(s\):)/g;
  const scenes = [...block.matchAll(scenePattern)];
  if (!scenes.length) fail(`frame ${heading[1]} has no time-coded scenes`);
  const originalEnd = Number(scenes.at(-1)[4]);
  if (!Number.isFinite(originalEnd) || originalEnd <= 0) {
    fail(`frame ${heading[1]} has an invalid final scene time`);
  }

  const scale = duration / originalEnd;
  let sceneIndex = 0;
  const retimedBlock = block.replace(scenePattern, (match, prefix, startText, dash, endText, suffix) => {
    const isLast = sceneIndex === scenes.length - 1;
    const start = Number(startText) * scale;
    const end = isLast ? duration : Number(endText) * scale;
    sceneIndex += 1;
    return `${prefix}${formatTime(start)}${dash}${formatTime(end)}${suffix}`;
  });

  output += source.slice(cursor, blockStart);
  output += retimedBlock;
  cursor = blockEnd;
  retimedFrames += 1;
}

output += source.slice(cursor);
writeFileSync(storyboardPath, output, "utf8");

const verification = readFileSync(storyboardPath, "utf8");
const verifiedHeadings = [...verification.matchAll(frameHeading)];
for (let index = 0; index < verifiedHeadings.length; index += 1) {
  const heading = verifiedHeadings[index];
  const blockEnd = index + 1 < verifiedHeadings.length ? verifiedHeadings[index + 1].index : verification.length;
  const block = verification.slice(heading.index, blockEnd);
  const duration = Number(block.match(/^- duration:\s*([0-9.]+)s\s*$/m)?.[1]);
  const scenes = [...block.matchAll(/Scene\s+\d+\s+\(([0-9.]+)\s*[–-]\s*([0-9.]+)s\):/g)];
  if (!scenes.length) fail(`verification found no scenes in frame ${heading[1]}`);
  if (Math.abs(Number(scenes[0][1])) > 0.001) fail(`frame ${heading[1]} does not start at 0`);
  for (let sceneIndex = 1; sceneIndex < scenes.length; sceneIndex += 1) {
    if (Math.abs(Number(scenes[sceneIndex][1]) - Number(scenes[sceneIndex - 1][2])) > 0.002) {
      fail(`frame ${heading[1]} has a gap or overlap before scene ${sceneIndex + 1}`);
    }
  }
  if (Math.abs(Number(scenes.at(-1)[2]) - duration) > 0.002) {
    fail(`frame ${heading[1]} does not cover its synced duration`);
  }
}

console.log(`storyboard retime: ${retimedFrames} frame(s) now cover synced voice durations`);
