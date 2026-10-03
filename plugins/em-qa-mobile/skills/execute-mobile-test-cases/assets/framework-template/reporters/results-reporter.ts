import fs from 'node:fs';
import path from 'node:path';
import { appId, env, platform, ROOT } from '../utils/env';
import { istCell } from '../utils/ist';
import { readDeviceLog, crashLines } from '../helpers/logReader';

/**
 * Writes test-results/<suite>/results.json: one entry per test case ID, merged across re-runs of the same day.
 *   {id, title, file, status, flaky, attempts, startedAt, endedAt, endedAtIst, durationMs, rawError,
 *    evidenceFiles[], manualReason, blockedReason, retestEvidence[], appCrashed, crashLines[], appState}
 * status: passed | failed | manual | blocked.
 * Called from the wdio hooks (beforeTest / afterTest), because evidence needs the device session:
 * - every case is screen-recorded; the recording, a screenshot and the device log excerpt (secrets removed) are
 *   kept in test-results/<suite>/evidence/<ID>/ only when the attempt failed;
 * - RETEST_EVIDENCE=1 (retest of a bug filed in Jira): a case that passes on its FIRST attempt also keeps
 *   retest_screenshot.png and retest_recording.mp4 (retestEvidence[]);
 * - evidence of other passing cases is discarded.
 * Tests whose title has no case ID are stored under "other:<title>".
 */

const ID_RE = /^(TC-[A-Z0-9]+-[A-Z]+-\d{3,})\b/;
const ANSI_RE = /\u001b\[[0-9;]*m/g;

export interface Entry {
  id: string;
  title: string;
  file: string;
  status: 'passed' | 'failed' | 'manual' | 'blocked';
  flaky: boolean;
  attempts: number;
  startedAt: string;
  endedAt: string;
  endedAtIst: string;
  durationMs: number;
  rawError: string;
  evidenceFiles: string[];
  manualReason?: string;
  blockedReason?: string;
  retestEvidence?: string[];
  appCrashed?: boolean;
  crashLines?: string[];
  appState?: string;
}

interface TestLike { title: string; parent?: string; file?: string; fullTitle?: string }
interface ResultLike { passed: boolean; error?: { message?: string; stack?: string }; duration?: number;
  retries?: { attempts: number; limit: number } }

const notes = new Map<string, { manual?: string; blocked?: string }>();
let current: { id: string; startedAt: Date; recording: boolean; attempt: number } | null = null;

export function caseId(title: string): string {
  const m = ID_RE.exec(title.trim());
  return m ? m[1] : `other:${title.trim()}`;
}

/** Suite folder name = the dated folder of the spec: tests/<Suite>_<date>/<flow>.spec.ts */
export function suiteOf(file?: string): string {
  if (process.env.SUITE) return process.env.SUITE;
  if (!file) return 'default';
  const rel = path.relative(path.join(ROOT, 'tests'), file).split(path.sep);
  return rel.length > 1 ? rel[0] : 'default';
}

function resultsDir(file?: string): string {
  return path.join(ROOT, 'test-results', suiteOf(file));
}

function relPath(p: string): string {
  return path.relative(ROOT, p).split(path.sep).join('/');
}

function load(file: string): Record<string, Entry> {
  if (!fs.existsSync(file)) return {};
  try {
    const data = JSON.parse(fs.readFileSync(file, 'utf8')) as { results?: Entry[] };
    return Object.fromEntries((data.results ?? []).map((e) => [e.id, e]));
  } catch {
    return {};
  }
}

function save(file: string, entries: Record<string, Entry>): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  const results = Object.values(entries).sort((a, b) => a.id.localeCompare(b.id));
  fs.writeFileSync(tmp, JSON.stringify({ updated: istCell(), platform: platform(), results }, null, 2));
  fs.renameSync(tmp, file);
}

/** The case needs a person (the device cannot be put in that condition by the script). The case stays PENDING. */
export function manualCheck(reason: string): void {
  if (current) notes.set(current.id, { ...notes.get(current.id), manual: reason });
}

/** The case cannot run in this environment (for example the build lacks the test dependency). */
export function blockedCheck(reason: string): void {
  if (current) notes.set(current.id, { ...notes.get(current.id), blocked: reason });
}

export async function beforeCase(test: TestLike): Promise<void> {
  const id = caseId(test.title);
  const prev = current?.id === id ? current.attempt : 0;
  current = { id, startedAt: new Date(), recording: false, attempt: prev + 1 };
  notes.delete(id);
  try {
    await readDeviceLog(); // drain: the next read returns only this attempt's lines
  } catch { /* logs are optional evidence */ }
  try {
    await driver.startRecordingScreen({ timeLimit: '600', forceRestart: true } as never);
    current.recording = true;
  } catch { /* recording is optional evidence */ }
}

async function stopRecording(): Promise<string> {
  if (!current?.recording) return '';
  try {
    return await driver.stopRecordingScreen();
  } catch {
    return '';
  }
}

async function appStateName(): Promise<string> {
  const id = appId();
  if (!id) return '';
  try {
    const s = Number(await driver.queryAppState(id));
    return ['not installed', 'not running', 'running in background (suspended)', 'running in background',
      'running in foreground'][s] ?? String(s);
  } catch {
    return '';
  }
}

export async function afterCase(test: TestLike, result: ResultLike): Promise<void> {
  const id = caseId(test.title);
  const startedAt = current?.id === id ? current.startedAt : new Date();
  const attempt = (result.retries?.attempts ?? 0) + 1;
  const note = notes.get(id) ?? {};
  const outDir = resultsDir(test.file);
  const evidenceDir = path.join(outDir, 'evidence', id.replace(/[^A-Za-z0-9_.-]/g, '_'));
  const video = await stopRecording();
  let log: string[] = [];
  try {
    log = await readDeviceLog();
  } catch { /* optional */ }
  const crash = crashLines(log, appId());
  const status: Entry['status'] = note.manual ? 'manual' : note.blocked ? 'blocked' : result.passed ? 'passed' : 'failed';

  const file = path.join(outDir, 'results.json');
  const entries = load(file);
  const prev = entries[id];
  const sameRun = prev && prev.status === 'failed' && attempt > 1;
  const evidence: string[] = sameRun ? [...prev.evidenceFiles] : [];
  const retest: string[] = [];
  let appState = '';

  if (status === 'failed') {
    fs.mkdirSync(evidenceDir, { recursive: true });
    const shot = path.join(evidenceDir, `attempt${attempt}_screenshot.png`);
    try {
      await driver.saveScreenshot(shot);
      evidence.push(relPath(shot));
    } catch { /* device may be gone */ }
    if (video) {
      const mp4 = path.join(evidenceDir, `attempt${attempt}_recording.mp4`);
      fs.writeFileSync(mp4, Buffer.from(video, 'base64'));
      evidence.push(relPath(mp4));
    }
    if (log.length) {
      const txt = path.join(evidenceDir, `attempt${attempt}_device-log.txt`);
      fs.writeFileSync(txt, log.slice(-400).join('\n'));
      evidence.push(relPath(txt));
    }
    appState = await appStateName();
  } else if (status === 'passed' && env('RETEST_EVIDENCE') === '1' && attempt === 1) {
    fs.mkdirSync(evidenceDir, { recursive: true });
    const shot = path.join(evidenceDir, 'retest_screenshot.png');
    try {
      await driver.saveScreenshot(shot);
      retest.push(relPath(shot));
    } catch { /* optional */ }
    if (video) {
      const mp4 = path.join(evidenceDir, 'retest_recording.mp4');
      fs.writeFileSync(mp4, Buffer.from(video, 'base64'));
      retest.push(relPath(mp4));
    }
  }

  const ended = new Date();
  const entry: Entry = {
    id,
    title: test.title,
    file: test.file ? relPath(test.file) : '',
    status,
    flaky: status === 'passed' && attempt > 1,
    attempts: attempt,
    startedAt: (sameRun ? new Date(prev.startedAt) : startedAt).toISOString(),
    endedAt: ended.toISOString(),
    endedAtIst: istCell(ended),
    durationMs: ended.getTime() - startedAt.getTime(),
    rawError: (result.error?.message ?? '').replace(ANSI_RE, '').slice(0, 4000),
    evidenceFiles: status === 'passed' && !sameRun ? [] : evidence,
  };
  if (note.manual) entry.manualReason = note.manual;
  if (note.blocked) entry.blockedReason = note.blocked;
  if (retest.length) entry.retestEvidence = retest;
  if (crash.length) {
    entry.appCrashed = true;
    entry.crashLines = crash.slice(0, 40);
  }
  if (appState) entry.appState = appState;
  entries[id] = entry;
  save(file, entries);
  current = null;
}
