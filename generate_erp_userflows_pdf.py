#!/usr/bin/env python3
"""
Axon ERP - Detailed Module User Flows & Operator Journeys Guide
Compiles a publication-grade technical PDF detailing screen-by-screen human-computer interaction,
UI controls, forms, modals, validation mechanisms, and cross-persona handoffs across all 18 ERP modules.
"""

import os
import sys
import weasyprint

def get_userflow_css():
    return """
    @page {
        size: A4;
        margin: 16mm 14mm 16mm 14mm;
        @top-left {
            content: "AXON ERP | OPERATOR USER FLOW GUIDE";
            font-size: 7.5pt;
            font-weight: 700;
            color: #64748b;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            letter-spacing: 0.05em;
        }
        @top-right {
            content: "SCREEN INTERACTIONS & OPERATOR JOURNEYS";
            font-size: 7.5pt;
            font-weight: 600;
            color: #64748b;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        @bottom-left {
            content: "CONFIDENTIAL & PROPRIETARY — UX & SYSTEM INTERACTION REFERENCE";
            font-size: 7pt;
            color: #94a3b8;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        @bottom-right {
            content: "Page " counter(page) " of " counter(pages);
            font-size: 7.5pt;
            font-weight: 700;
            color: #475569;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
    }

    @page:first {
        margin: 0;
        @top-left { content: none; }
        @top-right { content: none; }
        @bottom-left { content: none; }
        @bottom-right { content: none; }
    }

    * {
        box-sizing: border-box;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        line-height: 1.45;
        font-size: 8.5pt;
        margin: 0;
        padding: 0;
    }

    .cover-page {
        page-break-after: always;
        height: 100vh;
        background: linear-gradient(135deg, #090d16 0%, #111827 50%, #030712 100%);
        color: #ffffff;
        padding: 60mm 20mm 30mm 25mm;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
    }

    .cover-brand {
        display: inline-block;
        padding: 6px 14px;
        background: rgba(99, 102, 241, 0.25);
        border: 1px solid rgba(129, 140, 248, 0.5);
        border-radius: 6px;
        font-size: 9pt;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        font-weight: 800;
        color: #a5b4fc;
        margin-bottom: 24px;
    }

    .cover-title {
        font-size: 28pt;
        font-weight: 900;
        line-height: 1.15;
        letter-spacing: -0.02em;
        color: #ffffff;
        margin: 0 0 16px 0;
    }

    .cover-subtitle {
        font-size: 13pt;
        line-height: 1.4;
        color: #94a3b8;
        font-weight: 400;
        max-width: 520px;
        margin: 0 0 40px 0;
    }

    .cover-accent-bar {
        width: 70px;
        height: 4px;
        background: linear-gradient(90deg, #6366f1, #38bdf8);
        border-radius: 2px;
        margin-bottom: 40px;
    }

    .cover-meta-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        padding-top: 24px;
        max-width: 500px;
    }

    .meta-item-label {
        font-size: 7.5pt;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        margin-bottom: 3px;
        font-weight: 700;
    }

    .meta-item-val {
        font-size: 9pt;
        color: #f1f5f9;
        font-weight: 600;
    }

    .cover-footer {
        font-size: 7.5pt;
        color: #64748b;
        margin-top: 50px;
    }

    .page {
        page-break-after: always;
    }

    h1 {
        font-size: 18pt;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 10px 0;
        letter-spacing: -0.02em;
    }

    h2 {
        font-size: 13pt;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 8px 0;
        border-bottom: 2px solid #4f46e5;
        padding-bottom: 4px;
        letter-spacing: -0.01em;
    }

    h3 {
        font-size: 9pt;
        font-weight: 700;
        color: #1e293b;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 8px 0 4px 0;
    }

    p {
        margin: 0 0 6px 0;
        color: #334155;
    }

    .badge {
        display: inline-block;
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 7pt;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        vertical-align: middle;
    }

    .badge-indigo { background: #e0e7ff; color: #3730a3; border: 1px solid #a5b4fc; }
    .badge-cyan { background: #cffafe; color: #155e75; border: 1px solid #67e8f9; }
    .badge-emerald { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
    .badge-amber { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
    .badge-slate { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }

    .module-header {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #4f46e5;
        border-radius: 6px;
        padding: 7px 12px;
        margin-bottom: 8px;
    }

    .module-header-title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 3px;
    }

    .module-title-text {
        font-size: 12.5pt;
        font-weight: 800;
        color: #0f172a;
    }

    .module-meta-strip {
        display: flex;
        gap: 16px;
        font-size: 7.5pt;
        color: #475569;
    }

    .module-meta-strip strong {
        color: #0f172a;
    }

    .svg-container {
        width: 100%;
        margin: 6px 0 8px 0;
        text-align: center;
    }

    .svg-container svg {
        max-width: 100%;
        height: auto;
    }

    .grid-2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-bottom: 8px;
    }

    .grid-3 {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 8px;
        margin-bottom: 8px;
    }

    .card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 6px 10px;
    }

    .card-title {
        font-size: 7.8pt;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .card-indigo { border-top: 3px solid #4f46e5; background: #faf5ff; }
    .card-indigo .card-title { color: #4338ca; }

    .card-cyan { border-top: 3px solid #0891b2; background: #f0fdfa; }
    .card-cyan .card-title { color: #0e7490; }

    .card-emerald { border-top: 3px solid #059669; background: #f0fdf4; }
    .card-emerald .card-title { color: #065f46; }

    .card-amber { border-top: 3px solid #d97706; background: #fffbeb; }
    .card-amber .card-title { color: #92400e; }

    .card-rose { border-top: 3px solid #e11d48; background: #fff1f2; }
    .card-rose .card-title { color: #be123c; }

    .steps-list {
        margin: 0;
        padding-left: 13px;
        font-size: 7.8pt;
    }

    .steps-list li {
        margin-bottom: 3.5px;
        line-height: 1.35;
    }

    .steps-list strong {
        color: #0f172a;
    }

    .ui-specs-list {
        margin: 0;
        padding: 0;
        list-style: none;
        font-size: 7.6pt;
    }

    .ui-specs-list li {
        padding: 2.5px 0;
        border-bottom: 1px dashed rgba(0,0,0,0.06);
        display: flex;
        justify-content: space-between;
    }

    .ui-specs-list li:last-child {
        border-bottom: none;
    }

    .ui-label {
        font-weight: 700;
        color: #1e293b;
    }

    .ui-desc {
        color: #475569;
        text-align: right;
        max-width: 62%;
    }

    table.spec-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.5pt;
        margin: 6px 0 10px 0;
    }

    table.spec-table th {
        background: #0f172a;
        color: #ffffff;
        font-weight: 700;
        text-align: left;
        padding: 5px 7px;
        border: 1px solid #0f172a;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    table.spec-table td {
        padding: 5px 7px;
        border: 1px solid #cbd5e1;
        vertical-align: top;
        line-height: 1.35;
    }

    table.spec-table tr:nth-child(even) td {
        background-color: #f8fafc;
    }

    .toc-item {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        padding: 3.5px 0;
        border-bottom: 1px dotted #cbd5e1;
        font-size: 8.2pt;
    }

    .toc-num {
        font-weight: 800;
        color: #4f46e5;
        margin-right: 8px;
    }

    .toc-title {
        font-weight: 600;
        color: #1e293b;
    }

    .toc-dots {
        flex-grow: 1;
        border-bottom: 1px dotted #94a3b8;
        margin: 0 8px;
    }

    .toc-module {
        color: #64748b;
        font-size: 7.2pt;
    }
    """

def generate_svg_userflow(flow):
    """
    Renders an interactive, step-by-step Operator Userflow Vector SVG.
    Layout (Width: 720, Height: 235):
      - Col 0 (x=15..135): Step 1 - Page Navigation & Landing
      - Col 1 (x=155..280): Step 2 - User Trigger & Form Modal
      - Col 2 (x=305..415): Step 3 - Validation Gateway (Diamond)
      - Col 3 (x=440..560): Step 4 - Success State & UI Feedback
      - Col 4 (x=585..705): Step 5 - Downstream Persona Handoff
      - Bottom Row: Secondary Drawer Action & Validation Error Recovery Loop
    """
    w, h = 720, 235
    s1 = flow.get("step1", ("1. Land on Route", "View data table"))
    s2 = flow.get("step2", ("2. Click Action", "Open input modal"))
    dec = flow.get("decision", ("Form Valid?", "Valid", "Errors"))
    s4 = flow.get("step3", ("4. Save & Confirm", "Toast & table update"))
    s5 = flow.get("handoff", ("5. Next Persona", "Handoff to Approver"))
    err_text = flow.get("err_text", "Inline red alerts / Highlight missing inputs")
    sec_action = flow.get("secondary", ("View Detail Drawer", "Inspect item history / status"))

    svg = []
    svg.append(f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">')
    svg.append('''
      <defs>
        <marker id="uarr" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#475569" />
        </marker>
        <marker id="uarr-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#059669" />
        </marker>
        <marker id="uarr-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#dc2626" />
        </marker>
        <marker id="uarr-purple" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#7c3aed" />
        </marker>
        <linearGradient id="bgU" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="100%" stop-color="#f8fafc" />
        </linearGradient>
      </defs>
    ''')

    # Background canvas
    svg.append(f'<rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="url(#bgU)" stroke="#e2e8f0" stroke-width="1.2" />')

    # Top Legend Ribbon
    svg.append(f'''
      <g transform="translate(15, 10)">
        <rect x="0" y="0" width="10" height="10" rx="2" fill="#3b82f6" />
        <text x="14" y="8.5" font-size="8" fill="#475569" font-weight="700">PAGE ENTRY</text>
        <rect x="95" y="0" width="10" height="10" rx="2" fill="#4f46e5" />
        <text x="109" y="8.5" font-size="8" fill="#475569" font-weight="700">USER ACTION / MODAL</text>
        <rect x="235" y="0" width="10" height="10" rx="2" fill="#d97706" />
        <text x="249" y="8.5" font-size="8" fill="#475569" font-weight="700">UI VALIDATION GATE</text>
        <rect x="375" y="0" width="10" height="10" rx="2" fill="#059669" />
        <text x="389" y="8.5" font-size="8" fill="#475569" font-weight="700">SUCCESS STATE</text>
        <rect x="495" y="0" width="10" height="10" rx="2" fill="#7c3aed" />
        <text x="509" y="8.5" font-size="8" fill="#475569" font-weight="700">PERSONA HANDOFF</text>
      </g>
      <line x1="15" y1="26" x2="{w-15}" y2="26" stroke="#f1f5f9" stroke-width="1" />
    ''')

    # 1. STEP 1: PAGE ENTRY (Col 0)
    svg.append(f'''
      <rect x="15" y="44" width="120" height="52" rx="5" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.3" />
      <text x="75" y="64" font-size="8.5" font-weight="700" fill="#1e40af" text-anchor="middle">{s1[0][:20]}</text>
      <text x="75" y="79" font-size="7.5" fill="#2563eb" text-anchor="middle">{s1[1][:24]}</text>
    ''')

    # Arrow 1 -> 2
    svg.append(f'<path d="M 135 70 L 160 70" stroke="#475569" stroke-width="1.3" marker-end="url(#uarr)" />')

    # 2. STEP 2: USER ACTION / MODAL (Col 1)
    svg.append(f'''
      <rect x="160" y="44" width="125" height="52" rx="5" fill="#eef2ff" stroke="#4f46e5" stroke-width="1.3" />
      <text x="222" y="64" font-size="8.5" font-weight="700" fill="#312e81" text-anchor="middle">{s2[0][:20]}</text>
      <text x="222" y="79" font-size="7.5" fill="#4338ca" text-anchor="middle">{s2[1][:24]}</text>
    ''')

    # Arrow 2 -> Decision
    svg.append(f'<path d="M 285 70 L 315 70" stroke="#475569" stroke-width="1.3" marker-end="url(#uarr)" />')

    # 3. DECISION DIAMOND (Col 2)
    dec_cx, dec_cy = 360, 70
    dec_q, dec_p, dec_f = dec
    svg.append(f'''
      <polygon points="{dec_cx},{dec_cy-28} {dec_cx+45},{dec_cy} {dec_cx},{dec_cy+28} {dec_cx-45},{dec_cy}" fill="#fffbeb" stroke="#d97706" stroke-width="1.3" />
      <text x="{dec_cx}" y="{dec_cy-3}" font-size="7.5" font-weight="700" fill="#92400e" text-anchor="middle">{dec_q[:14]}</text>
      <text x="{dec_cx}" y="{dec_cy+9}" font-size="6.8" fill="#b45309" text-anchor="middle">Field Check</text>
    ''')

    # Pass Arrow (to Col 3)
    svg.append(f'<path d="M {dec_cx+45} {dec_cy} L 440 {dec_cy}" stroke="#059669" stroke-width="1.3" marker-end="url(#uarr-green)" />')
    svg.append(f'<text x="{dec_cx+55}" y="{dec_cy-5}" font-size="7" font-weight="700" fill="#059669">{dec_p[:8]}</text>')

    # 4. STEP 4: SUCCESS STATE (Col 3)
    svg.append(f'''
      <rect x="440" y="44" width="120" height="52" rx="5" fill="#f0fdf4" stroke="#059669" stroke-width="1.3" />
      <text x="500" y="64" font-size="8.5" font-weight="700" fill="#065f46" text-anchor="middle">{s4[0][:18]}</text>
      <text x="500" y="79" font-size="7.5" fill="#059669" text-anchor="middle">{s4[1][:22]}</text>
    ''')

    # Arrow 4 -> 5
    svg.append(f'<path d="M 560 70 L 585 70" stroke="#7c3aed" stroke-width="1.3" marker-end="url(#uarr-purple)" />')

    # 5. STEP 5: PERSONA HANDOFF (Col 4)
    svg.append(f'''
      <rect x="585" y="44" width="120" height="52" rx="5" fill="#faf5ff" stroke="#7c3aed" stroke-width="1.3" />
      <text x="645" y="64" font-size="8.5" font-weight="700" fill="#581c87" text-anchor="middle">{s5[0][:20]}</text>
      <text x="645" y="79" font-size="7.5" fill="#7c3aed" text-anchor="middle">{s5[1][:24]}</text>
    ''')

    # 6. VALIDATION ERROR LOOP (Bottom Left)
    svg.append(f'''
      <path d="M {dec_cx} {dec_cy+28} L {dec_cx} 140 L 222 140 L 222 96" fill="none" stroke="#dc2626" stroke-width="1.2" stroke-dasharray="3,2" marker-end="url(#uarr-red)" />
      <text x="{dec_cx+8}" y="125" font-size="7" font-weight="700" fill="#dc2626">{dec_f[:10]}</text>
      <rect x="145" y="148" width="220" height="26" rx="4" fill="#fff1f2" stroke="#f43f5e" stroke-width="1" />
      <text x="255" y="165" font-size="7.2" font-weight="600" fill="#be123c" text-anchor="middle">Error State: {err_text[:40]}</text>
    ''')

    # 7. SECONDARY ACTION / DETAIL DRAWER (Bottom Right)
    svg.append(f'''
      <path d="M 500 96 L 500 148 L 440 148" fill="none" stroke="#64748b" stroke-width="1.2" marker-end="url(#uarr)" />
      <rect x="410" y="148" width="295" height="42" rx="4" fill="#f8fafc" stroke="#94a3b8" stroke-width="1" />
      <text x="557" y="167" font-size="8" font-weight="700" fill="#1e293b" text-anchor="middle">Secondary Flow: {sec_action[0][:32]}</text>
      <text x="557" y="181" font-size="7.2" fill="#64748b" text-anchor="middle">{sec_action[1][:44]}</text>
    ''')

    # Bottom helper ribbon
    svg.append(f'''
      <g transform="translate(15, 205)">
        <circle cx="6" cy="6" r="5" fill="#475569" />
        <text x="16" y="9" font-size="7.5" fill="#475569" font-weight="600">Pro Tip: Keyboard shortcut &apos;/&apos; focuses the global search bar; &apos;Esc&apos; dismisses active slide-over drawers without saving.</text>
      </g>
    ''')

    svg.append('</svg>')
    return '\n'.join(svg)


USERFLOW_MODULES = [
    {
        "id": "uf1_auth",
        "num": "01",
        "name": "Authentication, MFA & User Profile",
        "route": "/login, /profile",
        "persona": "All Employees, System Administrator, Field Staff",
        "permission": "Public / Authenticated User",
        "overview": "The user entry gateway: manages enterprise authentication with secure Argon2id password hashing, 6-digit TOTP MFA verification, active facility/warehouse workspace switching, and password reset.",
        "screen_controls": [
            ("Top Site Switcher", "Pill selector switching the user's active operating factory and warehouse scope."),
            ("MFA Input Field", "6-box numeric OTP entry for Google Authenticator / 2FA TOTP code validation."),
            ("Session Toggles", "Remember Me retention checkbox and secure session token management."),
            ("User Profile Drawer", "Displays active session tokens, security key history, and emergency session signout.")
        ],
        "step1": ("1. Navigate to /login", "Landing on login portal"),
        "step2": ("2. Submit Credentials", "Enter email and password"),
        "decision": ("MFA Enabled?", "Require 2FA", "Direct Entry"),
        "step3": ("4. Active Session", "Redirect to Dashboard"),
        "handoff": ("5. Module Access", "Unlock authorized routes"),
        "err_text": "Invalid email/password (Throttled after 5 tries)",
        "secondary": ("Switch Facility Workspace", "Operator selects assigned factory from header pill"),
        "walkthrough": [
            ("Portal Landing", "User arrives at `/login`. The system presents the company branded login card for corporate credentials."),
            ("Credential Verification", "User submits email and password. Backend verifies password against Argon2id hash with brute-force rate limiting."),
            ("Two-Factor Authentication (TOTP)", "If MFA is enforced, a 6-digit TOTP input appears. The user inputs their authenticator passcode; `pyotp` verifies token freshness within a 30-second window."),
            ("Workspace Facility Scoping", "Upon successful authentication, the user lands on their home dashboard. The top navigation bar displays their active site (e.g. `Factory: Alpha Plant | Warehouse: WH-01`). Users assigned to multiple facilities can switch operational context instantly.")
        ],
        "modals_forms": [
            ("Local Login Form", "Email input, Password field (masked with toggle eye), 'Remember Me' checkbox."),
            ("MFA Verification Modal", "6-digit segmented PIN input with auto-advance and countdown resend timer."),
            ("Change Password Modal", "Current Password, New Password (strength meter: 8+ chars, uppercase, symbol), Confirm Password.")
        ],
        "error_states": "401 Unauthorized toast on bad password; 429 Too Many Requests banner locking the user for 15 minutes after 5 consecutive failed attempts.",
        "handoff_summary": "Hands off to the role's default landing route (e.g., Warehouse Operator &rarr; `/warehouse`, Buyer &rarr; `/procurement`)."
    },
    {
        "id": "uf2_control_tower",
        "num": "02",
        "name": "Dashboard & SC Control Tower",
        "route": "/, /sc-control-tower",
        "persona": "Chief Operating Officer, Plant Head, Supply Chain Director",
        "permission": "analytics:read, system:status",
        "overview": "The executive command center: aggregates real-time cross-module metrics into synchronized KPI scorecards, drill-down operational alert drawers, and live supply chain pipeline health trackers.",
        "screen_controls": [
            ("Date & Site Filter", "Dropdowns to filter metrics by today, last 7 days, this month, and specific factory sites."),
            ("Executive KPI Widgets", "Cards displaying OTIF %, Stock Health, Open PO Backlog, and Daily Revenue."),
            ("Bottleneck Alert Strip", "Badged warnings for overdue purchase orders, QC quarantine spikes, and credit holds."),
            ("Module Quick Launchers", "Direct navigation pills to open Purchase Orders, Warehouse GRN, and Sales Book.")
        ],
        "step1": ("1. Land on Dashboard", "Load Control Tower KPIs"),
        "step2": ("2. Click Alert Pill", "Filter overdue orders"),
        "decision": ("Threshold Alert?", "Investigate", "Nominal Health"),
        "step3": ("4. Drilldown Table", "Review bottleneck line items"),
        "handoff": ("5. Notify Supervisor", "Trigger expedited action"),
        "err_text": "Live telemetry timeout (auto-retry in 10s)",
        "secondary": ("Export Executive Brief", "Generate 1-click PDF status report of facility metrics"),
        "walkthrough": [
            ("Executive Overview", "User opens `/sc-control-tower`. The dashboard renders 6 real-time operational cards: On-Time In-Full Delivery (OTIF %), Inventory Value, Active Production Runs, and Days of Supply."),
            ("Interactive Bottleneck Triage", "Clicking on the amber '7 Overdue Inbound Deliveries' badge immediately filters the lower operational table to show late supplier shipments with contact details."),
            ("Deep-Link Navigation", "Clicking a row in the bottleneck table opens the corresponding Purchase Order or GRN in a dedicated side-panel drawer without losing dashboard context."),
            ("Scheduled Export", "User clicks the `[Download Snapshot]` button to generate an executive-ready PDF report for morning production standups.")
        ],
        "modals_forms": [
            ("Filter Range Modal", "Presets: Today, Week-to-Date, Month-to-Date, Custom Datepicker."),
            ("Expedite Notice Modal", "Recipients (Supplier / Expediter), Email Subject, Expedite Reason, Priority Tag.")
        ],
        "error_states": "Stale data indicator when telemetry cache exceeds 5 minutes; red toast if real-time connection disconnects.",
        "handoff_summary": "Escalates flagged operational delays to Procurement Buyers or Production Supervisors via in-app notification."
    },
    {
        "id": "uf3_parties",
        "num": "03",
        "name": "Parties Directory & AVL Governance",
        "route": "/parties, /party/:partyId, /avl-governance",
        "persona": "Procurement Manager, Commercial Analyst, Compliance Officer",
        "permission": "party:read, party:write, avl:audit",
        "overview": "Onboards and maintains external business partners: Vendors, Customers, Transporters, and Job Workers. Manages tax verification, Approved Vendor List (AVL) risk ratings, and customer credit limits.",
        "screen_controls": [
            ("Party Type Tabs", "Segmented pills filtering list by: All, Vendors, Customers, Transporters, Job Workers."),
            ("[+ New Party] CTA", "Opens slide-over drawer to register a new commercial partner."),
            ("Tax Verification Badge", "Green checkmark for validated GSTIN/PAN; amber shield for pending audit."),
            ("Credit Utilization Bar", "Visual progress bar showing outstanding receivables vs assigned credit limit.")
        ],
        "step1": ("1. Land on /parties", "Browse commercial master"),
        "step2": ("2. Click [+ New Party]", "Open Onboarding Drawer"),
        "decision": ("PAN/GST Valid?", "Save Master", "Inline Tax Error"),
        "step3": ("4. Party Created", "Green toast & record active"),
        "handoff": ("5. Quality Audit", "Queue vendor for AVL audit"),
        "err_text": "Duplicate Tax ID or Invalid GSTIN checksum",
        "secondary": ("Audit AVL Scorecard", "Set probation / approved status and credit terms"),
        "walkthrough": [
            ("Directory Search", "User navigates to `/parties`. Using the quick filter bar, they can search by Trading Name, Tax ID (GSTIN/PAN), or filter exclusively by 'Vendors'."),
            ("Party Onboarding Form", "User clicks `[+ New Party]`. A drawer opens requesting Legal Entity Name, Trade Name, Party Type, Currency, and Primary Contact Email."),
            ("Automated Tax Scrutiny", "User inputs the 15-character GSTIN. Client-side regex and backend checksum algorithms validate state code and PAN structure instantly."),
            ("Credit Limit & Terms Assignment", "For customers, the analyst enters Credit Limit ($) and Payment Terms (e.g. Net 30, Net 45). For vendors, bank account coordinates are provided for electronic payment disbursements."),
            ("AVL Governance Sign-off", "Quality and Procurement teams review vendor compliance documents, tagging vendor status as `APPROVED`, `PROBATION`, or `BLOCKED`.")
        ],
        "modals_forms": [
            ("Create Party Drawer", "Party Name, Type Selector, GSTIN, PAN, Email, Phone, Currency, Credit Limit, Payment Terms."),
            ("Bank Account Modal", "Beneficiary Name, Bank Name, Account Number, IFSC / SWIFT Code, Account Type."),
            ("Address Book Modal", "Address Label, Street, City, State Dropdown, PIN Code, Dispatch vs Billing checkbox.")
        ],
        "error_states": "Form blocks submission if GSTIN does not match PAN characters 3 through 12; red toast on duplicate tax registrations.",
        "handoff_summary": "Approved vendors appear in Procurement PO dropdowns; approved customers unlock Sales Order quotation."
    },
    {
        "id": "uf4_business_entities",
        "num": "04",
        "name": "Business Entities & Legal Invoicing",
        "route": "/po-invoice",
        "persona": "Corporate Controller, Finance Director, Legal Counsel",
        "permission": "org:read, org:write, finance:admin",
        "overview": "Configures corporate legal identities, regional state GSTIN branches, registered headquarters, corporate seals, and primary bank disbursement accounts used on all POs and tax invoices.",
        "screen_controls": [
            ("Entity Cards View", "Grid of registered legal corporations showing active branches and factories."),
            ("[+ Add Business Entity]", "Button triggering modal to register a new incorporated entity."),
            ("State Branch Manager", "Sub-table managing state GSTIN certificates and registered addresses."),
            ("Primary Bank Selector", "Radio button selecting the default clearing account for outbound payments.")
        ],
        "step1": ("1. Land on /po-invoice", "View Corporate Entities"),
        "step2": ("2. Click [+ Add Entity]", "Open Corporation Modal"),
        "decision": ("CIN / PAN Valid?", "Link Factories", "Fix Legal Reg ID"),
        "step3": ("4. Entity Activated", "Set as default issuer"),
        "handoff": ("5. Legal Setup Done", "PO & Invoice branding ready"),
        "err_text": "CIN format error or unmapped state GSTIN",
        "secondary": ("Upload Corporate Stamp", "Attach high-res digital signature for automated PDF generation"),
        "walkthrough": [
            ("Entity Navigation", "User enters `/po-invoice`. The screen displays active corporate profiles (e.g. 'Axon Technologies Private Limited')."),
            ("Corporate Registration", "User clicks `[+ Add Business Entity]` and enters Corporate Identification Number (CIN), Company PAN, and official registered legal address."),
            ("State Branch Mapping", "User adds state tax branches (e.g., Maharashtra GSTIN 27..., Gujarat GSTIN 24...) and maps them to operating physical factories."),
            ("Banking Disbursement Linking", "User adds commercial bank accounts, uploading IFSC codes and account numbers to designate the default account for vendor wire transfers."),
            ("Document Engine Branding", "User uploads corporate digital stamps and signatures for automated inclusion on PO and Tax Invoice PDF documents.")
        ],
        "modals_forms": [
            ("Business Entity Modal", "Legal Entity Name, Trade Name, CIN, Corporate PAN, Website, Registered Address."),
            ("State Tax Branch Modal", "State Dropdown, 15-digit GSTIN, Branch Name, Factory Mapping Selector."),
            ("Bank Account Linking Modal", "Bank Name, Branch, Account Number, IFSC Code, Currency, Default Account Toggle.")
        ],
        "error_states": "Rejects duplicate state branch registrations; alerts user if a factory is unmapped to any legal business entity.",
        "handoff_summary": "Available in Procurement as Buyer Entity and in Invoicing as Seller Tax Entity."
    },
    {
        "id": "uf5_facilities_wms",
        "num": "05",
        "name": "Facilities, Factory & WMS Bins",
        "route": "/factory-warehouse, /wms-bins",
        "persona": "Plant Head, Warehouse Operations Manager, Industrial Engineer",
        "permission": "warehouse:read, warehouse:write, factory:admin",
        "overview": "Builds the physical supply chain layout: factory manufacturing plants, central and regional warehouses, and multi-tier WMS bin hierarchies (Zones, Aisles, Racks, Shelves, Bins) with capacity rules.",
        "up_nodes": [("Factory Setup", "Define Sites"), ("Warehouse Setup", "Define Depots")],
        "screen_controls": [
            ("Facility Tree Explorer", "Interactive collapsible tree showing Factory &rarr; Warehouse &rarr; Zone &rarr; Bin."),
            ("[+ New Warehouse] CTA", "Button to create a storage depot (Raw Materials, WIP, FG, Quarantine)."),
            ("Bin Generator Tool", "Bulk generator dialog to create aisles and rack coordinates in bulk."),
            ("Bin Status Lock Switch", "Toggle switch to freeze a bin during physical audits or maintenance.")
        ],
        "step1": ("1. Land on /factory-warehouse", "Inspect Facility Layout"),
        "step2": ("2. Click [Bulk Bin Tool]", "Define Aisle/Rack pattern"),
        "decision": ("Capacity Check?", "Generate Bins", "Adjust Grid Specs"),
        "step3": ("4. Storage Grid Built", "500 Bins active & visual"),
        "handoff": ("5. WMS Ready", "Available for Putaway/Picking"),
        "err_text": "Conflicting bin coordinate naming convention",
        "secondary": ("Lock Bin for Audit", "Operator clicks [Lock Bin] during physical discrepancy check"),
        "walkthrough": [
            ("Facility Hierarchy Setup", "User opens `/factory-warehouse` and clicks `[+ Add Factory]`, setting the manufacturing plant name, site address, and operational cost center."),
            ("Warehouse Partitioning", "Under the factory, user adds dedicated storage warehouses: Raw Materials Warehouse (`WH-RM-01`), WIP Staging (`WH-WIP-01`), and Finished Goods (`WH-FG-01`)."),
            ("Multi-Tier Bin Grid Generation", "User clicks `[Bulk Bin Generator]` on `/wms-bins`. They enter Aisle range (A to E), Rack range (01 to 10), and Shelf range (1 to 4). The system auto-generates 200 serialized storage bins (`A-01-1` to `E-10-4`)."),
            ("Bin Velocity & Capacity Profiling", "User tags dock-adjacent bins as 'Fast-Moving High Velocity' and assigns maximum weight thresholds (e.g. max 1,000 kg).")
        ],
        "modals_forms": [
            ("Factory Creation Modal", "Factory Code, Factory Name, Address, Operating Hours, Linked Business Entity."),
            ("Warehouse Creation Modal", "Warehouse Code, Type (RAW_MATERIAL, WIP, FINISHED_GOODS, SCRAP), Site Selector."),
            ("Bulk Bin Generator Modal", "Zone Name, Aisle Prefix, Rack Count, Shelf Count, Volumetric Capacity (m³), Max Weight (kg).")
        ],
        "error_states": "Prevents deletion of warehouses containing active stock balances; warning modal on duplicate bin codes.",
        "handoff_summary": "Bins become immediately selectable in GRN Putaway and Wave Picking path optimization algorithms."
    },
    {
        "id": "uf6_products_bom",
        "num": "06",
        "name": "Product Catalog & Engineering BOM",
        "route": "/products",
        "persona": "R&D Engineer, Product Manager, Cost Accountant",
        "permission": "product:read, product:write, bom:read, bom:write",
        "overview": "Item master creation and multi-level Bill of Materials (BOM) management. Allows engineers to build assembly recipes, define component scrap allowances, manage ECO revisions, and run cost rollups.",
        "screen_controls": [
            ("Item Type Filters", "Pills to filter by: Finished Goods, Sub-Assemblies, Raw Materials, Consumables."),
            ("[+ New Product] CTA", "Button to open SKU creation drawer with barcode generator."),
            ("Interactive BOM Tree", "Collapsible multi-level component hierarchy with quantities and unit costs."),
            ("Cost Rollup Calculator", "Runs real-time sum of material, direct labor, and overhead absorption.")
        ],
        "step1": ("1. Land on /products", "Browse Product Catalog"),
        "step2": ("2. Click [+ New BOM]", "Open Recipe Builder"),
        "decision": ("Circular Loop?", "Save Revision", "Circular BOM Alert"),
        "step3": ("4. BOM v1.0 Published", "Locked & approved state"),
        "handoff": ("5. MRP Integration", "Available for planning"),
        "err_text": "Child component cannot equal parent assembly",
        "secondary": ("Run Cost Rollup", "Recomputes standard product cost against latest component prices"),
        "walkthrough": [
            ("SKU Definition", "User navigates to `/products` and clicks `[+ New Product]`. They enter Item Name, SKU Code (or auto-generate), Category, HSN Code, Base UOM, and standard sales price."),
            ("BOM Builder Initialization", "Selecting a Finished Good, user clicks `[Create Bill of Materials]`. They specify Assembly Batch Size (e.g. 1 Unit) and BOM Version (`v1.0`)."),
            ("Adding Child Components", "User searches and selects child items, specifying required quantity per build and planned scrap factor (e.g. 2% component attrition)."),
            ("Engineering Validation & Lock", "System verifies that no circular references exist (an assembly containing itself). Engineer clicks `[Approve & Lock BOM]`. Version status transitions to `ACTIVE`."),
            ("Cost Rollup Execution", "User clicks `[Calculate Cost Rollup]`. The engine aggregates active component purchase prices plus work center labor and overhead rates, saving standard product cost.")
        ],
        "modals_forms": [
            ("Create SKU Drawer", "Product Name, SKU Code, Category Dropdown, Type, HSN/SAC, Base UOM, Safety Stock, Reorder Point."),
            ("BOM Component Line Modal", "Component SKU Selector, Quantity per Unit, Scrap Allowance %, Routing Stage Selector."),
            ("Engineering Change Order (ECO) Modal", "ECO Number, Reason for Revision, Effective Start Date, Obsoleted Parts List.")
        ],
        "error_states": "System blocks saving if total component scrap exceeds 50%; error alert if component SKU is inactive.",
        "handoff_summary": "Active BOM recipes feed directly into MRP gross-to-net explosions and Shop Floor Work Orders."
    },
    {
        "id": "uf7_planning_mrp_drp",
        "num": "07",
        "name": "Supply Chain Planning: MRP & DRP",
        "route": "/forecasting, /mrp, /drp, /capacity-planning",
        "persona": "Master Scheduler, Supply Chain Planner, Inventory Controller",
        "permission": "mrp:read, mrp:plan, drp:transfer",
        "overview": "Synthesizes customer orders and sales forecasts against current inventory and lead times. Generates planned purchase requisitions and manufacturing work orders with lead-time offsetting.",
        "screen_controls": [
            ("Planning Horizon Selector", "Dropdown to select 30-day, 60-day, or 90-day time bucket schedules."),
            ("[Run MRP Engine] CTA", "High-visibility button triggering multi-echelon demand explosion."),
            ("Deficit Highlighting", "Red font for parts with projected stockouts before lead time expires."),
            ("[Convert to PO/WO] Buttons", "One-click actions to convert planned suggestions into formal requisitions.")
        ],
        "step1": ("1. Land on /mrp", "Inspect Net Deficit"),
        "step2": ("2. Click [Run MRP]", "Trigger Netting Calculation"),
        "decision": ("Capacity Breach?", "Release Orders", "Shift Horizon"),
        "step3": ("4. Suggestions Ready", "List of planned PRs & WOs"),
        "handoff": ("5. Convert Planned", "Requisitions sent to Buyer"),
        "err_text": "Supplier lead time extends beyond demand date",
        "secondary": ("Run DRP Rebalance", "Auto-creates inter-warehouse replenishment transfer requests"),
        "walkthrough": [
            ("Demand Review", "Planner reviews forecasted demand on `/forecasting` alongside unfulfilled committed Sales Orders on `/orders`."),
            ("Executing MRP Engine Run", "Planner navigates to `/mrp` and clicks `[Run MRP Engine]`. The backend traverses all active BOMs, nets physical on-hand stock and open POs, and computes net deficits."),
            ("Triage Planned Recommendations", "The screen presents two actionable tabs: 'Planned Purchase Requisitions' (for raw materials) and 'Planned Production Orders' (for sub-assemblies and finished goods)."),
            ("Bulk Conversion", "Planner selects 15 planned component lines and clicks `[Convert to Purchase Requisitions]`. The system automatically generates PR records tagged with vendor lead times and due dates.")
        ],
        "modals_forms": [
            ("MRP Run Parameters Modal", "Planning Horizon (weeks), Include Safety Stock (toggle), Scrap Factor (toggle)."),
            ("Convert Planned Order Modal", "Destination Warehouse, Required By Date, Target Vendor (auto-suggested from AVL).")
        ],
        "error_states": "Warning modal if supplier minimum order quantity (MOQ) requires buying significant excess inventory.",
        "handoff_summary": "Emits Purchase Requisitions to the Procurement Buyer queue and planned Work Orders to Production."
    },
    {
        "id": "uf8_procurement_po",
        "num": "08",
        "name": "Procurement & Purchase Orders",
        "route": "/procurement, /blanket-po, /vendor-portal",
        "persona": "Procurement Buyer, Purchasing Head, Finance Director",
        "permission": "po:read, po:write, po:approve",
        "overview": "Complete purchasing management: manages requisitions, issues competitive RFQs, drafts Purchase Orders (Standard or Blanket), enforces multi-tier signature limits, and handles vendor acknowledgments.",
        "screen_controls": [
            ("Status Filter Chips", "Filter list by Draft, Pending Approval, Approved, Issued, Partially Received, Closed."),
            ("[+ Create PO] CTA", "Primary action button opening the PO drafting studio."),
            ("Approval Banner", "Prominent green/amber banner prompting authorized managers to approve or reject."),
            ("Action Overflow Menu", "Options to Print PDF, Email Vendor, Create Revision, or Short-Close.")
        ],
        "step1": ("1. Land on /procurement", "Review Purchase Orders"),
        "step2": ("2. Click [+ Create PO]", "Open PO Creation Form"),
        "decision": ("Spend > $10,000?", "VP Approval Reqd", "Manager Signoff"),
        "step3": ("4. PO Issued to Vendor", "Dispatched via email/portal"),
        "handoff": ("5. Vendor & Receiving", "Warehouse alerts for receipt"),
        "err_text": "Exceeded department budget allocation",
        "secondary": ("Issue PO Amendment", "Buyer increments quantity and creates version PO-001-R1"),
        "walkthrough": [
            ("Requisition Ingestion", "Buyer opens `/procurement`, reviews pending Purchase Requisitions, and clicks `[Generate PO]` from an approved requisition."),
            ("PO Drafting", "Buyer selects the Approved Vendor, delivery warehouse, requested arrival date, payment terms, and incoterms. Line items specify HSN codes, ordered quantities, unit rates, and GST taxes."),
            ("Submission for Approval", "Buyer clicks `[Submit for Approval]`. The system checks total spend against approval limits. If total order is $45,000, it automatically assigns the approval task to the Supply Chain VP."),
            ("Manager Sign-Off", "VP receives notification, reviews the digital line item breakdown, and clicks `[Approve Purchase Order]`. Status changes to `APPROVED`."),
            ("Dispatch & Vendor Sync", "The system auto-compiles the official PDF, emails the vendor with a secure portal link, and transmits expected receipt schedules to the warehouse.")
        ],
        "modals_forms": [
            ("PO Header & Lines Studio", "Vendor Dropdown, Business Entity, Warehouse, Expected Date, Line Items Grid (SKU, Qty, Rate, Tax)."),
            ("Approval Decision Modal", "Approve / Reject radio button, Approval Comments, Forward to Higher Approver checkbox."),
            ("PO Short-Close Modal", "Short-Close Reason (Vendor stockout, project cancelled), Final Received Qty confirmation.")
        ],
        "error_states": "System blocks selecting a BLOCKED or DISQUALIFIED vendor; prevents editing line prices once PO is approved.",
        "handoff_summary": "Notifies the vendor to ship goods and opens the PO receiving window for Warehouse Gate Entry."
    },
    {
        "id": "uf9_inbound_logistics",
        "num": "09",
        "name": "Inbound Logistics & Gate Entry",
        "route": "/logistics, /freight-tms",
        "persona": "Security Gate Officer, Weighbridge Clerk, Inbound Logistics Officer",
        "permission": "logistics:read, logistics:write, gate:entry",
        "overview": "Tracks inbound transport vehicles from vendor dispatch, verifies Advance Shipping Notices (ASN), checks driver credentials and Delivery Challans at the factory gate, and prints Gate Entry passes.",
        "screen_controls": [
            ("Live Gate Queue Table", "Displays trucks at perimeter: Arrived, Weighed, Dock Assigned, Unloading."),
            ("[+ New Gate Entry] CTA", "High-contrast button for rapid vehicle check-in by security personnel."),
            ("Weighbridge Gross Button", "One-touch button capturing real-time automated digital scale weight."),
            ("Print Gate Pass", "Prints 3-copy physical pass for Driver, Receiving Dock, and Security Exit.")
        ],
        "step1": ("1. Land on /logistics", "Monitor Gate Queue"),
        "step2": ("2. Click [+ Gate Entry]", "Open Vehicle Check-In"),
        "decision": ("PO Line Active?", "Issue Gate Pass", "Turnaround Truck"),
        "step3": ("4. Pass Issued", "Print INW-Pass & assign dock"),
        "handoff": ("5. Unloading Dock", "Warehouse begins receipt"),
        "err_text": "Invalid vehicle registration or expired PO number",
        "secondary": ("Capture Weighbridge Gross", "Driver drives onto platform scale; clerk clicks [Sync Scale]"),
        "walkthrough": [
            ("Truck Arrival", "Truck arrives at factory perimeter. Security officer opens `/logistics` on a touchscreen gate terminal."),
            ("Vehicle Data Entry", "Officer clicks `[+ New Gate Entry]`. They enter Truck Registration Number, Driver Name, Mobile Number, Transporter Name, and Delivery Challan Number."),
            ("PO Validation", "Officer enters the vendor's Purchase Order number. System validates that the PO is active and approved, displaying expected delivery lines."),
            ("Weighbridge Scale Capture", "Truck pulls onto automated weighbridge platform. Officer clicks `[Read Weighbridge]`; the system records gross weight (e.g. 18,450 kg)."),
            ("Dock Assignment & Pass Issuance", "Officer clicks `[Assign Dock & Print Pass]`. The system assigns Unloading Dock #03 and prints Gate Inward Pass `INW-2026-0042`.")
        ],
        "modals_forms": [
            ("Gate Check-in Modal", "PO Number Lookup, Transporter, Vehicle Number, Driver License, Challan Number, Container Seal #."),
            ("Dock Allocation Modal", "Select Bay / Dock (Dock 1 to 8), Unloading Priority (Standard, Expedited, Frozen).")
        ],
        "error_states": "System blocks gate entry if container seals are reported broken; red alert on unauthorized transporter.",
        "handoff_summary": "Transfers custody of shipment to Warehouse Receiving Clerks for physical unloading."
    },
    {
        "id": "uf10_warehouse_grn_qc",
        "num": "10",
        "name": "Goods Receipt (GRN) & Inbound QC",
        "route": "/warehouse, /warehouse-qc/:grnId",
        "persona": "Receiving Storekeeper, QC Sampling Inspector, Inventory Specialist",
        "permission": "warehouse:read, grn:read, grn:write, qc:inspect",
        "overview": "Receives physical vendor deliveries, matches PO line items within tolerances, logs QC sampling inspections, issues accept/reject dispositions, prints serialized QR stickers, and executes putaway.",
        "screen_controls": [
            ("Inbound Receiving Console", "Tabs for: Pending Gate Inward, Draft GRN, In QC Inspection, Ready for Putaway."),
            ("[+ New GRN] CTA", "Initiates Goods Receipt Note linked to PO and Gate Pass."),
            ("[Launch QC Inspection]", "Opens technical testing scorecard for laboratory inspection."),
            ("[Batch Print QR Labels]", "One-click generation of thermal roll (4x2) or A4 sticker sheets.")
        ],
        "step1": ("1. Land on /warehouse", "Inspect Inbound Queue"),
        "step2": ("2. Click [+ New GRN]", "Count & verify packages"),
        "decision": ("QC Specs Passed?", "Accept & Print QR", "Quarantine / RTV"),
        "step3": ("4. Stock Putaway", "Scan pallet into bin"),
        "handoff": ("5. Finance & Stock", "Stock up & 3-Way ready"),
        "err_text": "Delivery exceeds PO over-receipt tolerance (>5%)",
        "secondary": ("Print Rejection Challan", "Inspector generates RTV note with rejection defect codes"),
        "walkthrough": [
            ("Receiving Initialization", "Storekeeper selects active Gate Pass `INW-2026-0042` and clicks `[+ Create GRN]`. System auto-populates vendor and PO line items."),
            ("Physical Package Verification", "Storekeeper counts physical boxes, entering received quantities. If quantity exceeds PO tolerance (+5%), the extra amount is blocked."),
            ("QC Sampling & Testing", "Goods move to QC Staging. QC Inspector navigates to `/warehouse-qc/:grnId`, testing dimensions, moisture, or electrical parameters against specifications."),
            ("Disposition & QR Printing", "Inspector approves batch (e.g. 500 Accepted, 10 Rejected). Storekeeper clicks `[Print QR Labels]`. Thermal printer outputs 500 serialized QR stickers."),
            ("Scan-to-Putaway", "Storekeeper affixes stickers, scans the pallet QR and destination bin barcode (`A-02-1`). Stock posts to inventory.")
        ],
        "modals_forms": [
            ("Create GRN Dialog", "Gate Pass ID, Vendor Invoice Number & Date, Received Quantities per PO line."),
            ("QC Inspection Form", "Sample Size, Visual Inspection (Pass/Fail), Measured Parameters table, Rejection Reason Dropdown."),
            ("QR Print Config Modal", "Sticker Size (4x2 Thermal Roll, 2x1 Roll, A4 24-Up Sheet), Copies per item, Include Batch ID.")
        ],
        "error_states": "System blocks inventory posting if mandatory QC inspection is skipped; alert if rejected goods lack defect code.",
        "handoff_summary": "Accepted lines appear in Finance AP for 3-Way Matching; rejected lines route to Return-to-Vendor challans."
    },
    {
        "id": "uf11_inventory_control",
        "num": "11",
        "name": "Inventory Control & Stock Ledger",
        "route": "/inventory, /inventory-item/:itemId, /cycle-counts",
        "persona": "Warehouse Manager, Stock Controller, Internal Auditor",
        "permission": "inventory:read, inventory:write, inventory:count",
        "overview": "Complete stock visibility: monitors real-time on-hand, allocated, and net available balances across all bins, traces item serials and batches, executes bin-to-bin transfers, and manages cycle counts.",
        "screen_controls": [
            ("Inventory Balances Table", "Columns: SKU, Name, Warehouse, Bin, On-Hand, Allocated, Available, Valuation."),
            ("Interactive Bin Transfer Drawer", "Slide-over tool to transfer items between warehouse bins in seconds."),
            ("Item Detail Timeline", "Chronological audit trail showing every receipt, issue, transfer, and adjustment."),
            ("[Start Cycle Count] CTA", "Initiates blind cycle count batch for designated warehouse zones.")
        ],
        "step1": ("1. Land on /inventory", "Monitor Stock Balances"),
        "step2": ("2. Click [Bin Transfer]", "Select source & target bin"),
        "decision": ("Stock Available?", "Post Transfer", "Insufficient Stock"),
        "step3": ("4. Ledger Updated", "Instant stock movement"),
        "handoff": ("5. Audit Compliance", "Balance sheet updated"),
        "err_text": "Cannot transfer stock locked in active pick wave",
        "secondary": ("Execute Blind Count", "Auditor scans items without seeing system expected counts"),
        "walkthrough": [
            ("Balance Monitoring", "User opens `/inventory`. The table displays total inventory across sites. Quick search filters by SKU `BATT-48V` to inspect on-hand vs allocated stock."),
            ("Bin-to-Bin Relocation", "Storekeeper notices fast-moving items in upper rack. They click `[Transfer Stock]`, select Source Bin `C-08-4`, Target Bin `A-01-1`, and enter quantity."),
            ("Cycle Count Audit", "Internal auditor navigates to `/cycle-counts` and clicks `[+ New Count Batch]`. They select Warehouse `WH-RM-01` and Zone `Aisle A`."),
            ("Blind Scanning", "Auditor scans physical bins and item barcodes using handheld terminal. The system conceals expected quantities to guarantee unbiased physical verification."),
            ("Variance Reconciliation", "Auditor submits count. System flags a variance of -2 units. Supervisor reviews variance, enters shrinkage reason code, and approves inventory adjustment.")
        ],
        "modals_forms": [
            ("Stock Transfer Modal", "Item SKU, Source Warehouse & Bin, Target Warehouse & Bin, Transfer Qty, Reason."),
            ("Cycle Count Setup Modal", "Count Batch Name, Count Type (Blind / Standard), Warehouse, Target Aisles/Zones."),
            ("Stock Adjustment Modal", "Item ID, Adjustment Type (+ Gain / - Loss), Quantity, Expense Reason Account.")
        ],
        "error_states": "System blocks negative inventory transactions; prevents transfers out of bins currently locked for cycle count.",
        "handoff_summary": "Maintains accurate stock baselines for Sales Order ATP netting and Production material staging."
    },
    {
        "id": "uf12_production_execution",
        "num": "12",
        "name": "Manufacturing, Work Orders & IPQC",
        "route": "/production, /production/new, /production/:runId, /quality-ipqc, /subcontracting",
        "persona": "Production Supervisor, Shop Floor Operator, IPQC Inspector",
        "permission": "inventory:read, production:plan, production:execute, qc:ipqc",
        "overview": "Shop floor execution engine: creates and releases Work Orders, allocates and stages raw materials, records work center progress, enforces in-process quality control gates, and yields finished goods.",
        "screen_controls": [
            ("Production Kanban Board", "Columns: Planned, Material Staged, In-Progress, IPQC Hold, Completed."),
            ("[+ New Production Run] CTA", "Button to schedule a manufacturing batch with target yield."),
            ("Component Allocation Bar", "Visual green/red indicator of component availability against BOM."),
            ("IPQC Inspection Checkpoint", "Stage gating interface requiring digital QC sign-off to advance.")
        ],
        "step1": ("1. Land on /production", "View Assembly Board"),
        "step2": ("2. Click [+ New Run]", "Select Finished Good SKU"),
        "decision": ("Components In Stock?", "Release Work Order", "Component Shortage"),
        "step3": ("4. Execute & Yield", "Inspect IPQC & yield FG"),
        "handoff": ("5. FG Stock & Orders", "Finished Goods to WH"),
        "err_text": "Component shortage: cannot allocate required parts",
        "secondary": ("Subcontract Job Work", "Supervisor issues outward challan to external processing vendor"),
        "walkthrough": [
            ("Work Order Scheduling", "Supervisor opens `/production` and clicks `[+ New Production Run]`. They select Finished Good SKU `SOLAR-INV-5KW` and Target Quantity `100 Units`."),
            ("BOM Explosion & Material Reservation", "System pulls active BOM recipe and checks warehouse inventory. All components are available; supervisor clicks `[Allocate & Stage Materials]`."),
            ("Material Staging to Shop Floor", "Warehouse picks raw materials and transfers them to Shop Floor WIP Bins (`WH-WIP-01`). Work Order transitions to `RELEASED`."),
            ("Routing & In-Process QC (IPQC)", "Operators run through assembly stages: PCB SMT &rarr; Chassis Assembly &rarr; Wiring. At the Burn-in Testing gate, IPQC inspector inspects 10 sample units and digitally signs the inspection gate."),
            ("Completion & FG Yield", "Supervisor inputs final yield: 98 units accepted, 2 units scrapped. System auto-prints Finished Good serial labels and deposits goods into Finished Goods Warehouse.")
        ],
        "modals_forms": [
            ("Create Production Run Modal", "Finished Good SKU, Batch Quantity, Planned Start/End Date, Priority, Linked Sales Order."),
            ("IPQC Checkpoint Modal", "Stage Name, Inspector Name, Parameters Tested table, Defect Count, Gate Pass/Fail toggle."),
            ("Complete Run Dialog", "Accepted FG Quantity, Scrap Quantity, Scrap Reason Code, Labor Hours Logged.")
        ],
        "error_states": "System prevents completing a run if any mandatory IPQC gate is unsigned; alerts if scrap exceeds 5%.",
        "handoff_summary": "Finished goods immediately update inventory balances and bind to waiting customer Sales Orders."
    },
    {
        "id": "uf13_sales_orders",
        "num": "13",
        "name": "Sales Management & Order Booking",
        "route": "/orders, /customer-portal",
        "persona": "Sales Executive, Order Desk Coordinator, Commercial Manager",
        "permission": "order:read, order:write, customer:portal",
        "overview": "Commercial revenue intake: creates customer quotations, converts quotes to binding Sales Orders, evaluates customer credit limits, checks Available-to-Promise (ATP) stock, and releases to fulfillment.",
        "screen_controls": [
            ("Sales Book Data Table", "Columns: SO #, Customer, Date, Total ($), Payment Status, Fulfillment Status, Actions."),
            ("[+ New Sales Order] CTA", "Opens order intake form with customer search and SKU pricing matrix."),
            ("Credit Check Alert Badge", "Highlights if customer is on CREDIT_HOLD due to overdue invoices."),
            ("ATP Inventory Indicator", "Pill indicating whether items are 'In Stock (Ready to Pick)' or 'Backorder (MTO)'.")
        ],
        "step1": ("1. Land on /orders", "Review Open Sales Orders"),
        "step2": ("2. Click [+ New Order]", "Select Customer & Add SKUs"),
        "decision": ("Within Credit Limit?", "Approve & Reserve", "Credit Hold Alert"),
        "step3": ("4. Order Released", "Soft stock reservation locked"),
        "handoff": ("5. Warehouse Wave", "Pushed to picking queue"),
        "err_text": "Customer credit limit exceeded ($15,000 overdue)",
        "secondary": ("Convert Quote to Order", "1-click conversion from accepted quotation to approved sales order"),
        "walkthrough": [
            ("Order Intake", "Sales coordinator navigates to `/orders` and clicks `[+ New Sales Order]`. They select Customer `SolarMax Enterprises` and shipping address."),
            ("Line Items & Pricing", "Coordinator adds 20 units of `SOLAR-INV-5KW`. The system automatically applies tier pricing, customer discount %, and state GST tax rules."),
            ("Automated Financial Credit Check", "System evaluates customer financial exposure: Unpaid AR Invoices + Unbilled Orders. The total is within the $50,000 credit ceiling."),
            ("ATP Inventory Check & Reservation", "System queries finished goods stock: 20 units are physically on-hand. Coordinator clicks `[Approve & Book Order]`. System places a soft reservation lock on the inventory."),
            ("Release to Warehouse", "Order status changes to `APPROVED`. It automatically enters the warehouse fulfillment queue for wave picking.")
        ],
        "modals_forms": [
            ("Sales Order Intake Studio", "Customer Dropdown, PO Ref #, Shipping Address, Delivery Due Date, Line Items Grid (SKU, Qty, Price, Tax)."),
            ("Override Credit Hold Dialog", "Requires Commercial Manager PIN, Justification Reason, Required Advance Payment %."),
            ("Quotation Generator Modal", "Prospect Name, Validity Window, Payment Terms, Commercial Terms & Conditions.")
        ],
        "error_states": "System blocks booking order if customer is on commercial hold; warning if requested date is within supplier lead time.",
        "handoff_summary": "Publishes order lines to the Warehouse Wave Picking console and notifies the customer via portal/email."
    },
    {
        "id": "uf14_warehouse_picking",
        "num": "14",
        "name": "Wave Picking, Packing & WMS Mobile",
        "route": "/wave-picking, /wms-mobile",
        "persona": "Pick Wave Planner, Mobile Scanner Picker, Packing Station Lead",
        "permission": "warehouse:read, wave:pick, wms:mobile",
        "overview": "Fulfillment execution: groups open orders into optimized pick waves, guides warehouse staff along shortest bin routes on mobile RF barcode scanners, verifies items at packing stations, and cartons orders.",
        "screen_controls": [
            ("Pick Wave Creation Tool", "Filters open orders by carrier, delivery zone, or SLA to form pick batches."),
            ("WMS Mobile Touch UI", "Mobile-optimized interface with large high-contrast scan prompts and audio beeps."),
            ("Packing Station Scanner", "Verifies 100% item barcodes against order lines to eliminate mis-picks."),
            ("Carton Weigh Scale Sync", "Captures package gross weight and prints serialized carton shipping labels.")
        ],
        "step1": ("1. Land on /wave-picking", "View Open Sales Orders"),
        "step2": ("2. Click [Generate Wave]", "Batch orders by shipping zone"),
        "decision": ("Pick Audit 100%?", "Cartonize & Seal", "Pick Discrepancy"),
        "step3": ("4. Cartons Staged", "Print packing slip & labels"),
        "handoff": ("5. Outbound Dock", "Handoff to Freight TMS"),
        "err_text": "Scanned SKU does not match required order line item",
        "secondary": ("Mobile Scanner Mode", "Warehouse staff open /wms-mobile on Zebra/Honeywell handheld terminals"),
        "walkthrough": [
            ("Wave Planning", "Supervisor navigates to `/wave-picking`, selects 12 open orders bound for North Region, and clicks `[Generate Pick Wave]`."),
            ("Mobile Directed Picking", "Picker logs into `/wms-mobile` on a handheld RF barcode scanner. The app directs the picker: 'Go to Aisle B, Rack 04, Bin 2'. Picker scans bin barcode, then scans SKU barcode."),
            ("Tote Transport to Packing Table", "Picked items arrive in totes at Packing Station #02. Packing lead selects the wave on the touch monitor."),
            ("Scan Verification & Packing", "Pack lead scans each item. Screen displays green checkmarks. If an incorrect SKU is scanned, an audible error buzzer alerts the operator."),
            ("Cartonization & Weighing", "Packer deposits goods into carton, places it on digital scale, and clicks `[Print Packing Slip & Carton Barcode]`. Box is sealed and moved to outbound staging dock.")
        ],
        "modals_forms": [
            ("Create Pick Wave Modal", "Wave Name, Priority (Urgent/Normal), Carrier Filter, Zone Filter, Max Orders per wave."),
            ("Packing Station Dialog", "Carton Type (Small/Med/Large Box, Pallet), Tare Weight, Gross Scale Weight, Seal #."),
            ("Pick Discrepancy Modal", "Flag Item Missing / Damaged, Request Swap from Backup Bin, Adjust Order Line.")
        ],
        "error_states": "System prevents sealing carton if any line item quantity is unverified; red alert if barcode scan fails.",
        "handoff_summary": "Transfers package counts, dimensions, and weights to the Outbound Logistics TMS engine."
    },
    {
        "id": "uf15_outbound_logistics",
        "num": "15",
        "name": "Outbound Logistics, TMS & Dispatch",
        "route": "/logistics, /shipping-engine, /statutory-logistics",
        "persona": "Logistics Dispatcher, Transport Coordinator, Carrier Transporter",
        "permission": "logistics:read, logistics:write, eway:generate",
        "overview": "Executes outward transport: runs transporter RFQ bidding, validates carrier vehicle placement, generates statutory e-Way Bills and e-Invoices, prints Delivery Challans, and tracks milestone PODs.",
        "screen_controls": [
            ("Dispatch Planning Console", "List of packed cartons staged at dock awaiting transporter booking."),
            ("[Transporter RFQ] CTA", "Broadcasts shipping request to registered freight carriers for bidding."),
            ("[Generate e-Way Bill] Button", "Direct integration with government NIC portal to generate official e-Way bill."),
            ("Proof of Delivery (POD) Uploader", "Uploads scanned signed delivery receipt to mark shipment complete.")
        ],
        "step1": ("1. Land on /shipping-engine", "Review Staged Cartons"),
        "step2": ("2. Click [Assign Carrier]", "Select lowest freight quote"),
        "decision": ("e-Way Bill Generated?", "Authorize Gate Pass", "NIC Portal Retry"),
        "step3": ("4. Truck Dispatched", "Delivery challan & gate out"),
        "handoff": ("5. Customer & Finance", "In-transit tracking & AR invoice"),
        "err_text": "e-Way bill API timeout or PIN code distance mismatch",
        "secondary": ("Upload Signed POD", "Dispatcher uploads customer delivery receipt to finalize delivery"),
        "walkthrough": [
            ("Dispatch Order Review", "Dispatcher opens `/shipping-engine`. The screen displays 4 shipments staged at Dock #01."),
            ("Carrier Selection", "Dispatcher reviews transporter bidding responses, selecting 'VRL Logistics' based on contract rate and guaranteed transit time."),
            ("Vehicle Placement & Verification", "Truck arrives at dock. Dispatcher verifies driver license, truck registration number, and loads the numbered cartons."),
            ("Statutory e-Way Bill & IRN Generation", "Dispatcher clicks `[Generate Statutory e-Way Bill]`. System connects to government GST API, generating e-Way Bill `EWB-991827361` with official QR barcode."),
            ("Gate Outward Pass & Departure", "System prints Delivery Challan and Gate Outward Pass. Truck departs; shipment status transitions to `IN_TRANSIT` with live SMS tracking for the customer.")
        ],
        "modals_forms": [
            ("Carrier Assignment Modal", "Transporter Dropdown, Vehicle Registration, Driver Name, Mobile, Freight Rate ($)."),
            ("e-Way Bill Generation Modal", "Consignor Address, Consignee GSTIN, HSN Code, Approx Distance (km), Transport Mode (Road)."),
            ("Proof of Delivery Modal", "Recipient Name, Delivery Date/Time, Remarks, File Upload (PDF/JPG signed POD).")
        ],
        "error_states": "System blocks gate exit without a valid statutory e-Way Bill for consignments over statutory threshold ($500 / ₹50,000).",
        "handoff_summary": "Confirmed dispatch triggers final AR Tax Invoice generation in Finance and updates customer order tracking."
    },
    {
        "id": "uf16_returns_rma",
        "num": "16",
        "name": "Customer Returns & Reverse Logistics",
        "route": "/returns",
        "persona": "Customer Support Lead, Reverse QC Engineer, Inventory Storekeeper",
        "permission": "returns:read, returns:write, rma:inspect",
        "overview": "Customer return authorization (RMA), reverse logistics intake, technical diagnostics, dispositioning (restock, rework, scrap), and financial credit note or replacement order issuance.",
        "screen_controls": [
            ("RMA Claims Table", "Columns: RMA #, Customer, Original Invoice, Reason, Status, Action."),
            ("[+ New Return Claim] CTA", "Initiates RMA ticket linked to historical sales invoice."),
            ("Reverse QC Diagnostic Panel", "Detailed technical testing checklist to determine defect root cause."),
            ("Disposition Selector", "Radio buttons: (1) Restock to Good Inventory; (2) Rework; (3) Scrap/Write-Off.")
        ],
        "step1": ("1. Land on /returns", "Inspect RMA Claims"),
        "step2": ("2. Click [+ New RMA]", "Validate Original SO / Serial"),
        "decision": ("Under Warranty?", "Approve Return", "Decline Out-of-Warranty"),
        "step3": ("4. Diagnostics & Disposition", "Restock, Rework, or Scrap"),
        "handoff": ("5. Issue Credit Note", "Finance refunds customer"),
        "err_text": "Serial number not found in historical sales dispatches",
        "secondary": ("Print Reverse Pickup Challan", "Generates return shipping label for customer courier pickup"),
        "walkthrough": [
            ("Claim Initiation", "Customer support rep navigates to `/returns` and clicks `[+ New RMA Ticket]`. They input Customer Name and Serial Number `INV-2026-0881`."),
            ("Warranty Validation", "System checks serial against original sales dispatch history: unit was delivered 45 days ago and is under 2-year manufacturer warranty. RMA is approved."),
            ("Physical Gate Inward", "Courier delivers returned package. Storekeeper checks inward pass and moves box to Quarantine Returns area."),
            ("Reverse QC Diagnostics", "Quality engineer tests unit on diagnostic bench. Defect is identified as faulty cooling fan. Engineer classifies disposition as `REWORK`."),
            ("Resolution & Credit Note", "Unit is transferred to repair shop floor. System auto-generates replacement dispatch or triggers Finance AR to issue a Credit Note.")
        ],
        "modals_forms": [
            ("Create RMA Modal", "Customer Lookup, Sales Invoice #, Item Serial #, Return Reason (Transit Damage, Defective, Wrong Item)."),
            ("Reverse QC Inspection Modal", "Serial Verified (toggle), Damage Severity, Diagnostic Notes, Final Disposition (Restock/Rework/Scrap)."),
            ("Credit Note Request Modal", "Original Invoice Amount, Restocking Fee Deduction %, Final Credit Amount.")
        ],
        "error_states": "System blocks warranty claims if serial number has been tampered with or warranty period has expired.",
        "handoff_summary": "Re-inducts restocked items into inventory and routes refund credit requests to Finance AR."
    },
    {
        "id": "uf17_finance_accounting",
        "num": "17",
        "name": "Finance, Invoicing & 3-Way Match",
        "route": "/finance, /landed-cost",
        "persona": "Accounts Payable Officer, Accounts Receivable Lead, Chief Financial Officer",
        "permission": "finance:read, invoice:post, payment:disburse",
        "overview": "Financial nucleus: automated 3-Way Matching (PO vs GRN vs Vendor Bill), AP payment vouchers, AR tax invoice issuance, tax withholding (TDS/GST), and landed cost capitalization.",
        "screen_controls": [
            ("3-Way Match Audit Console", "Side-by-side comparison table: PO Lines vs GRN Receipts vs Vendor Bill."),
            ("Variance Flag Warning", "Red highlight if vendor invoice price exceeds PO price by >1%."),
            ("[Approve AP Invoice] CTA", "Books the expense and queues invoice for payment disbursement."),
            ("[Run Payment Batch] Button", "Generates electronic bank clearing file (NEFT/RTGS/ACH) for approved bills.")
        ],
        "step1": ("1. Land on /finance", "Review AP Invoices"),
        "step2": ("2. Click [3-Way Match]", "Run automated line matching"),
        "decision": ("Within Tolerance?", "Approve Payment", "Discrepancy Hold"),
        "step3": ("4. Invoice Posted", "Book to Accounts Payable"),
        "handoff": ("5. Bank Disbursement", "Disburse via NEFT batch"),
        "err_text": "Price variance exceeds authorized tolerance limit (+2.5%)",
        "secondary": ("Landed Cost Capitalization", "Apportion freight/customs duty into inventory unit cost"),
        "walkthrough": [
            ("Vendor Bill Ingestion", "AP clerk navigates to `/finance` and clicks `[+ Ingest Vendor Bill]`. They select Vendor `Exide Batteries` and input invoice amount `$25,000`."),
            ("Automated 3-Way Matching", "Clerk clicks `[Run 3-Way Match]`. System compares: (1) PO Unit Price ($50.00); (2) GRN Accepted Quantity (500 units); (3) Invoice Total ($25,000). All lines align perfectly."),
            ("Tax Withholding Calculation", "System computes TDS deduction under Section 194C (2%) and records net payable amount ($24,500), booking debit to Inventory Asset and credit to AP."),
            ("Approval & Payment Queue", "Finance Controller reviews matched bill and clicks `[Approve for Disbursement]`. Status transitions to `SCHEDULED_FOR_PAYMENT`."),
            ("Bank File Export", "On Friday payment run, Treasury officer clicks `[Export Bank Payout File]`. System outputs bank-compliant NEFT batch file and marks invoices as `PAID`.")
        ],
        "modals_forms": [
            ("Ingest Vendor Bill Modal", "Vendor Dropdown, Bill Number, Bill Date, Total Amount, Tax Breakdown, Linked PO #."),
            ("3-Way Match Discrepancy Dialog", "Line Item Price Variance, Accepted vs Billed Qty, Dispute Reason, Send Vendor Notice toggle."),
            ("Payment Batch Disbursement Modal", "Bank Disbursement Account, Payment Method (NEFT/RTGS/Wire), Payout Date, Payment Voucher Notes.")
        ],
        "error_states": "System blocks payment approval if 3-way match fails; prevents posting to closed accounting periods.",
        "handoff_summary": "Clears vendor payables, updates general ledger asset accounts, and unfreezes vendor credit."
    },
    {
        "id": "uf18_admin_platform",
        "num": "18",
        "name": "Platform Administration & Audit",
        "route": "/users, /documents, /audit, /configuration",
        "persona": "System Administrator, Security Auditor, Compliance Officer",
        "permission": "user:write, audit:read, system:admin",
        "overview": "Administrative governance: manages user accounts, role-based access control (RBAC), multi-facility site scoping, document archiving and reprint, outbound notification logs, and immutable audit logs.",
        "screen_controls": [
            ("User Management Console", "User directory showing email, assigned roles, site scoping, and active status."),
            ("Role & Permission Matrix", "Interactive checkbox grid granting granular permissions per module."),
            ("Document Archive Search", "Repository of all generated PO, GRN, Packing Slip, and Invoice PDFs with reprints."),
            ("Immutable Audit Trail Log", "Filterable log capturing timestamp, user ID, IP address, and JSON before/after state diff.")
        ],
        "step1": ("1. Land on /users", "Inspect User Directory"),
        "step2": ("2. Click [+ Add User]", "Assign roles & site scope"),
        "decision": ("MFA Enforced?", "Activate User", "Prompt Setup"),
        "step3": ("4. User Active", "Send welcome invite email"),
        "handoff": ("5. Operational Login", "Operator accesses portal"),
        "err_text": "Cannot assign administrator role without 2FA",
        "secondary": ("Reprint Historical Document", "Admin searches document archive and regenerates signed PDF"),
        "walkthrough": [
            ("User Provisioning", "Admin navigates to `/users` and clicks `[+ Invite User]`. They enter user email, full name, and assign role `Warehouse Lead`."),
            ("Site Scoping Assignment", "Admin restricts user access by checking only `Factory: Alpha Plant` and `Warehouse: WH-01`. The user will be unable to see other company facilities."),
            ("Role Permission Tuning", "Admin opens `/configuration`, adjusting permissions to grant this role read/write access to GRN and Inventory, but read-only access to Finance."),
            ("Audit Trail Review", "Compliance officer visits `/audit`. They filter by Entity Type `PurchaseOrder` and User ID `john.doe` to review exact field mutations (old price vs new price) for a SOX audit."),
            ("Document Reprint", "Storekeeper lost physical GRN sticker sheet. Admin opens `/documents`, locates document ID, and clicks `[Reprint Document]`, instantly downloading the original encrypted PDF.")
        ],
        "modals_forms": [
            ("User Provisioning Modal", "Full Name, Corporate Email, Role Selector, Factory Scoping Checkboxes, Warehouse Scoping Checkboxes."),
            ("Role Editor Modal", "Role Name, Description, Module Permission Matrix (Read, Write, Approve, Delete checkboxes)."),
            ("Document Reprint Modal", "Document ID, Output Format, Digital Signature Verification Status, Reprint Reason.")
        ],
        "error_states": "System blocks deleting a user account with active transactional history (forces deactivation instead); audit logs are write-only and tamper-proof.",
        "handoff_summary": "Secures the platform and guarantees full traceability across all operational user actions."
    }
]


def generate_html_userflows():
    css = get_userflow_css()
    html = []
    html.append(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Axon ERP - Detailed Module User Flows Guide</title>
<style>
{css}
</style>
</head>
<body>
""")

    # 1. COVER PAGE
    html.append("""
    <div class="cover-page">
        <div>
            <div class="cover-brand">Axon ERP &bull; UX Architecture Series</div>
            <h1 class="cover-title">Comprehensive Module-by-Module<br>Operator User Flows &amp;<br>Interaction Specification</h1>
            <div class="cover-subtitle">Detailed screen-by-screen human interaction journeys, vector user flow diagrams, form controls, validation rules, error handling, and cross-persona handoffs across all 18 ERP modules.</div>
            <div class="cover-accent-bar"></div>
            
            <div class="cover-meta-grid">
                <div>
                    <div class="meta-item-label">Platform Version</div>
                    <div class="meta-item-val">v2.4.0 Enterprise Edition</div>
                </div>
                <div>
                    <div class="meta-item-label">Target Audience</div>
                    <div class="meta-item-val">Operations Leads, UX Architects, End-User Operators</div>
                </div>
                <div>
                    <div class="meta-item-label">UX Architecture</div>
                    <div class="meta-item-val">React &bull; Tailwind &bull; WMS Mobile &bull; RBAC Scoped</div>
                </div>
                <div>
                    <div class="meta-item-label">Publication Date</div>
                    <div class="meta-item-val">October 2026</div>
                </div>
            </div>
        </div>
        <div class="cover-footer">
            &copy; 2026 Axon Technologies Inc. All rights reserved. Operator Training &amp; Interaction Architecture Manual.
        </div>
    </div>
    """)

    # 2. EXECUTIVE UX FRAMEWORK & GLOBAL NAVIGATION
    html.append("""
    <div class="page">
        <h2>Executive UX Framework &amp; Global Navigation Architecture</h2>
        <p>Axon ERP is engineered around <strong>role-tailored operator experiences</strong>. Unlike monolithic ERP systems with cluttered forms, Axon optimizes human-computer interaction through clean, contextual workspaces, fast keyboard navigation, and specialized mobile terminal interfaces for industrial shop floors and warehouses.</p>
        
        <h3 style="margin-top: 12px; margin-bottom: 6px;">Global Navigation Layout Hierarchy</h3>
        <p>The screen workspace is structured into four consistent interface zones across every module:</p>
        
        <div class="grid-2" style="margin-bottom: 12px;">
            <div class="card card-indigo">
                <div class="card-title">1. Collapsible Sidebar &amp; Role Filtering</div>
                <p style="font-size: 7.6pt; margin: 0;">
                    &bull; <strong>Adaptive Rendering:</strong> The navigation sidebar strictly renders only the operational modules for which the logged-in user possesses valid Casbin permissions.<br>
                    &bull; <strong>Domain Clustering:</strong> Organized into logical groupings: <em>Overview &amp; SCM</em>, <em>Procurement</em>, <em>Warehouse &amp; Logistics</em>, <em>Manufacturing</em>, <em>Sales &amp; Orders</em>, and <em>Finance</em>.<br>
                    &bull; <strong>Pinning &amp; Collapsing:</strong> Operators can collapse the sidebar to icon-only mode to maximize screen real estate on factory touch monitors.
                </p>
            </div>
            <div class="card card-cyan">
                <div class="card-title">2. Global Header &amp; Facility Site Scoper</div>
                <p style="font-size: 7.6pt; margin: 0;">
                    &bull; <strong>Active Facility Scoper Pill:</strong> Prominent badge in the top navigation bar indicating the user's active operating factory (e.g. <code>Alpha Plant</code>) and warehouse (e.g. <code>WH-01</code>).<br>
                    &bull; <strong>Instant Site Context Switch:</strong> Multi-facility operators can click the pill to switch operational context without logging out.<br>
                    &bull; <strong>Command Palette (Cmd/Ctrl + K):</strong> Global search shortcut to instantly locate any SKU, Purchase Order, Sales Order, or Customer master record.
                </p>
            </div>
        </div>

        <div class="grid-2" style="margin-bottom: 12px;">
            <div class="card card-emerald">
                <div class="card-title">3. Dense Interactive Data Tables</div>
                <p style="font-size: 7.6pt; margin: 0;">
                    &bull; <strong>Sticky Header &amp; Pagination:</strong> Table headers remain fixed while scrolling; controls support 25, 50, or 100 rows per page.<br>
                    &bull; <strong>Contextual Quick Actions:</strong> Row hover surfaces inline action pills (e.g. <code>[View Detail]</code>, <code>[Edit]</code>, <code>[Print Labels]</code>).<br>
                    &bull; <strong>Color-Coded Status Badges:</strong> Standardized badges indicate lifecycle state (Green for Approved/Active, Amber for Pending/QC, Red for Blocked/Rejected).
                </p>
            </div>
            <div class="card card-amber">
                <div class="card-title">4. Slide-Over Drawers &amp; Action Modals</div>
                <p style="font-size: 7.6pt; margin: 0;">
                    &bull; <strong>Non-Destructive Navigation:</strong> Creation forms and inspection scorecards open in right-hand slide-over drawers, preserving table search filters.<br>
                    &bull; <strong>Instant Form Validation:</strong> Client-side validation catches missing fields and invalid tax codes before network submission.<br>
                    &bull; <strong>Unsaved Changes Guard:</strong> Warns operators before closing an incomplete drawer.
                </p>
            </div>
        </div>

        <h3 style="margin-top: 10px; margin-bottom: 6px;">Master User Flow Table of Contents</h3>
        <div style="margin-bottom: 8px;">
            <div class="toc-item"><span class="toc-num">UF 01</span><span class="toc-title">Login, Authentication, SSO &amp; User Profile</span><span class="toc-dots"></span><span class="toc-module">/login, /profile</span></div>
            <div class="toc-item"><span class="toc-num">UF 02</span><span class="toc-title">Dashboard &amp; Supply Chain Control Tower</span><span class="toc-dots"></span><span class="toc-module">/, /sc-control-tower</span></div>
            <div class="toc-item"><span class="toc-num">UF 03</span><span class="toc-title">Parties Directory &amp; AVL Governance</span><span class="toc-dots"></span><span class="toc-module">/parties, /avl-governance</span></div>
            <div class="toc-item"><span class="toc-num">UF 04</span><span class="toc-title">Business Entities &amp; Legal Invoicing Setup</span><span class="toc-dots"></span><span class="toc-module">/po-invoice</span></div>
            <div class="toc-item"><span class="toc-num">UF 05</span><span class="toc-title">Facilities, Factory &amp; Multi-Tier WMS Bins</span><span class="toc-dots"></span><span class="toc-module">/factory-warehouse, /wms-bins</span></div>
            <div class="toc-item"><span class="toc-num">UF 06</span><span class="toc-title">Product Catalog &amp; Engineering BOM</span><span class="toc-dots"></span><span class="toc-module">/products</span></div>
            <div class="toc-item"><span class="toc-num">UF 07</span><span class="toc-title">Supply Chain Planning: Demand, MRP &amp; DRP</span><span class="toc-dots"></span><span class="toc-module">/mrp, /drp, /forecasting</span></div>
            <div class="toc-item"><span class="toc-num">UF 08</span><span class="toc-title">Procurement, RFQ &amp; Purchase Orders</span><span class="toc-dots"></span><span class="toc-module">/procurement, /blanket-po</span></div>
            <div class="toc-item"><span class="toc-num">UF 09</span><span class="toc-title">Inbound Logistics &amp; Gate Entry</span><span class="toc-dots"></span><span class="toc-module">/logistics, /freight-tms</span></div>
            <div class="toc-item"><span class="toc-num">UF 10</span><span class="toc-title">Goods Receipt (GRN), QC &amp; QR Labeling</span><span class="toc-dots"></span><span class="toc-module">/warehouse, /warehouse-qc</span></div>
            <div class="toc-item"><span class="toc-num">UF 11</span><span class="toc-title">Inventory Control, Ledger &amp; Cycle Counts</span><span class="toc-dots"></span><span class="toc-module">/inventory, /cycle-counts</span></div>
            <div class="toc-item"><span class="toc-num">UF 12</span><span class="toc-title">Manufacturing, Work Orders &amp; IPQC</span><span class="toc-dots"></span><span class="toc-module">/production, /quality-ipqc</span></div>
            <div class="toc-item"><span class="toc-num">UF 13</span><span class="toc-title">Sales Management &amp; Order Intake Booking</span><span class="toc-dots"></span><span class="toc-module">/orders, /customer-portal</span></div>
            <div class="toc-item"><span class="toc-num">UF 14</span><span class="toc-title">Wave Picking, Packing &amp; WMS Mobile Scanners</span><span class="toc-dots"></span><span class="toc-module">/wave-picking, /wms-mobile</span></div>
            <div class="toc-item"><span class="toc-num">UF 15</span><span class="toc-title">Outbound Logistics, TMS &amp; Dispatch</span><span class="toc-dots"></span><span class="toc-module">/logistics, /shipping-engine</span></div>
            <div class="toc-item"><span class="toc-num">UF 16</span><span class="toc-title">Customer Returns &amp; Reverse Logistics (RMA)</span><span class="toc-dots"></span><span class="toc-module">/returns</span></div>
            <div class="toc-item"><span class="toc-num">UF 17</span><span class="toc-title">Finance, Invoicing &amp; 3-Way Match</span><span class="toc-dots"></span><span class="toc-module">/finance, /landed-cost</span></div>
            <div class="toc-item"><span class="toc-num">UF 18</span><span class="toc-title">Platform Administration, Users &amp; Audit Trail</span><span class="toc-dots"></span><span class="toc-module">/users, /audit, /documents</span></div>
        </div>
    </div>
    """)

    # 3. GLOBAL MULTI-PERSONA ROLE HIERARCHY
    html.append("""
    <div class="page">
        <h2>Global Persona Roles &amp; Operational Responsibilities</h2>
        <p>In Axon ERP, operational tasks flow sequentially between human personas. The matrix below defines the primary user roles, their day-to-day screens, and their core responsibilities across the platform.</p>
        
        <table class="spec-table">
            <thead>
                <tr>
                    <th style="width: 18%;">User Persona / Role</th>
                    <th style="width: 22%;">Primary Daily Routes</th>
                    <th style="width: 30%;">Key Responsibilities &amp; Actions</th>
                    <th style="width: 30%;">Upstream Inputs &amp; Downstream Handoffs</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Procurement Buyer</strong></td>
                    <td><code>/procurement</code><br><code>/parties</code><br><code>/vendor-portal</code></td>
                    <td>Reviews auto-generated PRs &bull; Issues vendor RFQs &bull; Drafts Purchase Orders &bull; Negotiates commercial terms.</td>
                    <td><strong>In:</strong> Requisitions from MRP Planner.<br><strong>Out:</strong> Dispatches PO to Vendor; alerts Warehouse.</td>
                </tr>
                <tr>
                    <td><strong>Security Gate Officer</strong></td>
                    <td><code>/logistics</code><br><code>/freight-tms</code></td>
                    <td>Inspects arriving trucks &bull; Verifies delivery challans &bull; Captures weighbridge scale weight &bull; Issues Gate Inward Pass.</td>
                    <td><strong>In:</strong> Vendor ASN.<br><strong>Out:</strong> Releases truck to Unloading Dock and Storekeeper.</td>
                </tr>
                <tr>
                    <td><strong>Warehouse Storekeeper</strong></td>
                    <td><code>/warehouse</code><br><code>/inventory</code><br><code>/wms-bins</code></td>
                    <td>Counts unloaded packages &bull; Drafts Goods Receipt Notes (GRN) &bull; Prints QR stickers &bull; Deposits pallets into WMS bins.</td>
                    <td><strong>In:</strong> Gate Entry Pass.<br><strong>Out:</strong> Delivers sample boxes to QC Inspection staging.</td>
                </tr>
                <tr>
                    <td><strong>QC Sampling Inspector</strong></td>
                    <td><code>/warehouse-qc/:id</code><br><code>/quality-ipqc</code></td>
                    <td>Executes physical/lab testing &bull; Records parameter measurements &bull; Issues Accepted / Rejected / Quarantine dispositions.</td>
                    <td><strong>In:</strong> Staged materials from Storekeeper.<br><strong>Out:</strong> Approves items for stock or issues RTV note.</td>
                </tr>
                <tr>
                    <td><strong>Production Supervisor</strong></td>
                    <td><code>/production</code><br><code>/products</code><br><code>/subcontracting</code></td>
                    <td>Schedules manufacturing runs &bull; Stages component BOM items &bull; Tracks routing work centers &bull; Yields finished goods.</td>
                    <td><strong>In:</strong> Demand from Sales or MRP.<br><strong>Out:</strong> Delivers finished goods to Finished Goods Warehouse.</td>
                </tr>
                <tr>
                    <td><strong>Order Desk Coordinator</strong></td>
                    <td><code>/orders</code><br><code>/customer-portal</code></td>
                    <td>Reviews customer quotes &bull; Books Sales Orders &bull; Verifies credit limits &bull; Reserves finished stock &bull; Releases to wave pick.</td>
                    <td><strong>In:</strong> Customer RFQ/PO.<br><strong>Out:</strong> Pushes approved lines to Warehouse Picking queue.</td>
                </tr>
                <tr>
                    <td><strong>Mobile Scanner Picker</strong></td>
                    <td><code>/wave-picking</code><br><code>/wms-mobile</code></td>
                    <td>Carries handheld RF scanner &bull; Follows shortest-path travel prompts &bull; Scans bin barcodes and item barcodes.</td>
                    <td><strong>In:</strong> Released Pick Wave.<br><strong>Out:</strong> Delivers picked totes to Packing Table lead.</td>
                </tr>
                <tr>
                    <td><strong>Packing Table Lead</strong></td>
                    <td><code>/wave-picking</code><br><code>/shipping-engine</code></td>
                    <td>Scan-verifies 100% item barcodes &bull; Packs into cartons &bull; Weighs boxes on scale &bull; Prints serialized carton barcodes.</td>
                    <td><strong>In:</strong> Totes from Picker.<br><strong>Out:</strong> Stages sealed cartons at shipping dock for Logistics.</td>
                </tr>
                <tr>
                    <td><strong>Outbound Dispatcher</strong></td>
                    <td><code>/logistics</code><br><code>/statutory-logistics</code></td>
                    <td>Assigns freight transporters &bull; Connects to NIC API to generate e-Way Bills &bull; Issues Delivery Challans &bull; Gate Out pass.</td>
                    <td><strong>In:</strong> Packed cartons from Packing Lead.<br><strong>Out:</strong> Hands shipment to driver; triggers Finance invoice.</td>
                </tr>
                <tr>
                    <td><strong>Accounts Payable Clerk</strong></td>
                    <td><code>/finance</code><br><code>/landed-cost</code></td>
                    <td>Ingests vendor invoices &bull; Executes automated 3-Way Matching against PO and GRN &bull; Prepares bank NEFT payment batches.</td>
                    <td><strong>In:</strong> Vendor Bill, Approved GRN, PO.<br><strong>Out:</strong> Treasury disbursement; updates Vendor Ledger.</td>
                </tr>
                <tr>
                    <td><strong>System Administrator</strong></td>
                    <td><code>/users</code><br><code>/audit</code><br><code>/configuration</code></td>
                    <td>Provisions user accounts &bull; Assigns RBAC roles &bull; Scopes multi-facility access &bull; Audits system compliance logs.</td>
                    <td><strong>In:</strong> HR / IT onboarding tickets.<br><strong>Out:</strong> Issues credentials and monitors security health.</td>
                </tr>
            </tbody>
        </table>

        <div class="card card-indigo" style="margin-top: 10px;">
            <div class="card-title">Cross-Persona Hand-off Paradigm</div>
            <p style="font-size: 7.7pt; margin: 0;">
                In Axon ERP, when an operator completes a stage (e.g. Storekeeper approves a GRN), the system performs two simultaneous actions: (1) atomically commits the database state; and (2) deposits the task directly into the next persona's operational queue (QC Inspector console). This eliminates manual emails, phone calls, and paper handoffs.
            </p>
        </div>
    </div>
    """)

    # 4. MODULE USER FLOW PAGES (18 MODULES)
    for mod in USERFLOW_MODULES:
        svg_diagram = generate_svg_userflow(mod)
        
        walkthrough_html = []
        for w_title, w_desc in mod["walkthrough"]:
            walkthrough_html.append(f"<li><strong>{w_title}:</strong> {w_desc}</li>")
        walkthrough_rendered = "\n".join(walkthrough_html)

        controls_html = []
        for c_title, c_desc in mod["screen_controls"]:
            controls_html.append(f"<li><span class=\"ui-label\">{c_title}</span><span class=\"ui-desc\">{c_desc}</span></li>")
        controls_rendered = "\n".join(controls_html)

        modals_html = []
        for m_title, m_desc in mod["modals_forms"]:
            modals_html.append(f"<li><strong>{m_title}:</strong> {m_desc}</li>")
        modals_rendered = "\n".join(modals_html)

        html.append(f"""
        <div class="page">
            <div class="module-header">
                <div class="module-header-title">
                    <span class="module-title-text">User Flow {mod['num']}: {mod['name']}</span>
                    <span class="badge badge-indigo">{mod['route']}</span>
                </div>
                <div class="module-meta-strip">
                    <span><strong>Target Persona:</strong> {mod['persona']}</span>
                    <span><strong>Required Permission:</strong> <code>{mod['permission']}</code></span>
                </div>
            </div>

            <p style="font-size: 8pt; margin-bottom: 5px;">{mod['overview']}</p>

            <div class="svg-container">
                {svg_diagram}
            </div>

            <div class="grid-2">
                <div class="card card-indigo">
                    <div class="card-title">Step-by-Step Operator Interaction Walkthrough</div>
                    <ul class="steps-list">
                        {walkthrough_rendered}
                    </ul>
                </div>
                <div class="card card-cyan">
                    <div class="card-title">Screen Layout &amp; Key UI Controls</div>
                    <ul class="ui-specs-list">
                        {controls_rendered}
                    </ul>
                    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid #cffafe;">
                        <span style="font-size: 7.5pt; font-weight: 800; color: #0e7490; text-transform: uppercase;">Modals &amp; Interactive Forms</span>
                        <ul class="steps-list" style="margin-top: 3px;">
                            {modals_rendered}
                        </ul>
                    </div>
                </div>
            </div>

            <div class="grid-2" style="margin-top: -2px;">
                <div class="card card-rose">
                    <div class="card-title">Error States, Validation &amp; Recovery</div>
                    <p style="font-size: 7.6pt; margin: 0;">{mod['error_states']}</p>
                </div>
                <div class="card card-emerald">
                    <div class="card-title">Downstream Persona Handoff</div>
                    <p style="font-size: 7.6pt; margin: 0;">{mod['handoff_summary']}</p>
                </div>
            </div>
        </div>
        """)

    # 5. CROSS-PERSONA OPERATIONAL JOURNEYS (P2P & O2C)
    html.append("""
    <div class="page">
        <h2>End-to-End Cross-Persona Operational Journeys</h2>
        <p>This section illustrates how multiple user personas collaborate step-by-step to execute the two primary commercial engines of the company.</p>

        <div class="card card-indigo" style="margin-bottom: 10px;">
            <div class="card-title">Journey 1: Procure-to-Pay (P2P) Operator Handshake Sequence</div>
            <p style="font-size: 7.6pt; line-height: 1.4; margin: 0;">
                <strong>1. Master Scheduler (on <code>/mrp</code>):</strong> Executes MRP netting run. System flags net deficit of 500 battery cells. Scheduler clicks <code>[Convert to Purchase Requisition]</code>.<br>
                <strong>2. Procurement Buyer (on <code>/procurement</code>):</strong> Reviews incoming PR. Invites 3 AVL vendors to bid on RFQ. Selects lowest compliant quotation. Drafts PO for $25,000. Clicks <code>[Submit for Approval]</code>.<br>
                <strong>3. Supply Chain VP (via Notification Banner):</strong> Receives pending approval badge. Reviews digital PO line items and signs off. PO PDF auto-emails to supplier.<br>
                <strong>4. Supplier Dispatcher (via <code>/vendor-portal</code>):</strong> Acknowledges PO. Enters vehicle registration and Advance Shipping Notice (ASN).<br>
                <strong>5. Security Gate Officer (on <code>/logistics</code>):</strong> Truck arrives. Officer verifies container seal, captures scale gross weight (14,200 kg), and prints Gate Pass <code>INW-0042</code> with Unloading Dock #03 assigned.<br>
                <strong>6. Warehouse Storekeeper (on <code>/warehouse</code>):</strong> Tallies unloaded boxes against PO. Discovers 500 units in good order. Clicks <code>[+ Create Draft GRN]</code>.<br>
                <strong>7. QC Inspector (on <code>/warehouse-qc/:id</code>):</strong> Tests 10 sample cells for internal resistance and voltage. Records test scores. Clicks <code>[Accept Batch]</code>.<br>
                <strong>8. Warehouse Storekeeper (on <code>/warehouse</code>):</strong> Prints 500 serialized thermal QR stickers (4x2). Scans pallet into Bin <code>A-02-1</code>. Stock ledger updates.<br>
                <strong>9. Accounts Payable Clerk (on <code>/finance</code>):</strong> Ingests vendor tax bill. Clicks <code>[Run 3-Way Match]</code>. PO price, GRN accepted quantity, and invoice match 100%. Books AP liability.<br>
                <strong>10. Treasury Officer (on <code>/finance</code>):</strong> Executes Friday bank run. Generates NEFT bank payout batch. Vendor receives electronic settlement.
            </p>
        </div>

        <div class="card card-emerald" style="margin-bottom: 10px;">
            <div class="card-title">Journey 2: Order-to-Cash (O2C) Operator Handshake Sequence</div>
            <p style="font-size: 7.6pt; line-height: 1.4; margin: 0;">
                <strong>1. Sales Representative (on <code>/orders</code>):</strong> Inputs commercial quotation for 25 units of Solar Inverter. Customer accepts quote. Rep clicks <code>[Convert to Sales Order]</code>.<br>
                <strong>2. Commercial Credit Analyst (via Order Hold Console):</strong> System checks customer exposure ($32,000) against $50,000 credit ceiling. Credit passes; order approved.<br>
                <strong>3. Inventory Engine (Automated Background):</strong> System locks soft reservation on 25 finished units in Warehouse <code>WH-FG-01</code>.<br>
                <strong>4. Wave Pick Planner (on <code>/wave-picking</code>):</strong> Consolidates 10 orders bound for South Region into Pick Wave #12. Clicks <code>[Release Wave]</code>.<br>
                <strong>5. Mobile Scanner Picker (on <code>/wms-mobile</code>):</strong> Handheld RF scanner directs picker through aisles in shortest sequence. Picker scans bin and item barcodes.<br>
                <strong>6. Packing Table Lead (on <code>/wave-picking</code>):</strong> Scans each inverter at packing station. Weighs box on digital scale (42.5 kg). Prints serialized carton shipping barcode.<br>
                <strong>7. Logistics Dispatcher (on <code>/shipping-engine</code>):</strong> Selects contract transporter. Clicks <code>[Generate Statutory e-Way Bill]</code> via government API. Prints Delivery Challan.<br>
                <strong>8. Security Officer (at Factory Gate):</strong> Inspects gate outward pass and releases vehicle. Shipment transitions to <code>IN_TRANSIT</code>.<br>
                <strong>9. Finance AR Lead (on <code>/finance</code>):</strong> Gate outward event auto-generates official GST Tax Invoice and emails copy to customer.<br>
                <strong>10. Logistics Coordinator (on <code>/logistics</code>):</strong> Driver delivers inverter; customer signs physical receipt. Coordinator uploads signed POD, closing order.
            </p>
        </div>
    </div>
    """)

    # 6. JOURNEYS 3 & 4: MANUFACTURING & AP 3-WAY MATCH
    html.append("""
    <div class="page">
        <h2>End-to-End Cross-Persona Operational Journeys (Cont.)</h2>
        <p>Walkthroughs for manufacturing shop floor execution and accounts payable 3-way discrepancy resolution.</p>

        <div class="card card-cyan" style="margin-bottom: 10px;">
            <div class="card-title">Journey 3: Shop Floor Work Order &amp; IPQC Assembly Sequence</div>
            <p style="font-size: 7.6pt; line-height: 1.4; margin: 0;">
                <strong>1. Master Scheduler (on <code>/mrp</code>):</strong> Schedules Production Order for 100 units of 48V Lithium Battery Pack.<br>
                <strong>2. Production Supervisor (on <code>/production</code>):</strong> Opens Work Order. System validates component availability (cells, BMS, enclosure). Supervisor clicks <code>[Allocate &amp; Stage]</code>.<br>
                <strong>3. Warehouse Storekeeper (on <code>/inventory</code>):</strong> Picks raw materials from <code>WH-RM-01</code> and transfers them to Shop Floor WIP Staging Bins (<code>WH-WIP-01</code>).<br>
                <strong>4. Shop Floor Line Lead (on Shop Floor Monitor):</strong> Begins Stage 1 (Cell Welding). Marks 100 packs welded; advances order to Stage 2 (BMS Integration).<br>
                <strong>5. IPQC Inspector (on <code>/quality-ipqc</code>):</strong> Mandatory quality checkpoint. Inspector tests voltage calibration across 5 packs. Enters test telemetry; digitally signs gate pass.<br>
                <strong>6. Shop Floor Line Lead:</strong> Completes Stage 3 (Enclosure Assembly &amp; Burn-in Test).<br>
                <strong>7. Production Supervisor (on <code>/production/:id</code>):</strong> Clicks <code>[Complete Production Run]</code>. Enters final yield: 99 units passed, 1 unit rejected for rework. System auto-prints Finished Good serial barcodes.<br>
                <strong>8. Warehouse Storekeeper (on <code>/inventory</code>):</strong> Scans completed battery packs into Finished Goods Warehouse <code>WH-FG-01</code>. Units become immediately available for sales dispatch.
            </p>
        </div>

        <div class="card card-rose" style="margin-bottom: 10px;">
            <div class="card-title">Journey 4: AP 3-Way Match Discrepancy &amp; Landed Cost Capitalization</div>
            <p style="font-size: 7.6pt; line-height: 1.4; margin: 0;">
                <strong>1. Vendor (via Email / Portal):</strong> Submits Tax Invoice #INV-9021 for $12,500 for delivery of raw aluminum enclosures.<br>
                <strong>2. Accounts Payable Clerk (on <code>/finance</code>):</strong> Enters invoice. System runs automated 3-Way Match against PO #PO-1044 and GRN #GRN-0882.<br>
                <strong>3. Automated Discrepancy Flag:</strong> System detects that the PO unit rate was $24.00, but the vendor billed $25.00 per unit (a $500 price variance exceeding the 1% tolerance threshold). Status locks on <code>MATCH_FAILED_HOLD</code>.<br>
                <strong>4. Procurement Buyer (via Alert Queue):</strong> Reviews discrepancy. Identifies that vendor billed for uncontracted express air freight. Buyer contacts vendor; vendor submits revised credit memo of $500.<br>
                <strong>5. AP Clerk:</strong> Attaches credit memo; 3-way match clears. Clerk approves invoice for payment.<br>
                <strong>6. Cost Accountant (on <code>/landed-cost</code>):</strong> Freight forwarder submits $600 shipping bill for the shipment. Accountant creates Landed Cost Voucher, allocating the $600 proportionately across the enclosures. The stock ledger unit valuation rate increases from $24.00 to $25.20, reflecting true landed cost.
            </p>
        </div>

        <div class="card card-amber">
            <div class="card-title">UX Feedback Mechanisms &amp; Mobile Ergonomics</div>
            <p style="font-size: 7.6pt; line-height: 1.4; margin: 0;">
                &bull; <strong>Audio-Visual Scanning Cues:</strong> In <code>/wms-mobile</code>, successful barcode scans produce a crisp high-frequency tone and green flash; errors trigger a low buzz and red screen border, allowing operators to scan items at high speed without looking at the monitor.<br>
                &bull; <strong>Touch Target Sizing:</strong> All buttons on shop floor and mobile views are padded to minimum 48x48px touch targets, ensuring error-free operation with industrial nitrile or leather gloves.<br>
                &bull; <strong>Optimistic UI Updates:</strong> Table rows update instantly upon clicking an action, while background synchronization handles database commits and rolls back with a red toast if an error occurs.
            </p>
        </div>
    </div>
    """)

    html.append("""
</body>
</html>
""")
    return "\n".join(html)


def main():
    print("==================================================================")
    print("Axon ERP: Compiling Detailed Module Userflows PDF...")
    print("==================================================================")

    output_pdf_path = os.path.abspath("Axon_ERP_Detailed_User_Flows_Guide.pdf")

    print("[1/3] Generating comprehensive Userflow HTML with vector SVGs...")
    html_content = generate_html_userflows()
    print(f"      HTML content generated ({len(html_content):,} bytes).")

    print("[2/3] Compiling PDF via WeasyPrint engine...")
    doc = weasyprint.HTML(string=html_content)
    doc.write_pdf(output_pdf_path)

    pdf_size = os.path.getsize(output_pdf_path)
    print(f"[3/3] PDF compilation completed successfully!")
    print(f"      Target PDF File: {output_pdf_path}")
    print(f"      File Size: {pdf_size / 1024 / 1024:.2f} MB ({pdf_size:,} bytes)")
    print("==================================================================")


if __name__ == "__main__":
    main()
