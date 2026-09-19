import re

new_base = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#1e3a5f" />
  <meta name="description" content="B2B prospect research and scoring engine" />
  <link rel="manifest" href="/manifest.json" />
  <link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180'><rect fill='%231e3a5f' width='180' height='180'/><text x='50%25' y='50%25' font-size='80' fill='white' dominant-baseline='middle' text-anchor='middle'>C</text></svg>" />
  <title>{% block title %}Coextend Prospect Intelligence{% endblock %}</title>
  <style>
    /* ========================================
       PROFESSIONAL B2B DESIGN SYSTEM
       Inspired by Stripe Dashboard / Linear
       ======================================== */
    
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      /* Light Neutral Base */
      --bg-primary: #ffffff;
      --bg-secondary: #fafbfc;
      --bg-tertiary: #f4f6f8;
      
      /* Surfaces */
      --surface: #ffffff;
      --surface-elevated: #ffffff;
      --surface-overlay: #f8f9fa;
      
      /* Borders */
      --border: #e3e8ed;
      --border-strong: #d1d9e0;
      --divider: #e3e8ed;
      
      /* Navy/Steel Blue Accent - Engineering Trust */
      --accent-primary: #1e3a5f;
      --accent-hover: #2c5282;
      --accent-light: #e8f0fe;
      --accent-lighter: #f5f8ff;
      
      /* Text */
      --text-primary: #1f2937;
      --text-secondary: #4b5563;
      --text-tertiary: #6b7280;
      --text-muted: #9ca3af;
      --text-light: #d1d5db;
      
      /* Priority Bands - Subtle */
      --high: #057a55;
      --high-bg: #ecfdf5;
      --high-border: #a7f3d0;
      --medium: #b45309;
      --medium-bg: #fffbeb;
      --medium-border: #fcd34d;
      --low: #6b7280;
      --low-bg: #f9fafb;
      --low-border: #e5e7eb;
      
      /* Confidence Labels */
      --verified: #057a55;
      --verified-bg: #ecfdf5;
      --probable: #b45309;
      --probable-bg: #fffbeb;
      --unverified: #dc2626;
      --unverified-bg: #fef2f2;
      
      /* Spacing Scale */
      --space-1: 4px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --space-5: 20px;
      --space-6: 24px;
      --space-8: 32px;
      --space-10: 40px;
      
      /* Typography */
      --font-stack: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
      --text-sm: 13px;
      --text-base: 14px;
      --text-lg: 16px;
      --text-xl: 18px;
      --text-2xl: 20px;
      
      /* Radii */
      --radius: 6px;
      --radius-lg: 8px;
      --radius-xl: 12px;
      
      /* Shadows */
      --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.04);
      --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
      --shadow: 0 2px 4px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
      --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04);
    }

    body {
      background: var(--bg-secondary);
      color: var(--text-primary);
      font-family: var(--font-stack);
      font-size: var(--text-base);
      line-height: 1.5;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    a { color: var(--accent-primary); text-decoration: none; transition: color 0.15s; }
    a:hover { color: var(--accent-hover); }

    /* ========================================
       HEADER
       ======================================== */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0 var(--space-6);
      height: 60px;
      display: flex;
      align-items: center;
      gap: var(--space-4);
      position: sticky;
      top: 0;
      z-index: 100;
    }

    header .logo {
      font-size: var(--text-lg);
      font-weight: 600;
      color: var(--accent-primary);
      letter-spacing: -0.01em;
    }

    header .tagline {
      font-size: var(--text-sm);
      color: var(--text-tertiary);
      margin-left: var(--space-2);
    }

    header nav {
      margin-left: auto;
      display: flex;
      gap: var(--space-6);
      font-size: var(--text-base);
    }

    header nav a {
      color: var(--text-secondary);
      font-weight: 500;
    }

    header nav a:hover {
      color: var(--accent-primary);
    }

    /* ========================================
       MAIN LAYOUT
       ======================================== */
    main {
      max-width: 980px;
      margin: 0 auto;
      padding: var(--space-8) var(--space-6);
    }

    /* ========================================
       CARDS
       ======================================== */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: var(--space-6);
      margin-bottom: var(--space-4);
      box-shadow: var(--shadow-xs);
    }

    .card h2 {
      font-size: var(--text-lg);
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: var(--space-4);
      letter-spacing: -0.01em;
    }

    /* ========================================
       TYPOGRAPHY
       ======================================== */
    .section-title {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: var(--space-3);
    }

    p { margin-bottom: var(--space-3); line-height: 1.6; }
    ul, ol { padding-left: var(--space-5); }
    li { margin-bottom: var(--space-2); }

    /* ========================================
       FORMS
       ======================================== */
    label {
      display: block;
      font-size: var(--text-sm);
      font-weight: 500;
      color: var(--text-secondary);
      margin-bottom: var(--space-2);
      margin-top: var(--space-4);
    }
    label:first-of-type { margin-top: 0; }

    input[type="text"],
    input[type="url"],
    textarea,
    select {
      width: 100%;
      padding: var(--space-3) var(--space-4);
      background: var(--bg-primary);
      border: 1px solid var(--border-strong);
      border-radius: var(--radius);
      color: var(--text-primary);
      font-family: var(--font-stack);
      font-size: var(--text-base);
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }

    input:focus,
    textarea:focus,
    select:focus {
      border-color: var(--accent-primary);
      box-shadow: 0 0 0 3px var(--accent-lighter);
    }

    input::placeholder,
    textarea::placeholder {
      color: var(--text-light);
    }

    textarea {
      resize: vertical;
      min-height: 80px;
    }

    /* ========================================
       BUTTONS
       ======================================== */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--space-2);
      margin-top: var(--space-5);
      padding: var(--space-3) var(--space-5);
      background: var(--accent-primary);
      color: #ffffff;
      border: none;
      border-radius: var(--radius);
      font-family: var(--font-stack);
      font-size: var(--text-base);
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s, transform 0.05s;
    }

    .btn:hover { background: var(--accent-hover); }
    .btn:active { transform: translateY(1px); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    .btn-outline {
      background: transparent;
      border: 1px solid var(--border-strong);
      color: var(--text-secondary);
    }

    .btn-outline:hover {
      background: var(--bg-tertiary);
      border-color: var(--text-muted);
      color: var(--text-primary);
    }

    /* ========================================
       ALERTS
       ======================================== */
    .alert {
      padding: var(--space-3) var(--space-4);
      border-radius: var(--radius);
      font-size: var(--text-sm);
      margin-bottom: var(--space-4);
      border: 1px solid transparent;
    }

    .alert-warning {
      background: var(--medium-bg);
      border-color: var(--medium-border);
      color: #78350f;
    }

    .alert-error {
      background: var(--unverified-bg);
      border-color: #fecaca;
      color: #991b1b;
    }

    .alert-info {
      background: var(--accent-lighter);
      border-color: #bfdbfe;
      color: #1e40af;
    }

    /* ========================================
       BADGES
       ======================================== */
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.01em;
    }

    .badge-verified { background: var(--verified-bg); color: var(--verified); }
    .badge-probable { background: var(--probable-bg); color: var(--probable); }
    .badge-unverified { background: var(--unverified-bg); color: var(--unverified); }
    .badge-high { background: var(--high-bg); color: var(--high); }
    .badge-medium { background: var(--medium-bg); color: var(--medium); }
    .badge-low { background: var(--low-bg); color: var(--low); }
    .badge-draft { background: var(--accent-lighter); color: var(--accent-primary); }

    /* ========================================
       SCORE CIRCLE
       ======================================== */
    .score-circle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 64px;
      height: 64px;
      border-radius: 50%;
      border: 2px solid var(--accent-primary);
      font-size: 24px;
      font-weight: 700;
      color: var(--accent-primary);
      background: var(--surface);
    }

    /* ========================================
       KV GRID
       ======================================== */
    .kv-grid {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: var(--space-2) var(--space-4);
      font-size: var(--text-sm);
    }

    .kv-key { color: var(--text-tertiary); font-weight: 500; }
    .kv-val { color: var(--text-primary); }

    /* ========================================
       TABLES
       ======================================== */
    table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }

    th {
      text-align: left;
      padding: var(--space-3);
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      background: var(--bg-tertiary);
    }

    td {
      padding: var(--space-3);
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }

    tbody tr:last-child td { border-bottom: none; }
    tbody tr:hover { background: var(--bg-tertiary); }

    /* ========================================
       TABS
       ======================================== */
    .tabs {
      display: flex;
      gap: 0;
      margin-bottom: var(--space-4);
      border-bottom: 1px solid var(--border);
    }

    .tab {
      padding: var(--space-3) var(--space-5);
      border: none;
      border-bottom: 2px solid transparent;
      background: none;
      cursor: pointer;
      font-size: var(--text-base);
      font-weight: 500;
      color: var(--text-tertiary);
      transition: color 0.15s, border-color 0.15s;
      margin-bottom: -1px;
    }

    .tab:hover { color: var(--text-secondary); }
    .tab.active { color: var(--accent-primary); border-bottom-color: var(--accent-primary); }

    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    /* ========================================
       PRE / CODE
       ======================================== */
    pre {
      background: var(--bg-tertiary);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: var(--space-4);
      font-size: var(--text-sm);
      font-family: 'SF Mono', Monaco, 'Courier New', monospace;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.6;
      color: var(--text-primary);
    }

    /* ========================================
       FOOTER
       ======================================== */
    footer {
      text-align: center;
      font-size: var(--text-sm);
      color: var(--text-muted);
      padding: var(--space-8) var(--space-6);
      border-top: 1px solid var(--border);
      margin-top: var(--space-10);
      background: var(--bg-secondary);
    }

    /* ========================================
       RESPONSIVE - MOBILE (390px)
       ======================================== */
    @media (max-width: 767px) {
      body { font-size: var(--text-base); }

      header {
        padding: var(--space-4);
        height: auto;
        min-height: 56px;
        flex-direction: column;
        align-items: flex-start;
        gap: var(--space-2);
      }

      header nav { margin-left: 0; gap: var(--space-4); }

      main { padding: var(--space-4); }

      .card { padding: var(--space-4); margin-bottom: var(--space-3); }
      .card h2 { font-size: var(--text-base); }

      .btn { width: 100%; padding: var(--space-3); }

      .score-circle { width: 56px; height: 56px; font-size: 20px; border-width: 2px; }

      .kv-grid { grid-template-columns: 1fr; gap: var(--space-2); }

      table { font-size: var(--text-sm); }
      th, td { padding: var(--space-2); }

      .tabs { overflow-x: auto; -webkit-overflow-scrolling: touch; }
      .tab { padding: var(--space-3) var(--space-4); font-size: var(--text-sm); white-space: nowrap; }
    }

    /* ========================================
       RESPONSIVE - TABLET (768px+)
       ======================================== */
    @media (min-width: 768px) {
      main { max-width: 960px; padding: var(--space-8) var(--space-6); }
    }

    /* ========================================
       RESPONSIVE - DESKTOP (1440px+)
       ======================================== */
    @media (min-width: 1440px) {
      main { max-width: 1100px; padding: var(--space-10); }
      .card { padding: var(--space-8); }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <span class="logo">Coextend</span>
      <span class="tagline">Prospect Intelligence</span>
    </div>
    <nav>
      <a href="/">New Prospect</a>
      <a href="/docs" target="_blank">API Docs</a>
    </nav>
  </header>

  <main>
    {% block content %}{% endblock %}
  </main>

  <footer>
    Coextend Prospect Intelligence · Drafts require human review · No automated outreach
  </footer>

  <script>
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js').catch(e => {
        console.log('Service Worker registration failed:', e);
      });
    }
  </script>
</body>
</html>'''

with open("ui/templates/base.html", "w", encoding="utf-8") as f:
    f.write(new_base)

print("✓ Updated base.html with refined B2B professional design")
