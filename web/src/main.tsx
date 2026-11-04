// SPDX-FileCopyrightText: 2026 WrinkleByte LLC
// SPDX-License-Identifier: AGPL-3.0-only

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { migrateLegacyDatabase } from './db/migrateLegacyDatabase'

const queryClient = new QueryClient()

async function bootstrap() {
  // Must complete before any component can query the renamed `db` — see
  // migrateLegacyDatabase.ts for why this can't just run lazily.
  await migrateLegacyDatabase()

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

bootstrap()
