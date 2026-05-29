import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// HashRouter (not BrowserRouter): the Power Apps Code Apps player serves the
// bundle from a deep, unpredictable `…/storageproxy/…/index.html` path, so
// path-based routing matches no route and renders blank. Hash routing is
// independent of the host path.
import { HashRouter } from 'react-router-dom'
import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <FluentProvider theme={webLightTheme}>
      <HashRouter>
        <App />
      </HashRouter>
    </FluentProvider>
  </StrictMode>,
)
