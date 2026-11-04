#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

// Captures one PNG of this app's dev server via Playwright — for attaching
// visual evidence to a Vikunja "Needs Review" card, not a visual-regression
// suite. Spins up `vite` itself so it can run unattended (no separately
// running dev server required), then tears it down.
//
// Usage: node scripts/screenshot.mjs [--path /some/route] [--out shot.png] [--port 5173]
//
// First run needs the Chromium binary: `npx playwright install chromium`.
//
// Note: routes behind SetupGate (src/features/auth/SetupGate.tsx) render
// whatever the app shows without a reachable backend (loading/setup state,
// not the feature UI) unless VITE_API_PROXY_TARGET points at a running
// backend — see vite.config.ts. That's expected, not a script bug.

import { spawn } from 'node:child_process'
import { chromium } from 'playwright'

function parseArgs(argv) {
  const opts = { path: '/', out: 'screenshot.png', port: '5173' }
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i].replace(/^--/, '')
    if (key in opts) opts[key] = argv[++i]
  }
  return opts
}

async function waitForServer(url, timeoutMs = 30_000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url)
      if (res.ok || res.status < 500) return
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 300))
  }
  throw new Error(`Dev server at ${url} did not become ready within ${timeoutMs}ms`)
}

async function main() {
  const { path, out, port } = parseArgs(process.argv.slice(2))
  const base = `http://localhost:${port}`

  const vite = spawn('npx', ['vite', '--port', port, '--strictPort'], {
    cwd: new URL('..', import.meta.url).pathname,
    stdio: 'pipe',
  })
  vite.stdout.on('data', (d) => process.stderr.write(d))
  vite.stderr.on('data', (d) => process.stderr.write(d))
  vite.on('error', (err) => console.error('vite spawn error:', err))

  try {
    await waitForServer(base)

    const browser = await chromium.launch()
    try {
      const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
      await page.goto(`${base}${path}`, { waitUntil: 'networkidle' })
      await page.screenshot({ path: out, fullPage: true })
      console.log(`Saved screenshot to ${out}`)
    } finally {
      await browser.close()
    }
  } finally {
    vite.kill()
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
