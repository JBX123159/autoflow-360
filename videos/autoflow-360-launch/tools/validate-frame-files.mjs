#!/usr/bin/env node

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";

function readFlag(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && index + 1 < process.argv.length ? process.argv[index + 1] : fallback;
}

const projectDir = resolve(readFlag("project", "."));
const framesDir = join(projectDir, "compositions", "frames");
const audioMetaPath = join(projectDir, "audio_meta.json");
if (!existsSync(framesDir)) throw new Error(`frames directory not found: ${framesDir}`);
if (!existsSync(audioMetaPath)) throw new Error(`audio metadata not found: ${audioMetaPath}`);

const expectedDurations = new Map(
  JSON.parse(readFileSync(audioMetaPath, "utf8")).voices.map((voice) => [
    Number(voice.frame),
    Number(voice.duration_s),
  ]),
);
const requested = readFlag("frames", "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const files = (requested.length ? requested : readdirSync(framesDir).filter((name) => name.endsWith(".html")))
  .map((name) => (name.endsWith(".html") ? name : `${name}.html`))
  .sort();

const errors = [];
for (const fileName of files) {
  const filePath = join(framesDir, fileName);
  if (!existsSync(filePath)) {
    errors.push(`${fileName}: file missing`);
    continue;
  }
  const source = readFileSync(filePath, "utf8");
  const trimmed = source.trim();
  const frameId = basename(fileName, ".html");
  const frameNumber = Number(frameId.slice(0, 2));
  const expectedDuration = expectedDurations.get(frameNumber);

  if (!/^<template\b/.test(trimmed) || !/<\/template>$/.test(trimmed)) {
    errors.push(`${frameId}: output must be one template fragment`);
  }
  if (/<(?:!doctype|html|head|body)\b/i.test(source)) errors.push(`${frameId}: full-document tag found`);
  if (!source.includes(`data-composition-id="${frameId}"`)) errors.push(`${frameId}: composition id mismatch`);
  if (!/data-start="0(?:\.0+)?"/.test(source)) errors.push(`${frameId}: root data-start is missing`);
  if (!/data-width="1920"/.test(source) || !/data-height="1080"/.test(source)) {
    errors.push(`${frameId}: canvas size mismatch`);
  }
  const durationMatch = source.match(/data-composition-id="[^"]+"[^>]*data-duration="([0-9.]+)"|data-duration="([0-9.]+)"[^>]*data-composition-id="[^"]+"/);
  const rootDuration = Number(durationMatch?.[1] ?? durationMatch?.[2]);
  if (!Number.isFinite(expectedDuration) || Math.abs(rootDuration - expectedDuration) > 0.002) {
    errors.push(`${frameId}: duration ${rootDuration} does not match audio ${expectedDuration}`);
  }
  if (!/assets\/vendor\/gsap\.min\.js/.test(source)) errors.push(`${frameId}: local GSAP is missing`);
  if (!/@font-face[\s\S]*?assets\/fonts\/NotoSansSC-VF\.ttf/.test(source)) {
    errors.push(`${frameId}: local Chinese font is missing`);
  }
  if (!/gsap\.timeline\(\s*\{[^}]*paused\s*:\s*true/.test(source)) {
    errors.push(`${frameId}: paused timeline is missing`);
  }
  const timelineKey = new RegExp(`window\\.__timelines\\s*\\[\\s*["']${frameId}["']\\s*\\]\\s*=`);
  if (!timelineKey.test(source)) errors.push(`${frameId}: timeline registration mismatch`);
  if (/https?:\/\/|@import\b/i.test(source)) errors.push(`${frameId}: remote resource found`);
  if (/<(?:audio|video)\b/i.test(source)) errors.push(`${frameId}: frame-owned audio or video found`);
  if (/Math\.random\s*\(|Date\.now\s*\(|performance\.now\s*\(|repeat\s*:\s*-1/.test(source)) {
    errors.push(`${frameId}: non-deterministic or infinite animation found`);
  }
  if (/\btransition\s*:/.test(source)) errors.push(`${frameId}: CSS transition found`);
  if (/#root\s*\{[^}]*\bbackground(?:-color)?\s*:/s.test(source)) {
    errors.push(`${frameId}: background must not be painted on #root`);
  }

  const clipTags = [...source.matchAll(/<[^>]+class="[^"]*\bclip\b[^"]*"[^>]*>/g)].map((match) => match[0]);
  if (!clipTags.length) errors.push(`${frameId}: no clip layer found`);
  for (const [clipIndex, tag] of clipTags.entries()) {
    for (const attribute of ["data-start", "data-duration", "data-track-index"]) {
      if (!tag.includes(`${attribute}=`)) errors.push(`${frameId}: clip ${clipIndex + 1} missing ${attribute}`);
    }
  }
}

if (errors.length) {
  for (const error of errors) console.error(`frame validation error: ${error}`);
  process.exit(1);
}
console.log(`frame validation: ${files.length} file(s) PASS`);
