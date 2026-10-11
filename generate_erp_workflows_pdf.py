#!/usr/bin/env python3
"""
Axon ERP - Workflow & Cross-Module Architecture Specification Generator
Compiles an exhaustive, publication-grade technical PDF detailing all module workflows,
decision engines, state machines, and cross-module integrations with high-fidelity vector flowcharts.
"""

import os
import sys
import weasyprint

def get_base_css():
    return """
    @page {
        size: A4;
        margin: 16mm 14mm 16mm 14mm;
        @top-left {
            content: "AXON ERP | ENTERPRISE SPECIFICATION";
            font-size: 7.5pt;
            font-weight: 700;
            color: #64748b;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            letter-spacing: 0.05em;
        }
        @top-right {
            content: "MODULE WORKFLOWS & LOGIC INTEGRATION";
            font-size: 7.5pt;
            font-weight: 600;
            color: #64748b;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        @bottom-left {
            content: "CONFIDENTIAL & PROPRIETARY — SYSTEM ARCHITECTURE REFERENCE";
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
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0b1329 100%);
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
        background: rgba(37, 99, 235, 0.25);
        border: 1px solid rgba(59, 130, 246, 0.5);
        border-radius: 6px;
        font-size: 9pt;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        font-weight: 800;
        color: #60a5fa;
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
        background: linear-gradient(90deg, #2563eb, #38bdf8);
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

    .page-avoid-break {
        page-break-inside: avoid;
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
        border-bottom: 2px solid #2563eb;
        padding-bottom: 4px;
        letter-spacing: -0.01em;
    }

    h3 {
        font-size: 9.5pt;
        font-weight: 700;
        color: #1e293b;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 10px 0 4px 0;
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

    .badge-blue { background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
    .badge-purple { background: #ede9fe; color: #5b21b6; border: 1px solid #c4b5fd; }
    .badge-green { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
    .badge-amber { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
    .badge-slate { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }

    .module-header {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2563eb;
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }

    .module-header-title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }

    .module-title-text {
        font-size: 13pt;
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
        margin: 8px 0 10px 0;
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
        padding: 7px 10px;
    }

    .card-title {
        font-size: 8pt;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .card-purple { border-top: 3px solid #7c3aed; background: #faf5ff; }
    .card-purple .card-title { color: #6b21a8; }

    .card-green { border-top: 3px solid #059669; background: #f0fdf4; }
    .card-green .card-title { color: #065f46; }

    .card-blue { border-top: 3px solid #2563eb; background: #f8fafc; }
    .card-blue .card-title { color: #1e40af; }

    .card-amber { border-top: 3px solid #d97706; background: #fffbeb; }
    .card-amber .card-title { color: #92400e; }

    .steps-list {
        margin: 0;
        padding-left: 14px;
        font-size: 8pt;
    }

    .steps-list li {
        margin-bottom: 4px;
        line-height: 1.35;
    }

    .steps-list strong {
        color: #0f172a;
    }

    .integration-list {
        margin: 0;
        padding: 0;
        list-style: none;
        font-size: 7.8pt;
    }

    .integration-list li {
        padding: 3px 0;
        border-bottom: 1px dashed rgba(0,0,0,0.06);
        display: flex;
        justify-content: space-between;
    }

    .integration-list li:last-child {
        border-bottom: none;
    }

    .integration-item-label {
        font-weight: 700;
        color: #1e293b;
    }

    .integration-item-desc {
        color: #475569;
        text-align: right;
        max-width: 60%;
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
        padding: 4px 0;
        border-bottom: 1px dotted #cbd5e1;
        font-size: 8.5pt;
    }

    .toc-num {
        font-weight: 800;
        color: #2563eb;
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
        font-size: 7.5pt;
    }

    .state-pill {
        display: inline-block;
        padding: 1px 5px;
        border-radius: 3px;
        font-family: monospace;
        font-size: 7pt;
        font-weight: 700;
    }
    .state-draft { background: #e2e8f0; color: #334155; }
    .state-pending { background: #fef3c7; color: #b45309; }
    .state-approved { background: #dcfce7; color: #15803d; }
    .state-rejected { background: #fee2e2; color: #b91c1c; }
    .state-active { background: #dbeafe; color: #1d4ed8; }
    .state-closed { background: #f1f5f9; color: #64748b; }
    """

def generate_svg_flowchart(mod_data):
    """
    Constructs a sharp, balanced vector SVG flowchart.
    Layout (Width: 720, Height: 240):
      - Col 0 (x=15..140): Upstream Inputs (Purple)
      - Col 1 (x=175..300): Process Step 1 & 2 (Blue)
      - Col 2 (x=335..455): Decision Gateway / Validation (Amber)
      - Col 3 (x=490..590): Process Step 3 / Outcome (Blue)
      - Col 4 (x=600..710): Downstream Hand-offs (Emerald)
      - Error loop underneath
    """
    w, h = 720, 240
    up = mod_data.get('up_nodes', [('Upstream Module', 'Input Trigger')])
    steps = mod_data.get('core_steps', [('Step 1', 'Subtext'), ('Step 2', 'Subtext')])
    dec = mod_data.get('decision', ('Validation Check?', 'Pass', 'Fail / Revise'))
    down = mod_data.get('down_nodes', [('Downstream Module', 'Output Handoff')])
    exc = mod_data.get('exception_label', 'Revision / Reject Loop')

    svg = []
    svg.append(f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">')
    svg.append('''
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#475569" />
        </marker>
        <marker id="arr-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#059669" />
        </marker>
        <marker id="arr-red" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#dc2626" />
        </marker>
        <linearGradient id="bgG" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="100%" stop-color="#f8fafc" />
        </linearGradient>
      </defs>
    ''')

    # Background canvas
    svg.append(f'<rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="url(#bgG)" stroke="#e2e8f0" stroke-width="1.2" />')

    # Top Legend Ribbon
    svg.append(f'''
      <g transform="translate(15, 10)">
        <rect x="0" y="0" width="10" height="10" rx="2" fill="#7c3aed" />
        <text x="14" y="8.5" font-size="8" fill="#475569" font-weight="700">UPSTREAM INFLOW</text>
        <rect x="120" y="0" width="10" height="10" rx="2" fill="#2563eb" />
        <text x="134" y="8.5" font-size="8" fill="#475569" font-weight="700">INTERNAL WORKFLOW</text>
        <rect x="250" y="0" width="10" height="10" rx="2" fill="#d97706" />
        <text x="264" y="8.5" font-size="8" fill="#475569" font-weight="700">DECISION GATEWAY</text>
        <rect x="380" y="0" width="10" height="10" rx="2" fill="#059669" />
        <text x="394" y="8.5" font-size="8" fill="#475569" font-weight="700">DOWNSTREAM HANDOFF</text>
      </g>
      <line x1="15" y1="26" x2="{w-15}" y2="26" stroke="#f1f5f9" stroke-width="1" />
    ''')

    # 1. UPSTREAM BOXES (Col 0)
    up_cnt = len(up)
    up_box_h = 36 if up_cnt > 2 else 44
    up_start_y = 38 if up_cnt > 2 else 50
    for idx, (title, sub) in enumerate(up):
        cur_y = up_start_y + idx * (up_box_h + 8)
        svg.append(f'''
          <rect x="15" y="{cur_y}" width="125" height="{up_box_h}" rx="5" fill="#f5f3ff" stroke="#7c3aed" stroke-width="1.2" />
          <text x="77" y="{cur_y + 16}" font-size="8" font-weight="700" fill="#6d28d9" text-anchor="middle">{title[:20]}</text>
          <text x="77" y="{cur_y + 28}" font-size="7" fill="#4c1d95" text-anchor="middle">{sub[:24]}</text>
        ''')
        # Arrow from upstream to Step 1
        svg.append(f'<path d="M 140 {cur_y + up_box_h/2} C 155 {cur_y + up_box_h/2}, 155 75, 175 75" fill="none" stroke="#7c3aed" stroke-width="1.2" stroke-dasharray="3,2" marker-end="url(#arr)" />')

    # 2. STEP 1 (Col 1, Top)
    s1_title, s1_sub = steps[0] if len(steps) > 0 else ('Intake & Draft', 'Create record')
    svg.append(f'''
      <rect x="175" y="50" width="115" height="50" rx="5" fill="#eff6ff" stroke="#2563eb" stroke-width="1.4" />
      <text x="232" y="70" font-size="8.5" font-weight="700" fill="#1e40af" text-anchor="middle">{s1_title[:18]}</text>
      <text x="232" y="85" font-size="7.5" fill="#3b82f6" text-anchor="middle">{s1_sub[:22]}</text>
    ''')

    # Arrow Step 1 to Decision or Step 2
    if len(steps) > 1:
        s2_title, s2_sub = steps[1]
        svg.append(f'<path d="M 232 100 L 232 125" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)" />')
        svg.append(f'''
          <rect x="175" y="125" width="115" height="50" rx="5" fill="#eff6ff" stroke="#2563eb" stroke-width="1.4" />
          <text x="232" y="145" font-size="8.5" font-weight="700" fill="#1e40af" text-anchor="middle">{s2_title[:18]}</text>
          <text x="232" y="160" font-size="7.5" fill="#3b82f6" text-anchor="middle">{s2_sub[:22]}</text>
        ''')
        svg.append(f'<path d="M 290 150 L 330 150" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)" />')
        dec_cy = 150
    else:
        svg.append(f'<path d="M 290 75 L 330 75" stroke="#475569" stroke-width="1.3" marker-end="url(#arr)" />')
        dec_cy = 75

    # 3. DECISION DIAMOND (Col 2)
    dec_cx = 385
    dec_text, dec_pass, dec_fail = dec
    # Diamond points: (dec_cx, dec_cy-35), (dec_cx+55, dec_cy), (dec_cx, dec_cy+35), (dec_cx-55, dec_cy)
    svg.append(f'''
      <polygon points="{dec_cx},{dec_cy-32} {dec_cx+55},{dec_cy} {dec_cx},{dec_cy+32} {dec_cx-55},{dec_cy}" fill="#fffbeb" stroke="#d97706" stroke-width="1.4" />
      <text x="{dec_cx}" y="{dec_cy-4}" font-size="7.5" font-weight="700" fill="#92400e" text-anchor="middle">{dec_text[:16]}</text>
      <text x="{dec_cx}" y="{dec_cy+9}" font-size="6.8" fill="#b45309" text-anchor="middle">Verification</text>
    ''')

    # Pass Arrow (to Col 3)
    svg.append(f'<path d="M {dec_cx+55} {dec_cy} L 475 {dec_cy}" stroke="#059669" stroke-width="1.3" marker-end="url(#arr-green)" />')
    svg.append(f'<text x="{dec_cx+68}" y="{dec_cy-5}" font-size="7" font-weight="700" fill="#059669">{dec_pass[:8]}</text>')

    # 4. STEP 3 / EXECUTION (Col 3)
    s3_title = steps[2][0] if len(steps) > 2 else 'Release & Commit'
    s3_sub = steps[2][1] if len(steps) > 2 else 'Post changes'
    svg.append(f'''
      <rect x="475" y="{dec_cy-25}" width="105" height="50" rx="5" fill="#eff6ff" stroke="#2563eb" stroke-width="1.4" />
      <text x="527" y="{dec_cy-5}" font-size="8.5" font-weight="700" fill="#1e40af" text-anchor="middle">{s3_title[:18]}</text>
      <text x="527" y="{dec_cy+10}" font-size="7.5" fill="#3b82f6" text-anchor="middle">{s3_sub[:20]}</text>
    ''')

    # 5. DOWNSTREAM BOXES (Col 4)
    down_cnt = len(down)
    down_box_h = 36 if down_cnt > 2 else 44
    down_start_y = 38 if down_cnt > 2 else 50
    for idx, (title, sub) in enumerate(down):
        cur_y = down_start_y + idx * (down_box_h + 8)
        svg.append(f'''
          <rect x="605" y="{cur_y}" width="105" height="{down_box_h}" rx="5" fill="#f0fdf4" stroke="#059669" stroke-width="1.2" />
          <text x="657" y="{cur_y + 16}" font-size="8" font-weight="700" fill="#065f46" text-anchor="middle">{title[:18]}</text>
          <text x="657" y="{cur_y + 28}" font-size="7" fill="#047857" text-anchor="middle">{sub[:22]}</text>
        ''')
        # Arrow from Step 3 to downstream
        svg.append(f'<path d="M 580 {dec_cy} C 595 {dec_cy}, 595 {cur_y + down_box_h/2}, 605 {cur_y + down_box_h/2}" fill="none" stroke="#059669" stroke-width="1.2" marker-end="url(#arr-green)" />')

    # 6. FAIL / EXCEPTION LOOP (Bottom)
    svg.append(f'''
      <path d="M {dec_cx} {dec_cy+32} L {dec_cx} 210 L 232 210 L 232 {175 if len(steps)>1 else 100}" fill="none" stroke="#dc2626" stroke-width="1.2" stroke-dasharray="3,2" marker-end="url(#arr-red)" />
      <text x="{dec_cx-10}" y="198" font-size="7" font-weight="700" fill="#dc2626" text-anchor="end">{dec_fail[:16]}</text>
      <text x="{dec_cx-80}" y="222" font-size="7" font-weight="600" fill="#991b1b" text-anchor="middle">Exception: {exc[:35]}</text>
    ''')

    svg.append('</svg>')
    return '\n'.join(svg)


def generate_global_architecture_svg():
    """
    Generates a full-width high-level visual supply chain map showing all 18 modules
    grouped into 5 enterprise layers.
    """
    w, h = 720, 380
    svg = []
    svg.append(f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">')
    svg.append('''
      <defs>
        <marker id="g-arr" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#3b82f6" />
        </marker>
        <marker id="g-arr-dark" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#475569" />
        </marker>
        <linearGradient id="bgGA" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ffffff" /><stop offset="100%" stop-color="#f8fafc" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="720" height="380" rx="8" fill="url(#bgGA)" stroke="#cbd5e1" stroke-width="1.2" />
    ''')

    # LAYER 1: GOVERNANCE & FOUNDATION (Top)
    svg.append('''
      <rect x="15" y="15" width="690" height="60" rx="6" fill="#f8fafc" stroke="#94a3b8" stroke-dasharray="4,2" />
      <text x="25" y="30" font-size="8" font-weight="800" fill="#475569" letter-spacing="0.05em">LAYER 1: ENTERPRISE FOUNDATION &amp; MASTER DATA GOVERNANCE</text>
      
      <rect x="25" y="36" width="125" height="32" rx="4" fill="#0f172a" />
      <text x="87" y="52" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M1: Identity &amp; RBAC</text>
      <text x="87" y="62" font-size="6.5" fill="#94a3b8" text-anchor="middle">Native Auth / Site Scope</text>

      <rect x="160" y="36" width="125" height="32" rx="4" fill="#1e293b" />
      <text x="222" y="52" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M2: Parties &amp; AVL</text>
      <text x="222" y="62" font-size="6.5" fill="#94a3b8" text-anchor="middle">Vendors, Customers, Transporters</text>

      <rect x="295" y="36" width="130" height="32" rx="4" fill="#1e293b" />
      <text x="360" y="52" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M3: Business Entities</text>
      <text x="360" y="62" font-size="6.5" fill="#94a3b8" text-anchor="middle">Legal Entities, PAN, GSTIN</text>

      <rect x="435" y="36" width="130" height="32" rx="4" fill="#1e293b" />
      <text x="500" y="52" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M4: Facilities &amp; WMS</text>
      <text x="500" y="62" font-size="6.5" fill="#94a3b8" text-anchor="middle">Factories, Warehouses, Bins</text>

      <rect x="575" y="36" width="120" height="32" rx="4" fill="#1e293b" />
      <text x="635" y="52" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M5: Products &amp; BOM</text>
      <text x="635" y="62" font-size="6.5" fill="#94a3b8" text-anchor="middle">Engineering Specs, Cost Rollup</text>
    ''')

    # LAYER 2: INBOUND SUPPLY CHAIN & MANUFACTURING (Middle Top)
    svg.append('''
      <rect x="15" y="90" width="690" height="75" rx="6" fill="#eff6ff" stroke="#93c5fd" />
      <text x="25" y="105" font-size="8" font-weight="800" fill="#1e40af" letter-spacing="0.05em">LAYER 2: PLAN-TO-PRODUCE &amp; PROCURE-TO-PAY (INBOUND VALUE STREAM)</text>

      <rect x="25" y="112" width="100" height="44" rx="4" fill="#2563eb" />
      <text x="75" y="130" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M6: MRP &amp; DRP</text>
      <text x="75" y="142" font-size="6.5" fill="#dbeafe" text-anchor="middle">Demand Netting</text>

      <path d="M 125 134 L 140 134" stroke="#2563eb" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="140" y="112" width="105" height="44" rx="4" fill="#2563eb" />
      <text x="192" y="130" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M7: Procurement</text>
      <text x="192" y="142" font-size="6.5" fill="#dbeafe" text-anchor="middle">PO, RFQ, Approvals</text>

      <path d="M 245 134 L 260 134" stroke="#2563eb" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="260" y="112" width="100" height="44" rx="4" fill="#2563eb" />
      <text x="310" y="130" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M8: Inbound Gate</text>
      <text x="310" y="142" font-size="6.5" fill="#dbeafe" text-anchor="middle">ASN &amp; Gate Entry</text>

      <path d="M 360 134 L 375 134" stroke="#2563eb" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="375" y="112" width="100" height="44" rx="4" fill="#2563eb" />
      <text x="425" y="130" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M9: GRN &amp; QC</text>
      <text x="425" y="142" font-size="6.5" fill="#dbeafe" text-anchor="middle">Inspection, QR Print</text>

      <path d="M 475 134 L 490 134" stroke="#2563eb" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="490" y="112" width="105" height="44" rx="4" fill="#1d4ed8" />
      <text x="542" y="130" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M10: Inventory</text>
      <text x="542" y="142" font-size="6.5" fill="#dbeafe" text-anchor="middle">Stock Ledger &amp; Bins</text>

      <path d="M 595 134 L 610 134" stroke="#2563eb" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="610" y="112" width="85" height="44" rx="4" fill="#1e40af" />
      <text x="652" y="130" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M11: Production</text>
      <text x="652" y="142" font-size="6.5" fill="#dbeafe" text-anchor="middle">Work Orders, IPQC</text>
    ''')

    # LAYER 3: OUTBOUND ORDER-TO-CASH & REVERSE LOGISTICS (Middle Bottom)
    svg.append('''
      <rect x="15" y="180" width="690" height="75" rx="6" fill="#f0fdf4" stroke="#86efac" />
      <text x="25" y="195" font-size="8" font-weight="800" fill="#166534" letter-spacing="0.05em">LAYER 3: ORDER-TO-CASH (O2C) &amp; REVERSE LOGISTICS (OUTBOUND VALUE STREAM)</text>

      <rect x="25" y="202" width="115" height="44" rx="4" fill="#15803d" />
      <text x="82" y="220" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M12: Sales Orders</text>
      <text x="82" y="232" font-size="6.5" fill="#dcfce7" text-anchor="middle">Intake, ATP, Credit Check</text>

      <path d="M 140 224 L 160 224" stroke="#15803d" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="160" y="202" width="120" height="44" rx="4" fill="#15803d" />
      <text x="220" y="220" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M13: Wave Picking</text>
      <text x="220" y="232" font-size="6.5" fill="#dcfce7" text-anchor="middle">WMS Mobile, Packing</text>

      <path d="M 280 224 L 300 224" stroke="#15803d" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="300" y="202" width="125" height="44" rx="4" fill="#15803d" />
      <text x="362" y="220" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M14: Outbound TMS</text>
      <text x="362" y="232" font-size="6.5" fill="#dcfce7" text-anchor="middle">Carrier RFQ, e-Way Bill</text>

      <path d="M 425 224 L 445 224" stroke="#15803d" stroke-width="1.5" marker-end="url(#g-arr)" />

      <rect x="445" y="202" width="115" height="44" rx="4" fill="#166534" />
      <text x="502" y="220" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">Customer Delivery</text>
      <text x="502" y="232" font-size="6.5" fill="#dcfce7" text-anchor="middle">POD Confirmation</text>

      <path d="M 560 224 L 585 224" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="3,2" marker-end="url(#g-arr-dark)" />

      <rect x="585" y="202" width="110" height="44" rx="4" fill="#dc2626" />
      <text x="640" y="220" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M15: Returns (RMA)</text>
      <text x="640" y="232" font-size="6.5" fill="#fee2e2" text-anchor="middle">Reverse QC, Restock/Scrap</text>
    ''')

    # LAYER 4: FINANCE & LANDED COST (Bottom Middle)
    svg.append('''
      <rect x="15" y="270" width="690" height="50" rx="6" fill="#fdf4ff" stroke="#f0abfc" />
      <text x="25" y="284" font-size="8" font-weight="800" fill="#86198f" letter-spacing="0.05em">LAYER 4: FINANCIAL ACCOUNTING, 3-WAY MATCHING &amp; COST CAPITALIZATION</text>

      <rect x="25" y="290" width="210" height="25" rx="3" fill="#a21caf" />
      <text x="130" y="306" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M16a: AP 3-Way Match (PO vs GRN vs Bill)</text>

      <rect x="250" y="290" width="210" height="25" rx="3" fill="#a21caf" />
      <text x="355" y="306" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M16b: AR Invoicing &amp; Tax Settlement</text>

      <rect x="475" y="290" width="220" height="25" rx="3" fill="#701a75" />
      <text x="585" y="306" font-size="7.5" font-weight="700" fill="#ffffff" text-anchor="middle">M17: Landed Cost &amp; Valuation Posting</text>
    ''')

    # LAYER 5: SUPPORT SERVICES & ANALYTICS (Bottom)
    svg.append('''
      <rect x="15" y="330" width="690" height="38" rx="6" fill="#f1f5f9" stroke="#94a3b8" />
      <text x="25" y="344" font-size="8" font-weight="800" fill="#334155" letter-spacing="0.05em">LAYER 5: PLATFORM ENGINES &amp; CONTROL TOWER</text>

      <rect x="25" y="348" width="155" height="16" rx="2" fill="#334155" />
      <text x="102" y="359" font-size="6.8" font-weight="700" fill="#ffffff" text-anchor="middle">Document Engine (Async PDF)</text>

      <rect x="195" y="348" width="155" height="16" rx="2" fill="#334155" />
      <text x="272" y="359" font-size="6.8" font-weight="700" fill="#ffffff" text-anchor="middle">Notification Transport (Email/SMS)</text>

      <rect x="365" y="348" width="155" height="16" rx="2" fill="#334155" />
      <text x="442" y="359" font-size="6.8" font-weight="700" fill="#ffffff" text-anchor="middle">Audit Trail (Immutable Ledger)</text>

      <rect x="535" y="348" width="160" height="16" rx="2" fill="#0f172a" />
      <text x="615" y="359" font-size="6.8" font-weight="700" fill="#ffffff" text-anchor="middle">SC Control Tower &amp; Analytics</text>
    ''')

    svg.append('</svg>')
    return '\n'.join(svg)


MODULES_CATALOG = [
    {
        "id": "m1_identity",
        "num": "01",
        "name": "Identity, Authentication & RBAC",
        "route": "/login, /profile, /users",
        "entities": "users, roles, user_roles, user_role_warehouses, user_role_factories, sessions",
        "roles": "System Admin, All Operational Users",
        "overview": "Governs enterprise authentication, multi-factor token issuance, native Argon2id credentials, session lifecycle, and strict site-level data scoping across multiple factories and warehouses.",
        "up_nodes": [
            ("Native Auth", "Argon2id Hash / MFA"),
            ("Direct Login", "Enterprise Session Token")
        ],
        "core_steps": [
            ("Auth & Token Verify", "Evaluate credentials"),
            ("Site Scope Resolve", "Factories & Warehouses"),
            ("Casbin RBAC Policy", "Module endpoint grant")
        ],
        "decision": ("Valid Session?", "Authorized", "401 / 403 Forbidden"),
        "down_nodes": [
            ("All App Modules", "Inject User Context"),
            ("Audit Trail", "Write Login Event")
        ],
        "exception_label": "Lock account after 5 failed attempts",
        "workflow_steps": [
            ("Authentication Handshake", "User provides email/password and optional MFA code. The backend verifies the password hash using Argon2id and validates credentials against active account policies."),
            ("MFA & Session Issuance", "If TOTP is active, pyotp validates the 6-digit passcode. A cryptographic session is minted in the `sessions` table with an expiration timestamp and stored in an HTTP-only secure cookie."),
            ("Site & Warehouse Scoping", "The user's assigned roles are loaded along with explicit warehouse (`user_role_warehouses`) and factory (`user_role_factories`) access bindings. If an operator is restricted to Warehouse WH-01, queries across inventory, GRN, and orders automatically inject tenancy filters."),
            ("Casbin Enforcement & Routing", "Casbin RBAC policy evaluates `(sub, obj, act)` on each API endpoint. If permitted, the request executes; otherwise, a 403 Forbidden response is returned and logged in `audit_log`.")
        ],
        "upstream_conn": [
            ("Native Identity Engine", "Argon2id credential store, multi-factor TOTP verification, and session manager."),
            ("Organization Admin", "Assigns user records to specific business units, factories, and operational roles.")
        ],
        "downstream_conn": [
            ("All Functional Domains", "Every API route depends on `get_current_user` dependency, propagating `user_id`, `role`, and `allowed_warehouse_ids`."),
            ("Audit Logging", "Every state transition records `performed_by_user_id` for SOX compliance.")
        ],
        "state_machine": "USER: PENDING_ACTIVATION -> ACTIVE -> SUSPENDED -> TERMINATED | SESSION: ACTIVE -> REVOKED / EXPIRED"
    },
    {
        "id": "m2_parties",
        "num": "02",
        "name": "Parties & AVL Governance",
        "route": "/parties, /party/:partyId, /avl-governance",
        "entities": "parties, party_types, party_addresses, party_bank_accounts, party_versions",
        "roles": "Procurement Manager, Sales Operations, Compliance Officer",
        "overview": "Master registry for all external commercial entities: Vendors, Customers, Transporters, and Job Workers. Enforces Approved Vendor List (AVL) compliance, KYC/Tax ID validation, and credit limit guardrails.",
        "up_nodes": [
            ("Procurement Team", "New Vendor Request"),
            ("Sales Team", "New Customer Onboard")
        ],
        "core_steps": [
            ("Tax ID Validation", "PAN, GSTIN, CIN check"),
            ("KYC & Bank Verification", "IFSC, IBAN & Contacts"),
            ("AVL Risk Scoring", "Quality & Compliance")
        ],
        "decision": ("Approved Vendor?", "Active Master", "Hold / Probation"),
        "down_nodes": [
            ("Procurement PO", "Vendor Selection"),
            ("Sales Orders", "Customer Credit Check"),
            ("Logistics TMS", "Transporter Carrier")
        ],
        "exception_label": "Blacklist on default / tax invalidity",
        "workflow_steps": [
            ("Party Intake & Categorization", "Commercial entity created with a formal legal name, trading name, and designated party type (VENDOR, CUSTOMER, TRANSPORTER, JOB_WORKER)."),
            ("Tax & Regulatory Validation", "System executes checksum and format validations on PAN (10 alphanumeric) and state GSTIN (15 characters). Cryptographic hashing ensures duplicate tax entities cannot be fraudulently registered."),
            ("Banking & Address Verification", "Multi-site billing and shipping addresses are recorded with postal codes and state codes. Bank accounts are verified for automated NEFT/RTGS AP settlement."),
            ("AVL Governance & Credit Scrutiny", "Procurement/Quality audits assign AVL status (`APPROVED`, `PROBATION`, `DISQUALIFIED`). For customers, a strict credit limit and payment terms (e.g. Net 30) are established. Only `APPROVED` vendors can be selected on Purchase Orders.")
        ],
        "upstream_conn": [
            ("Foundation Domain", "References `party_types` and currency codes."),
            ("Quality & Audit Domain", "Supplier scorecard audits feed directly into the AVL rating calculation.")
        ],
        "downstream_conn": [
            ("Procurement (PO)", "Mandatory foreign key `purchase_orders.vendor_id` -> `parties.id`. Inactive or blocked parties reject PO creation."),
            ("Sales (Orders)", "Foreign key `orders.customer_id` -> `parties.id`. Real-time query validates outstanding receivables against credit limit."),
            ("Logistics (TMS)", "Transporters (`party_type = TRANSPORTER`) are invited to freight RFQs and bound to carrier dispatch manifests."),
            ("Finance (AP/AR)", "Supplies bank coordinates for AP payouts and billing addresses for tax-compliant GST invoices.")
        ],
        "state_machine": "PARTY: DRAFT -> UNDER_REVIEW -> APPROVED -> PROBATION -> BLOCKED -> ARCHIVED"
    },
    {
        "id": "m3_business_entities",
        "num": "03",
        "name": "Business Entities & Seller Profiles",
        "route": "/po-invoice",
        "entities": "business_entities, factory_business_entities, business_entity_bank_accounts",
        "roles": "Finance Director, Legal Counsel, Corporate Controller",
        "overview": "Establishes corporate legal entities, state-level GSTIN registrations, registered headquarters, corporate seals, and primary banking coordinates for all buying and selling transactions.",
        "up_nodes": [
            ("Corporate Legal", "Entity Incorporation"),
            ("Tax Department", "State GSTIN Registrations")
        ],
        "core_steps": [
            ("Entity Profile Setup", "CIN, PAN, Legal Name"),
            ("Factory/Wh Linkage", "Physical site assignment"),
            ("Banking Configuration", "Primary disbursement accts")
        ],
        "decision": ("Valid GSTIN?", "Activate Entity", "Reject / Update Reg"),
        "down_nodes": [
            ("Purchase Orders", "Legal Buyer Entity"),
            ("AR Tax Invoicing", "Legal Seller Profile"),
            ("PDF Documents", "Branding & Bank Details")
        ],
        "exception_label": "Suspension on expired tax registration",
        "workflow_steps": [
            ("Entity Registration", "Corporate identity recorded with Corporate Identification Number (CIN), Permanent Account Number (PAN), and state-specific Goods and Services Tax Identification Numbers (GSTIN)."),
            ("Facility Association", "Operating factories and warehouses are mapped to corresponding legal business entities. This enforces correct intrastate vs interstate tax rules (CGST/SGST vs IGST) based on facility location."),
            ("Bank Disbursement Allocation", "Virtual and physical commercial bank accounts are linked to the business entity, designating primary clearing accounts for vendor electronic fund transfers."),
            ("Document Engine Branding", "Official digital signatures, corporate logos, registered office addresses, and default PO/Invoice legal disclaimers are assigned for automated PDF rendering.")
        ],
        "upstream_conn": [
            ("Foundation Domain", "Configures parent corporate identity and currency standards.")
        ],
        "downstream_conn": [
            ("Procurement (PO)", "Every Purchase Order carries `business_entity_id`, defining which internal corporate entity is contractually liable for payment."),
            ("Finance (Invoicing)", "AR invoices use the business entity's GSTIN and state code to compute state tax liability and print corporate bank details."),
            ("Logistics (e-Way Bill)", "Supplies the consignor/consignee tax registration numbers for statutory transport compliance.")
        ],
        "state_machine": "BUSINESS_ENTITY: DRAFT -> ACTIVE -> REVISED -> DEREGISTERED"
    },
    {
        "id": "m4_facilities_wms",
        "num": "04",
        "name": "Facilities, Factories & WMS Bins",
        "route": "/factory-warehouse, /wms-bins",
        "entities": "factories, warehouses, locations (bins, racks, aisles, zones)",
        "roles": "Plant Head, Warehouse Operations Manager, Logistics Engineer",
        "overview": "Models the physical industrial topology: manufacturing factories, centralized warehouses, regional distribution centers, and granular WMS bin locations with capacity and velocity rules.",
        "up_nodes": [
            ("Industrial Engineering", "Factory Layout Setup"),
            ("Supply Chain Strategy", "Warehouse Topology")
        ],
        "core_steps": [
            ("Facility Hierarchy", "Factory -> Warehouses"),
            ("WMS Topology Build", "Zone -> Aisle -> Rack -> Bin"),
            ("Velocity Profiling", "Fast/Slow moving rules")
        ],
        "decision": ("Bin Verified?", "Active Storage Node", "Remap Topology"),
        "down_nodes": [
            ("Warehouse GRN", "Putaway Inward Bins"),
            ("Production Staging", "Shop Floor WIP Bins"),
            ("Wave Picking", "Optimal Pick Routes")
        ],
        "exception_label": "Bin lock on damage or physical audit",
        "workflow_steps": [
            ("Factory Definition", "Manufacturing sites are established with geographical addresses, operating cost centers, labor rosters, and linked legal entities."),
            ("Warehouse Categorization", "Dedicated storage depots are created for specific functions: Raw Materials (RM), Work-in-Progress (WIP), Finished Goods (FG), and Quarantine / Scrap."),
            ("Multi-Tier WMS Hierarchy", "Each warehouse is subdivided into Zones (e.g. Ambient, Cold, High-Value), Aisles, Racks, Shelves, and individual Bins with volumetric and weight limits."),
            ("Velocity & Putaway Logic", "Fast-moving items are mapped to lower-tier, dock-adjacent bins to minimize forklift travel time during wave picking.")
        ],
        "upstream_conn": [
            ("Identity (RBAC)", "User site scoping filters bind warehouse workers to specific physical facilities."),
            ("Business Entities", "Every warehouse and factory must belong to a valid corporate legal entity.")
        ],
        "downstream_conn": [
            ("GRN Receiving", "Determines allowable receiving docks and default inbound inspection bins."),
            ("Inventory Balances", "`stock_balances` and `stock_ledger` records maintain quantities broken down by `warehouse_id` and `location_id` (bin)."),
            ("Production", "Defines the staging locations for raw material shop floor issues and WIP queues."),
            ("Picking & Shipping", "Wave picking generates shortest-path travel routes through aisles and racks.")
        ],
        "state_machine": "LOCATION: ACTIVE -> FULL -> LOCKED_FOR_AUDIT -> DAMAGED -> INACTIVE"
    },
    {
        "id": "m5_products_bom",
        "num": "05",
        "name": "Product Catalog & Engineering BOM",
        "route": "/products",
        "entities": "products, product_categories, boms, bom_versions, bom_components, bom_approvals",
        "roles": "R&D Engineer, Product Manager, Cost Accountant",
        "overview": "Defines sellable and component SKUs, engineering Bill of Materials (BOM) multi-level hierarchies, scrap allowances, version effectivity dates, and automated standard cost rollups.",
        "up_nodes": [
            ("Engineering / R&D", "CAD / PLM Item Design"),
            ("Costing Department", "Labor & Overhead Rates")
        ],
        "core_steps": [
            ("SKU Definition", "Category, UOM, Specs"),
            ("BOM Multi-Level Tree", "Parent-Child Component Tree"),
            ("Cost Rollup Calculation", "Material + Labor + OH")
        ],
        "decision": ("ECO Approved?", "Publish Active BOM", "Engineering Revision"),
        "down_nodes": [
            ("MRP Engine", "BOM Explosion Netting"),
            ("Production Runs", "Work Order Recipe"),
            ("Sales Catalog", "Product Price & ATP")
        ],
        "exception_label": "Cycle detected / Scrap rate excessive",
        "workflow_steps": [
            ("SKU Master Creation", "Item categorized as RAW_MATERIAL, SUB_ASSEMBLY, FINISHED_GOOD, or CONSUMABLE. System auto-generates unique SKU codes and barcodes with base and secondary UOM conversion ratios."),
            ("BOM Composition", "Engineers construct parent-child component trees specifying component part IDs, gross quantity per build unit, and planned scrap loss percentages."),
            ("Version Control & Effectivity", "BOMs are version-controlled (`v1.0`, `v2.0`). Engineering Change Orders (ECO) define effectivity start and end dates. Obsolete components are automatically blocked from future production."),
            ("Standard Cost Rollup Engine", "The system traverses the BOM hierarchy, aggregating active component purchase costs plus machine operation costs and direct labor rates to establish the standard manufacturing cost.")
        ],
        "upstream_conn": [
            ("Product Categories", "Inherits default HSN/SAC codes, tax rates, and inventory valuation methods (FIFO/Weighted Average).")
        ],
        "downstream_conn": [
            ("MRP Engine", "Explodes active BOMs to calculate gross-to-net raw material purchasing requirements."),
            ("Production Execution", "Supplies the definitive component recipe for Work Order material staging and component consumption."),
            ("Procurement", "Provides component specifications and authorized manufacturer part numbers."),
            ("Sales Catalog", "Exposes finished goods SKUs for customer quoting and order entry.")
        ],
        "state_machine": "BOM: DRAFT -> SUBMITTED -> PENDING_ENGINEERING_REVIEW -> APPROVED -> ACTIVE -> OBSOLETE"
    },
    {
        "id": "m6_planning_mrp_drp",
        "num": "06",
        "name": "Planning: Demand, MRP & DRP",
        "route": "/forecasting, /mrp, /drp, /capacity-planning",
        "entities": "mrp_runs, mrp_planned_orders, drp_transfers, sales_forecasts",
        "roles": "Master Scheduler, Supply Chain Planner, Inventory Controller",
        "overview": "Synthesizes sales forecasts, committed orders, existing inventory, and open purchase orders to run multi-echelon MRP explosions and DRP replenishment across all factory and distribution hubs.",
        "up_nodes": [
            ("Sales Orders", "Committed Demand"),
            ("Forecasting Engine", "Statistical Demand Model"),
            ("Current Stock", "On-Hand & Open POs")
        ],
        "core_steps": [
            ("Gross Demand Netting", "Sales + Forecast - Inventory"),
            ("Multi-Level Explosion", "Explode BOM Trees"),
            ("Lead-Time Offsetting", "Calculate Order Due Dates")
        ],
        "decision": ("Capacity Feasible?", "Release Planned Orders", "Re-profile Schedule"),
        "down_nodes": [
            ("Procurement (PR)", "Auto-generate Requisitions"),
            ("Production Orders", "Auto-generate Work Orders"),
            ("DRP Logistics", "Inter-warehouse Transfers")
        ],
        "exception_label": "Supplier lead time breach / Capacity bottle-neck",
        "workflow_steps": [
            ("Demand Ingestion & MPS", "Aggregates committed Sales Orders and statistical sales forecasts into a time-phased Master Production Schedule (MPS)."),
            ("Gross-to-Net Inventory Calculation", "Deducts currently available physical inventory, allocated stock, and scheduled in-transit PO receipts to derive net deficit for each finished product."),
            ("Multi-Level BOM Explosion", "Traverses product BOMs to explode component requirements, multiplying gross quantities by assembly batch size and applying scrap factors."),
            ("Lead Time Offsetting & Lot Sizing", "Applies vendor lead times and production cycle times backwards to determine release dates, applying Minimum Order Quantities (MOQ) and packaging multiples."),
            ("Planned Order Generation", "Emits automated Purchase Requisitions for raw materials and planned Work Orders for in-house manufacturing.")
        ],
        "upstream_conn": [
            ("Sales Orders", "Supplies hard unfulfilled sales lines."),
            ("Inventory Balances", "Queries current unreserved stock balances and safety stock thresholds."),
            ("Product BOM", "Provides component ratios and lead time attributes.")
        ],
        "downstream_conn": [
            ("Requisitions Domain", "Auto-creates records in `purchase_requisitions` for external supplier procurement."),
            ("Production Domain", "Creates proposed manufacturing runs in `production_runs` (Planned status)."),
            ("DRP Transfers", "Creates inter-warehouse transfer requests to rebalance regional inventory.")
        ],
        "state_machine": "MRP_RUN: SCHEDULED -> RUNNING -> COMPLETED -> ORDERS_GENERATED -> ARCHIVED"
    },
    {
        "id": "m7_procurement_po",
        "num": "07",
        "name": "Procurement, RFQ & Purchase Orders",
        "route": "/procurement, /blanket-po, /vendor-portal",
        "entities": "purchase_requisitions, rfqs, purchase_orders, po_lines, po_approvals, blanket_pos",
        "roles": "Buyer, Procurement Head, Finance Approver, External Vendor",
        "overview": "End-to-end purchasing workflow: converts requisitions to RFQs, manages supplier bidding, issues formal Purchase Orders (Standard or Blanket), enforces approval hierarchies, and manages revisions.",
        "up_nodes": [
            ("MRP Planning", "Auto-Requisitions"),
            ("Manual Requisition", "Departmental Purchase Request"),
            ("Parties Master", "Approved Vendor List")
        ],
        "core_steps": [
            ("RFQ & Quotation Bidding", "Compare Vendor Pricing"),
            ("PO Generation", "Lines, Rates, Taxes, Delivery"),
            ("Multi-Tier Approval", "Hierarchy Signature Limits")
        ],
        "decision": ("Approval Limits OK?", "PO Issued & Dispatched", "Rejected / Revise"),
        "down_nodes": [
            ("Vendor Portal / PDF", "Supplier Confirmation"),
            ("Warehouse Receiving", "Expected Inbound Lines"),
            ("Finance AP", "3-Way Match Baseline")
        ],
        "exception_label": "Over-budget / Disqualified vendor rejection",
        "workflow_steps": [
            ("Requisition & RFQ Bidding", "Approved Purchase Requisitions trigger RFQs distributed to AVL vendors. Vendor bids are ingested and compared for unit rate, payment terms, and delivery commitment."),
            ("Purchase Order Drafting", "Buyer selects awarded vendor and drafts PO specifying line items, HSN codes, tax structures, delivery schedules, freight terms, and recipient warehouse."),
            ("Multi-Tier Approval Hierarchy", "PO routes through dynamic approval gates based on total spend threshold (e.g. Level 1: Plant Buyer up to $5,000; Level 2: Supply Chain VP up to $50,000; Level 3: CFO beyond $50,000)."),
            ("PO Dispatch & Vendor Acknowledgment", "Approved PO triggers background PDF compilation and email transmission to vendor, while publishing to the Vendor Portal for acknowledgment and ASN filing."),
            ("Amendment & Short-Close", "Changes generate versioned PO amendments (`PO-001-R1`). Buyers can short-close remaining unfulfilled balances when partial delivery is deemed final.")
        ],
        "upstream_conn": [
            ("Requisitions / MRP", "Pulls line item demand, quantity, and target delivery dates."),
            ("Parties Master", "Validates vendor AVL status, currency, and tax IDs."),
            ("Business Entities", "Defines the legal buyer identity on the PO header.")
        ],
        "downstream_conn": [
            ("Inbound Logistics", "Transporters reference PO numbers on Gate Passes."),
            ("Warehouse GRN", "Inbound receiving matches vendor delivery against active PO line item tolerances."),
            ("Finance AP", "Locked PO prices and line quantities form the immutable baseline for 3-Way Matching."),
            ("Supplier Scorecard", "PO promised dates benchmark supplier On-Time In-Full (OTIF) ratings.")
        ],
        "state_machine": "PO: DRAFT -> PENDING_APPROVAL -> APPROVED -> ISSUED -> PARTIALLY_RECEIVED -> RECEIVED -> BILLED -> CLOSED / SHORT_CLOSED"
    },
    {
        "id": "m8_logistics_inbound",
        "num": "08",
        "name": "Inbound Logistics & Gate Entry",
        "route": "/logistics, /freight-tms",
        "entities": "transport_requests, gate_entries, dispatches",
        "roles": "Security Gate Officer, Inbound Logistics Coordinator, Weighbridge Operator",
        "overview": "Tracks inbound transport vehicles from vendor dispatch, processes Advance Shipping Notices (ASN), verifies driver credentials and Delivery Challans at the factory gate, and prints Gate Entry passes.",
        "up_nodes": [
            ("Vendor Portal", "Advance Shipping Notice (ASN)"),
            ("Purchase Orders", "Delivery Schedule & Tolerances")
        ],
        "core_steps": [
            ("Gate Check & Weighbridge", "Vehicle, Driver, Gross Weight"),
            ("Challan Verification", "Match PO & Delivery Challan"),
            ("Gate Entry Pass Issue", "Generate INW-Pass")
        ],
        "decision": ("PO & Challan Valid?", "Dock Allocation", "Reject Vehicle at Gate"),
        "down_nodes": [
            ("Warehouse Receiving", "Dock Unload & GRN Draft"),
            ("Supplier Scorecard", "Record Gate Arrival Time")
        ],
        "exception_label": "Seal tamper / Vehicle mismatch turnaround",
        "workflow_steps": [
            ("ASN & Inbound Alert", "Vendor logs planned shipment in portal with transporter details, truck registration, LR/e-Way bill number, and estimated arrival date."),
            ("Physical Gate Arrival & Inspection", "Truck arrives at factory perimeter. Security inspects container seals, driver documentation, and matches physical Delivery Challan against open POs in the system."),
            ("Weighbridge Gross Weighing", "Truck drives onto automated weighbridge; gross vehicle weight is logged directly into the system to prevent bulk material theft or shorting."),
            ("Gate Entry Number Creation", "System generates a unique Gate Inward Pass (`INW-YYYY-XXXXX`), assigns a specific warehouse unloading dock, and releases the truck into the yard.")
        ],
        "upstream_conn": [
            ("Procurement (PO)", "Validates that active, approved PO lines exist for the incoming goods."),
            ("Transporter Master", "Validates carrier identity and vehicle compliance records.")
        ],
        "downstream_conn": [
            ("Warehouse GRN", "Gate Entry Pass is mandatory foreign key to initialize a Goods Receipt Note."),
            ("Logistics Control", "Tracks turnaround demurrage time from gate entry to final dock exit.")
        ],
        "state_machine": "GATE_ENTRY: VEHICLE_ARRIVED -> INSPECTION_PASS -> DOCK_ASSIGNED -> UNLOADING -> GATE_EXIT"
    },
    {
        "id": "m9_grn_qc",
        "num": "09",
        "name": "GRN, Inbound QC & QR Labeling",
        "route": "/warehouse, /warehouse-qc/:grnId",
        "entities": "grns, grn_lines, inventory_items, rejection_codes, sticker_sizes",
        "roles": "Receiving Clerk, QC Inspector, Inventory Stockman",
        "overview": "Manages physical material unloading, PO line quantity matching with over-receipt tolerances, rigorous QC sampling inspection, QR/Barcode sticker generation, and putaway execution.",
        "up_nodes": [
            ("Inbound Gate Entry", "Unloaded Vehicle Manifest"),
            ("Purchase Orders", "PO Line Quantities & Pricing")
        ],
        "core_steps": [
            ("Draft GRN Intake", "Count physical boxes/units"),
            ("QC Sampling & Testing", "Inspect against item specs"),
            ("Disposition & QR Print", "Accept, Reject, Print QR Labels")
        ],
        "decision": ("QC Passed?", "Post to Inventory", "Quarantine / Return to Vendor"),
        "down_nodes": [
            ("Inventory Balances", "Increment Stock Ledger"),
            ("Finance AP", "Approved Baseline for 3-Way"),
            ("Supplier Scorecard", "PPM Defect Rate Record")
        ],
        "exception_label": "Rejection note & Return-to-Vendor challan",
        "workflow_steps": [
            ("Unloading & PO Matching", "Receiving team tallies physical packages against PO lines. System enforces over-receipt tolerance limits (e.g. max +5% allowed); excess quantities are blocked."),
            ("Draft GRN Creation", "Draft GRN records received quantity, vendor batch numbers, and manufacturing/expiry dates. Goods move to QC Inspection staging location."),
            ("Quality Control (QC) Inspection", "QC Inspector executes sampling protocol. Quality parameters are tested (dimensions, purity, electrical specs). Quantities are partitioned into `accepted_qty`, `rejected_qty`, and `quarantine_qty`."),
            ("QR/Barcode Label Generation", "Accepted units trigger automated generation of serialized QR sticker sheets (thermal roll 4x2, 2x1, or A4 24-up) containing SKU, GRN ID, batch ID, and tracking hash."),
            ("Putaway & Stock Ledger Posting", "Stockman scans QR labels and deposits pallets into assigned WMS warehouse bins. System atomically posts transactions to `stock_ledger` and updates PO received totals.")
        ],
        "upstream_conn": [
            ("Purchase Orders", "Links `grn.po_id` -> `purchase_orders.id` and updates line received quantities."),
            ("Gate Entry", "Links inward vehicle pass for complete supply chain auditability.")
        ],
        "downstream_conn": [
            ("Inventory Ledger", "Creates active records in `inventory_items` and increments `stock_balances`."),
            ("Finance AP 3-Way Match", "The `accepted_qty` on GRN lines defines the maximum payable quantity for vendor invoice clearance."),
            ("Supplier Scorecards", "Rejection counts instantly degrade the vendor's quality scorecard rating.")
        ],
        "state_machine": "GRN: DRAFT -> PENDING_QC -> QC_IN_PROGRESS -> APPROVED -> COMPLETED / REJECTED"
    },
    {
        "id": "m10_inventory_control",
        "num": "10",
        "name": "Inventory Control & Stock Ledger",
        "route": "/inventory, /inventory-item/:itemId, /cycle-counts",
        "entities": "stock_balances, stock_ledger, inventory_items, transfers, cycle_counts",
        "roles": "Warehouse Manager, Inventory Controller, Internal Auditor",
        "overview": "Heart of the operational system: double-entry stock ledger, real-time bin balances, lot/serial traceability, inter-warehouse transfers, blind cycle counting, and scrap adjustments.",
        "up_nodes": [
            ("GRN Receiving", "Accepted Inbound Stock"),
            ("Production Yield", "Finished Goods Inward"),
            ("Sales Returns", "RMA Restocked Units")
        ],
        "core_steps": [
            ("Real-Time Ledger Entry", "Double-entry debit/credit"),
            ("Bin Location Tracking", "Specific rack/shelf balances"),
            ("Perpetual Cycle Count", "Blind physical audit scan")
        ],
        "decision": ("Stock Reconciled?", "Confirmed Stock Balance", "Post Variance Adjustment"),
        "down_nodes": [
            ("Production Staging", "Component Allocation"),
            ("Sales Fulfillment", "Hard Stock Reservation"),
            ("Finance Ledger", "Balance Sheet Asset Valuation")
        ],
        "exception_label": "Disposal / Write-off authorization",
        "workflow_steps": [
            ("Double-Entry Stock Ledger", "Every material movement records an immutable row in `stock_ledger` with `quantity`, `uom`, `warehouse_id`, `location_id`, `valuation_rate`, and reference document."),
            ("Real-Time Stock Balances", "Queries return instant visibility into Total On-Hand, Allocated (Reserved for Production/Orders), In-Transit, and Net Available stock per SKU."),
            ("Bin Transfers & Rebalancing", "Warehouse staff scan source bin and destination bin to execute internal relocations without affecting overall facility balances."),
            ("Perpetual & Blind Cycle Counts", "Auditors initiate blind count batches where staff scan items without visibility to system expected quantities. Variances trigger supervisor investigation."),
            ("Inventory Adjustments & Disposals", "Authorized variances post debit/credit adjustments to the stock ledger with documented reason codes (damages, shrinkage, obsolescence).")
        ],
        "upstream_conn": [
            ("Warehouse GRN", "Inward stock receipts."),
            ("Production Completion", "Finished good and sub-assembly receipts."),
            ("Customer Returns (RMA)", "Re-induction of restocked return goods.")
        ],
        "downstream_conn": [
            ("Production Runs", "Reserves components for active work orders; issues components to shop floor."),
            ("Sales Wave Picking", "Locks inventory allocations and fulfills outbound sales orders."),
            ("Finance General Ledger", "Feeds inventory asset valuations into corporate Balance Sheet accounts.")
        ],
        "state_machine": "ITEM: IN_STOCK -> ALLOCATED -> PICKED -> SHIPPED | DISPOSED | UNDER_COUNT"
    },
    {
        "id": "m11_production_execution",
        "num": "11",
        "name": "Production Execution & IPQC",
        "route": "/production, /production/new, /production/:runId, /quality-ipqc, /subcontracting",
        "entities": "production_runs, production_consumptions, production_run_stages, finished_good_allocations, subcontracting_orders",
        "roles": "Production Supervisor, Shop Floor Operator, IPQC Inspector",
        "overview": "Transforms raw materials into finished assemblies: Work Order release, component staging & consumption, multi-stage routing, in-process quality gates, scrap tracking, and finished goods allocation.",
        "up_nodes": [
            ("MRP Planning", "Planned Production Run"),
            ("Sales Orders", "Make-to-Order Request"),
            ("Product BOM", "Assembly Recipe & Routing")
        ],
        "core_steps": [
            ("Component Allocation", "Reserve raw inventory"),
            ("Shop Floor Issue", "Transfer stock to WIP bins"),
            ("Stage Routing & IPQC", "Inspection at each machine station")
        ],
        "decision": ("Stage IPQC Passed?", "Complete & Yield FG", "Rework / Scrap Line Item"),
        "down_nodes": [
            ("Inventory Ledger", "Receive Finished Goods"),
            ("Sales Orders", "FG Allocation Binding"),
            ("Finance Costing", "Material & Labor Variances")
        ],
        "exception_label": "Excess scrap / Engineering halt",
        "workflow_steps": [
            ("Work Order Release & Allocation", "Production Order created for target finished SKU and batch quantity. System validates component availability against BOM and places hard reservation locks on raw materials."),
            ("Shop Floor Staging & Issue", "Materials transferred from main storage to shop floor WIP staging bins. System generates Material Transfer Slips with batch serialization."),
            ("Multi-Stage Execution & Routing", "Order progresses through sequential work center stages (e.g. SMT Assembly -> Soldering -> Enclosure Assembly -> Burn-in Testing)."),
            ("In-Process Quality Control (IPQC)", "At defined gate stages, IPQC inspectors perform testing. The order cannot advance to the next work center until the IPQC inspection report is digitally signed."),
            ("Subcontracting (Job Work)", "If a stage requires external processing (e.g. powder coating), a Subcontracting Delivery Challan is issued, tracking material at vendor premises until inward return."),
            ("Yield Declaration & FG Allocation", "Final completion records accepted finished goods yield and scrap loss. Finished goods are immediately allocated to awaiting customer Sales Orders or posted to stock.")
        ],
        "upstream_conn": [
            ("BOM Domain", "Inherits multi-level component requirements, standard scrap %, and routing stages."),
            ("Inventory Domain", "Consumes raw material stock batches."),
            ("Sales Orders", "Make-to-Order production runs are directly tagged with `order_id`.")
        ],
        "downstream_conn": [
            ("Inventory Balances", "Deducts raw materials from stock; adds newly minted finished good SKUs to FG warehouse."),
            ("Finished Good Allocations", "Directly binds completed serials to waiting sales order lines."),
            ("Finance Costing", "Computes actual manufacturing cost (actual component usage + labor/overhead absorption) vs standard cost.")
        ],
        "state_machine": "PRODUCTION_RUN: DRAFT -> PLANNED -> RELEASED -> IN_PROGRESS -> IPQC_HOLD -> COMPLETED -> CLOSED"
    },
    {
        "id": "m12_sales_orders",
        "num": "12",
        "name": "Sales Management & Order Booking",
        "route": "/orders, /customer-portal",
        "entities": "orders, order_lines, quotations, reservations",
        "roles": "Sales Representative, Commercial Manager, Customer Service",
        "overview": "Governs commercial revenue intake: customer quotations, sales order entry, automated credit limit checks, Available-to-Promise (ATP) stock netting, soft reservations, and fulfillment release.",
        "up_nodes": [
            ("Customer Request", "RFQ / Purchase Order"),
            ("Parties Master", "Customer Credit Profile"),
            ("Product Catalog", "SKU Pricing & Catalogs")
        ],
        "core_steps": [
            ("Quotation to SO", "Convert quote or intake direct"),
            ("Credit & Margin Check", "Validate limit & profitability"),
            ("ATP & Stock Reservation", "Reserve available stock / MTO")
        ],
        "decision": ("Credit & Stock OK?", "Approve & Release SO", "Commercial Hold / Advance Reqd"),
        "down_nodes": [
            ("Wave Picking", "Trigger Warehouse Fulfillment"),
            ("Production MTO", "Trigger Work Order Build"),
            ("Finance AR", "Billing Schedule Setup")
        ],
        "exception_label": "Over credit limit / Payment default hold",
        "workflow_steps": [
            ("Inquiry & Quotation", "Sales rep prepares quotation specifying line items, pricing tiers, discounts, delivery timelines, and payment terms."),
            ("Sales Order Intake", "Upon customer confirmation, quote converts to a binding Sales Order (`SO-YYYY-XXXXX`). Line items specify delivery addresses and requested dispatch dates."),
            ("Automated Credit & Financial Checks", "System queries the customer's total unpaid AR balance + unbilled open orders. If total exposure breaches the approved credit limit, the SO is placed on `CREDIT_HOLD`."),
            ("Available-to-Promise (ATP) & Soft Reservation", "System nets requested quantities against unreserved finished inventory. If stock exists, a soft reservation is created; if stock is deficient, a Make-to-Order production demand is triggered."),
            ("Order Release to Fulfillment", "Once approved, commercial lock is lifted and the order is published to the warehouse queue for wave picking.")
        ],
        "upstream_conn": [
            ("Parties Master", "Validates customer master, credit ceiling, tax exemption certificates, and addresses."),
            ("Products Master", "Pulls sellable SKUs, pricing matrices, and tax rates.")
        ],
        "downstream_conn": [
            ("Warehouse Wave Picking", "Approved order lines appear on picking consoles for fulfillment."),
            ("Production Planning", "Unstocked lines trigger make-to-order manufacturing runs."),
            ("Finance AR", "Forms the contractual basis for generating tax invoices upon dispatch.")
        ],
        "state_machine": "ORDER: DRAFT -> PENDING_CREDIT_CHECK -> CREDIT_HOLD -> APPROVED -> ALLOCATED -> PICKING -> SHIPPED -> INVOICED -> CLOSED"
    },
    {
        "id": "m13_warehouse_picking",
        "num": "13",
        "name": "Warehouse Wave Picking & Packing",
        "route": "/wave-picking, /wms-mobile",
        "entities": "wave_picks, pick_tasks, packing_slips, cartons",
        "roles": "Pick Wave Planner, Mobile Scanner Picker, Packing Station Lead",
        "overview": "Optimizes order fulfillment: groups approved sales orders into intelligent pick waves, dispatches bin-directed tasks to mobile barcode scanners, verifies goods at packing tables, and generates carton labels.",
        "up_nodes": [
            ("Approved Sales Orders", "Unfulfilled Order Lines"),
            ("WMS Bins Master", "Rack & Shelf Coordinates")
        ],
        "core_steps": [
            ("Wave Generation", "Group by route, carrier, or SLA"),
            ("Mobile Bin Picking", "Shortest path scanner pick"),
            ("Packing & Weight Verify", "Scan verification & packing slip")
        ],
        "decision": ("Pick Audit 100%?", "Cartonize & Stage", "Pick Discrepancy Flag"),
        "down_nodes": [
            ("Inventory Balances", "Deduct Physical Stock"),
            ("Outbound TMS", "Packed Carton Dimensions"),
            ("Customer Notification", "Packing Confirmation")
        ],
        "exception_label": "Missing bin stock / Damaged unit swap",
        "workflow_steps": [
            ("Pick Wave Optimization", "Supervisor consolidates open sales orders into a wave based on shipping carrier, delivery zone, or high-priority SLA."),
            ("Bin-Directed Mobile Picking", "Warehouse pickers receive optimized traveling sequences on mobile handheld scanners. Staff must scan the bin barcode and SKU barcode to eliminate pick errors."),
            ("Packing Station Intake & Audit", "Picked items arrive in totes at packing stations. Pack lead scans each item to verify 100% quantity and quality conformity against order lines."),
            ("Cartonization & Barcode Labeling", "Items are packed into shipping cartons. System records carton dimensions, net weight, and tare weight, and prints carton shipping barcodes (`CARTON-001/003`)."),
            ("Packing Slip & Staging", "System generates Packing Slip, seals cartons, and marks packages as `STAGED_AT_DOCK` for transporter pickup.")
        ],
        "upstream_conn": [
            ("Sales Orders", "Consumes approved order line item quantities."),
            ("WMS Facilities", "Uses aisle and bin coordinates to compute shortest picking paths.")
        ],
        "downstream_conn": [
            ("Inventory Stock Ledger", "Converts soft reservations into definitive inventory issue deductions."),
            ("Outbound Logistics", "Transfers carton count, volumetric dimensions, and gross shipping weight to the freight shipping engine.")
        ],
        "state_machine": "WAVE_PICK: DRAFT -> RELEASED -> IN_PROGRESS -> PICKED -> PACKED -> STAGED"
    },
    {
        "id": "m14_logistics_outbound",
        "num": "14",
        "name": "Outbound Logistics & Freight TMS",
        "route": "/logistics, /freight-tms, /statutory-logistics, /shipping-engine",
        "entities": "dispatches, transport_requests, carrier_rfqs, carrier_bids, delivery_challans",
        "roles": "Logistics Dispatcher, Transporter Carrier, Transport Accounts Clerk",
        "overview": "Executes outward transport: runs transporter RFQ bidding, validates carrier vehicle placement, generates statutory e-Way Bills and e-Invoices, prints Delivery Challans, and tracks milestone PODs.",
        "up_nodes": [
            ("Staged Cartons", "Packed Sales Shipments"),
            ("Transporter Master", "Registered Freight Carriers")
        ],
        "core_steps": [
            ("Carrier RFQ & Booking", "Transporter bidding & rate lock"),
            ("Statutory Compliance", "Generate e-Way Bill & IRN"),
            ("Dock Loading & Gate Out", "Loading sheet & delivery challan")
        ],
        "decision": ("e-Way Bill Valid?", "Dispatch Shipment", "Hold Dock Loading"),
        "down_nodes": [
            ("Customer Tracking", "In-Transit Live Telemetry"),
            ("Finance AR", "Trigger Tax Invoice"),
            ("Logistics AP", "Freight Bill Settlement")
        ],
        "exception_label": "Vehicle breakdown / In-transit exception",
        "workflow_steps": [
            ("Freight RFQ & Transporter Bidding", "Dispatch request triggers spot RFQ or assigns primary contract transporter based on freight lane rate matrices."),
            ("Vehicle Placement & Dock Loading", "Assigned truck arrives at loading dock. Driver details and vehicle registration number are verified against booking records. Cartons loaded according to weight distribution."),
            ("Statutory Compliance Generation", "System connects to government GST/NIC portal API to auto-generate electronic e-Way Bill and electronic Tax Invoice (IRN QR code)."),
            ("Delivery Challan & Gate Outward Pass", "Official Delivery Challan and Security Gate Outward Pass are issued. Truck exits perimeter; shipment status updates to `IN_TRANSIT`."),
            ("Milestone Tracking & POD Upload", "GPS milestones update shipment progress. Upon delivery, driver obtains signed physical or digital Proof of Delivery (POD) uploaded to the system.")
        ],
        "upstream_conn": [
            ("Warehouse Packing", "Receives total carton count, pallet volume, and shipping weight."),
            ("Business Entities", "Pulls consignor legal entity details and state GST registration.")
        ],
        "downstream_conn": [
            ("Sales Orders", "Transitions sales order status to `SHIPPED` and `DELIVERED`."),
            ("Finance AR", "Confirmed dispatch triggers final AR Tax Invoice generation."),
            ("Finance AP", "Transporter POD serves as mandatory verification to clear freight bills for payment.")
        ],
        "state_machine": "DISPATCH: READY_FOR_DISPATCH -> VEHICLE_ASSIGNED -> LOADED -> GATE_OUT -> IN_TRANSIT -> DELIVERED -> SETTLED"
    },
    {
        "id": "m15_returns_rma",
        "num": "15",
        "name": "Customer Returns & Reverse Logistics",
        "route": "/returns",
        "entities": "returns, return_lines, return_inspections, credit_notes",
        "roles": "Customer Support, Reverse QC Engineer, Inventory Restock Clerk",
        "overview": "Manages customer Return Material Authorizations (RMA), reverse logistics intake, technical diagnostics, dispositioning (restock, rework, scrap), and financial credit note or replacement order issuance.",
        "up_nodes": [
            ("Customer Portal", "Return / Warranty Claim"),
            ("Historical Sales Orders", "Original Invoice Verification")
        ],
        "core_steps": [
            ("RMA Intake & Gate Inward", "Verify original serial number"),
            ("Reverse QC Diagnostics", "Defect root-cause inspection"),
            ("Disposition Decision", "Restock, Rework, or Scrap")
        ],
        "decision": ("Under Warranty?", "Approve Resolution", "Reject Claim / Return to Cust"),
        "down_nodes": [
            ("Inventory Balances", "Restock / Scrap Posting"),
            ("Finance AR", "Issue Credit Note"),
            ("Quality Engineering", "CAPA Defect Investigation")
        ],
        "exception_label": "Customer damage / Fraudulent return decline",
        "workflow_steps": [
            ("RMA Initiation & Validation", "Customer submits return request. System cross-references original Sales Order and invoice to ensure warranty validity and return window eligibility."),
            ("Reverse Pickup & Gate Inward", "Reverse logistics pickup scheduled. Upon arrival at factory, security logs Return Gate Pass and delivers goods to Quarantine Returns staging."),
            ("Technical Diagnostics & Reverse QC", "Quality engineers test returned unit, verifying serial numbers and classifying root cause (transit damage, manufacturing defect, user error)."),
            ("Dispositioning Execution", "Accepted units are dispositioned: (1) Good units sanitized and returned to active stock; (2) Fixable units routed to rework production; (3) Non-salvageable units scrapped."),
            ("Financial & Commercial Resolution", "Customer is resolved via: (A) Automated Credit Note issued in Finance AR against original invoice; or (B) Zero-dollar replacement Sales Order dispatched.")
        ],
        "upstream_conn": [
            ("Sales Orders", "Validates original purchase price, serial number validity, and customer identity.")
        ],
        "downstream_conn": [
            ("Inventory Ledger", "Increments warehouse stock if restocked, or logs scrap disposal."),
            ("Finance AR", "Triggers formal GST-compliant Credit Note reducing customer receivables."),
            ("Quality Management", "Feeds defect analytics into Corrective and Preventive Action (CAPA) dashboards.")
        ],
        "state_machine": "RMA: REQUESTED -> RMA_APPROVED -> RECEIVED -> QC_INSPECTION -> RESTOCKED / SCRAPPED -> SETTLED"
    },
    {
        "id": "m16_finance_settlement",
        "num": "16",
        "name": "Finance, Invoicing & 3-Way Match",
        "route": "/finance",
        "entities": "invoices, invoice_lines, ap_invoices, ap_invoice_lines, payments, accounting_periods",
        "roles": "Accounts Payable Officer, Accounts Receivable Lead, Chief Financial Officer",
        "overview": "Financial nucleus of the ERP: automated 3-Way Matching (PO vs GRN vs Vendor Bill), AP payment vouchers, AR tax invoice issuance, tax withholding (TDS/GST), and accounting period governance.",
        "up_nodes": [
            ("Procurement PO", "Contracted Rates & Terms"),
            ("Warehouse GRN", "Accepted Physical Quantities"),
            ("Outbound Dispatch", "Shipped Sales Orders")
        ],
        "core_steps": [
            ("Automated 3-Way Match", "Compare PO, GRN, & Vendor Bill"),
            ("Tax & Withholding Calc", "Compute GST & TDS deductions"),
            ("Payment Disbursement", "Bank batch payout voucher")
        ],
        "decision": ("Match Within Tol?", "Approve for Payment", "Price/Qty Dispute Hold"),
        "down_nodes": [
            ("Vendor / Cust Ledger", "Post AP/AR Balance"),
            ("General Ledger", "Financial Journal Posting"),
            ("Bank Integration", "NEFT / RTGS Payout Batch")
        ],
        "exception_label": "Discrepancy notice to vendor",
        "workflow_steps": [
            ("AP Vendor Bill Ingestion", "Vendor tax invoice submitted via portal or accounts payable desk. System parses line items, tax numbers, and invoice totals."),
            ("Automated 3-Way Matching Engine", "System executes rigorous 3-way check: (1) PO Unit Price vs Invoice Unit Price; (2) GRN Accepted Quantity vs Invoiced Quantity; (3) PO Payment Terms. Tolerances (e.g. max 1% price variance) are strictly enforced."),
            ("Invoice Clearance & Tax Booking", "Matched invoices auto-approve. System computes statutory withholdings (TDS under Income Tax Act, GST TDS) and books debit to Expense/Inventory Asset and credit to Accounts Payable."),
            ("AR Tax Invoicing", "Outbound dispatches auto-generate AR Tax Invoices with sequential fiscal year numbering, posting debit to Customer Receivables and credit to Sales Revenue and GST Output Liability."),
            ("Payment Vouchers & Reconciliation", "Treasury runs payment batch generation, exporting bank clearing files. Incoming customer receipts are reconciled against open AR invoices.")
        ],
        "upstream_conn": [
            ("Procurement", "Pulls contracted rates, approved PO lines, and payment terms."),
            ("Warehouse GRN", "Pulls verified accepted goods receipt lines."),
            ("Sales Dispatch", "Pulls confirmed shipped order lines for AR billing.")
        ],
        "downstream_conn": [
            ("Parties Ledger", "Updates real-time outstanding vendor payables and customer credit utilization balances."),
            ("Accounting Periods", "Restricts transaction posting to open accounting fiscal periods.")
        ],
        "state_machine": "INVOICE: DRAFT -> PENDING_MATCH -> MATCH_FAILED_HOLD -> APPROVED -> SCHEDULED_FOR_PAYMENT -> PAID"
    },
    {
        "id": "m17_landed_cost",
        "num": "17",
        "name": "Landed Cost & Inventory Valuation",
        "route": "/landed-cost",
        "entities": "landed_costs, landed_cost_items, landed_cost_allocations, stock_ledger",
        "roles": "Cost Accountant, Import/Export Manager, Financial Analyst",
        "overview": "Capitalizes indirect procurement expenses (customs tariffs, maritime freight, port handling, transit insurance) across physical inventory batches to reflect true landed cost in balance sheet valuation.",
        "up_nodes": [
            ("Warehouse GRN", "Inbound Stock Batches"),
            ("Logistics / Customs AP", "Freight & Duty Invoices")
        ],
        "core_steps": [
            ("Landed Cost Voucher", "Aggregate expense bills"),
            ("Apportionment Engine", "Prorate by Value, Qty, or Weight"),
            ("Batch Valuation Re-rate", "Adjust unit cost in stock ledger")
        ],
        "decision": ("Stock Available?", "Capitalize to Stock Asset", "Post COGS Variance Exp"),
        "down_nodes": [
            ("Stock Ledger Valuation", "Update Historical Cost"),
            ("Finance Balance Sheet", "Debit Asset, Credit AP Freight"),
            ("Profitability Analytics", "True Product Gross Margin")
        ],
        "exception_label": "Over-allocation / Currency revaluation audit",
        "workflow_steps": [
            ("Expense Ingestion", "Third-party freight forwarder bills, customs clearance duties, and insurance invoices are booked and linked to an Inbound Shipment file."),
            ("Landed Cost Voucher Creation", "Cost accountant initiates Landed Cost Voucher (`LCV-YYYY-XXXXX`), attaching relevant inbound GRN batches."),
            ("Apportionment Calculation", "System distributes total expense across received items based on chosen allocation rule: By Value (ad valorem), By Quantity, By Net Weight, or By Cubic Volume."),
            ("Stock Ledger Revaluation Posting", "System calculates cost delta per unit. If inventory is still in warehouse, the unit valuation rate in `stock_ledger` is capitalized upward. If already sold, variance posts directly to Cost of Goods Sold (COGS).")
        ],
        "upstream_conn": [
            ("Warehouse GRN", "Supplies received item line quantities, initial PO purchase rates, and batch IDs."),
            ("Logistics / Freight Invoices", "Supplies payable expense amounts from third-party logistics service providers.")
        ],
        "downstream_conn": [
            ("Inventory Balances", "Increases balance sheet valuation of raw materials and purchased components."),
            ("Product Costing", "Feeds actual landed cost baselines back into BOM engineering cost comparison.")
        ],
        "state_machine": "LANDED_COST: DRAFT -> EXPENSES_LINKED -> ALLOCATED -> POSTED_TO_LEDGER"
    },
    {
        "id": "m18_platform_services",
        "num": "18",
        "name": "Platform Engines & Control Tower",
        "route": "/documents, /notifications, /audit, /sc-control-tower",
        "entities": "documents, notifications, notification_templates, audit_logs, delivery_logs",
        "roles": "System Administrator, Executive Operations, Compliance Auditor",
        "overview": "Cross-cutting foundation: asynchronous headless PDF rendering, multi-channel transactional alerts (Email, SMS, Webhook), immutable regulatory audit logging, and the executive Supply Chain Control Tower.",
        "up_nodes": [
            ("Any ERP Module", "Transactional Business Event"),
            ("Executive Console", "KPI Telemetry Request")
        ],
        "core_steps": [
            ("Document Engine", "Async WeasyPrint PDF render"),
            ("Notification Transport", "Jinja2 template & SMTP dispatch"),
            ("Audit Trail Capture", "Old vs New state JSON diff")
        ],
        "decision": ("Delivery Succeeded?", "Complete & Archive", "Exponential Backoff Retry"),
        "down_nodes": [
            ("Cloud Object Storage", "Immutable PDF Archive"),
            ("User Inbox / Phone", "Real-Time Notification"),
            ("PostgreSQL Analytics", "Operational Analytics Replica")
        ],
        "exception_label": "Notification delivery suppression queue",
        "workflow_steps": [
            ("Asynchronous Document Generation", "Transactions (PO approval, GRN receipt, Tax Invoice, e-Way Bill) emit document render events. Background worker executes WeasyPrint to compile pixel-perfect PDFs, uploads to S3/Cloud Storage, and returns secure pre-signed URLs."),
            ("Multi-Channel Notification Dispatch", "Event triggers match configured templates, substituting runtime variables. Messages are dispatched via SMTP email, SMS gateway, or webhook with automatic retry backoff."),
            ("Immutable Audit Logging", "Every mutating REST API request captures `user_id`, `ip_address`, `endpoint`, timestamp, entity name, entity ID, and a JSON diff of pre-change and post-change state. Audit records are tamper-proof."),
            ("Supply Chain Control Tower", "Aggregates cross-module metrics in real-time: Supplier OTIF, Inventory Turn Ratio, WIP Shop Floor Aging, Open Order Fill Rate, and Cash Conversion Cycle, leveraging high-performance PostgreSQL queries for business intelligence.")
        ],
        "upstream_conn": [
            ("All Functional Domains", "Receives transactional triggers, documents to print, and audit state deltas.")
        ],
        "downstream_conn": [
            ("External Stakeholders", "Delivers official signed documents and email alerts to suppliers and customers."),
            ("PostgreSQL Operational Store", "Maintains operational transactional records and aggregated materialized metrics for enterprise reporting.")
        ],
        "state_machine": "DOCUMENT: QUEUED -> RENDERING -> STORED | NOTIFICATION: QUEUED -> SENT -> FAILED"
    }
]


def generate_html():
    css = get_base_css()

    html = []
    html.append(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Axon ERP - Workflow &amp; Cross-Module Architecture Specification</title>
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
            <div class="cover-brand">Axon ERP &bull; Architecture Series</div>
            <h1 class="cover-title">Enterprise Workflow &amp;<br>Cross-Module Integration<br>Specification</h1>
            <div class="cover-subtitle">Complete operational manual, visual vector flowcharts, state machine engines, and cross-module data connection blueprints across all 18 enterprise domains.</div>
            <div class="cover-accent-bar"></div>
            
            <div class="cover-meta-grid">
                <div>
                    <div class="meta-item-label">Platform Version</div>
                    <div class="meta-item-val">v2.4.0 Enterprise Edition</div>
                </div>
                <div>
                    <div class="meta-item-label">Document Classification</div>
                    <div class="meta-item-val">Confidential &bull; System Architecture Reference</div>
                </div>
                <div>
                    <div class="meta-item-label">Core Architecture</div>
                    <div class="meta-item-val">FastAPI &bull; PostgreSQL &bull; React &bull; Redis</div>
                </div>
                <div>
                    <div class="meta-item-label">Publication Date</div>
                    <div class="meta-item-val">October 2026</div>
                </div>
            </div>
        </div>
        <div class="cover-footer">
            &copy; 2026 Axon Technologies Inc. All rights reserved. Prepared for Solution Architects, Software Engineers, and Operations Leadership.
        </div>
    </div>
    """)

    # 2. TABLE OF CONTENTS & EXECUTIVE SUMMARY
    html.append("""
    <div class="page">
        <h2>Executive Summary &amp; Table of Contents</h2>
        <p><strong>Axon ERP</strong> is an enterprise-grade manufacturing and supply chain operating system. It coordinates the end-to-end commercial lifecycle across multi-site manufacturing facilities, automated warehouses, regulatory compliance gateways, and double-entry financial ledgers.</p>
        <p>This technical manual provides an exhaustive operational reference for every domain module in the platform. Each section pairs a <strong>high-fidelity vector flowchart</strong> with precise step-by-step business logic, state machine specifications, and explicit upstream and downstream cross-module integration contracts.</p>
        
        <h3 style="margin-top: 14px; margin-bottom: 8px;">Document Structure &amp; Navigation</h3>
        <div style="margin-bottom: 14px;">
            <div class="toc-item"><span class="toc-num">SEC 0</span><span class="toc-title">Global Enterprise Architecture &amp; Value Stream Flowchart</span><span class="toc-dots"></span><span class="toc-module">Global Supply Chain Topology</span></div>
            <div class="toc-item"><span class="toc-num">MOD 01</span><span class="toc-title">Identity, Authentication &amp; Role-Based Access Control (RBAC)</span><span class="toc-dots"></span><span class="toc-module">/login, /users, /profile</span></div>
            <div class="toc-item"><span class="toc-num">MOD 02</span><span class="toc-title">Parties Master &amp; Approved Vendor List (AVL) Governance</span><span class="toc-dots"></span><span class="toc-module">/parties, /avl-governance</span></div>
            <div class="toc-item"><span class="toc-num">MOD 03</span><span class="toc-title">Business Entities &amp; PO/Invoice Legal Profiles</span><span class="toc-dots"></span><span class="toc-module">/po-invoice</span></div>
            <div class="toc-item"><span class="toc-num">MOD 04</span><span class="toc-title">Facilities, Factories, Warehouses &amp; Multi-Tier WMS Bins</span><span class="toc-dots"></span><span class="toc-module">/factory-warehouse, /wms-bins</span></div>
            <div class="toc-item"><span class="toc-num">MOD 05</span><span class="toc-title">Product Catalog, Engineering BOM &amp; Cost Rollup</span><span class="toc-dots"></span><span class="toc-module">/products</span></div>
            <div class="toc-item"><span class="toc-num">MOD 06</span><span class="toc-title">Supply Chain Planning: Demand Forecasting, MRP &amp; DRP</span><span class="toc-dots"></span><span class="toc-module">/mrp, /drp, /forecasting</span></div>
            <div class="toc-item"><span class="toc-num">MOD 07</span><span class="toc-title">Procurement, Sourcing RFQ &amp; Purchase Orders</span><span class="toc-dots"></span><span class="toc-module">/procurement, /blanket-po</span></div>
            <div class="toc-item"><span class="toc-num">MOD 08</span><span class="toc-title">Inbound Logistics, Advance Shipping Notice &amp; Gate Entry</span><span class="toc-dots"></span><span class="toc-module">/logistics, /freight-tms</span></div>
            <div class="toc-item"><span class="toc-num">MOD 09</span><span class="toc-title">Goods Receipt Notes (GRN), Inbound QC &amp; QR Labeling</span><span class="toc-dots"></span><span class="toc-module">/warehouse, /warehouse-qc</span></div>
            <div class="toc-item"><span class="toc-num">MOD 10</span><span class="toc-title">Inventory Control, Double-Entry Ledger &amp; Cycle Counting</span><span class="toc-dots"></span><span class="toc-module">/inventory, /cycle-counts</span></div>
            <div class="toc-item"><span class="toc-num">MOD 11</span><span class="toc-title">Production Execution, Work Orders, IPQC &amp; Subcontracting</span><span class="toc-dots"></span><span class="toc-module">/production, /subcontracting</span></div>
            <div class="toc-item"><span class="toc-num">MOD 12</span><span class="toc-title">Sales Management, Quotations &amp; Order Intake Booking</span><span class="toc-dots"></span><span class="toc-module">/orders, /customer-portal</span></div>
            <div class="toc-item"><span class="toc-num">MOD 13</span><span class="toc-title">Warehouse Wave Picking, Packing &amp; Cartonization</span><span class="toc-dots"></span><span class="toc-module">/wave-picking, /wms-mobile</span></div>
            <div class="toc-item"><span class="toc-num">MOD 14</span><span class="toc-title">Outbound Logistics, Freight TMS &amp; Statutory e-Way Bills</span><span class="toc-dots"></span><span class="toc-module">/logistics, /shipping-engine</span></div>
            <div class="toc-item"><span class="toc-num">MOD 15</span><span class="toc-title">Customer Returns, Reverse Logistics &amp; RMA Diagnostics</span><span class="toc-dots"></span><span class="toc-module">/returns</span></div>
            <div class="toc-item"><span class="toc-num">MOD 16</span><span class="toc-title">Finance, Accounts Payable/Receivable &amp; 3-Way Match</span><span class="toc-dots"></span><span class="toc-module">/finance</span></div>
            <div class="toc-item"><span class="toc-num">MOD 17</span><span class="toc-title">Landed Cost Capitalization &amp; Inventory Revaluation</span><span class="toc-dots"></span><span class="toc-module">/landed-cost</span></div>
            <div class="toc-item"><span class="toc-num">MOD 18</span><span class="toc-title">Platform Services: Documents, Alerts, Audit &amp; Control Tower</span><span class="toc-dots"></span><span class="toc-module">/documents, /audit, /notifications</span></div>
            <div class="toc-item"><span class="toc-num">SEC 19</span><span class="toc-title">Master Cross-Module Dependency &amp; Integration Matrix</span><span class="toc-dots"></span><span class="toc-module">End-to-End Value Streams</span></div>
        </div>

        <div class="card card-blue" style="margin-top: 10px;">
            <div class="card-title">Architectural Principles &bull; The Modular Monolith Engine</div>
            <p style="font-size: 7.8pt; margin: 0;">Axon ERP is engineered as a clean <em>modular monolith</em> with strictly bounded domains. State transitions in one module (such as GRN approval) trigger transactional side effects in dependent modules (such as Inventory balance increases and Finance 3-way match staging) through domain service contracts and ACID database transactions, preventing data desynchronization.</p>
        </div>
    </div>
    """)

    # 3. GLOBAL ENTERPRISE ARCHITECTURE FLOWCHART
    html.append(f"""
    <div class="page">
        <h2>Global Enterprise Architecture &amp; Value Stream</h2>
        <p>The diagram below depicts the end-to-end operational lifecycle of Axon ERP. Data originates in the foundational governance layers and cascades through procurement, manufacturing, warehousing, order fulfillment, and financial accounting.</p>
        
        <div class="svg-container">
            {generate_global_architecture_svg()}
        </div>

        <div class="grid-2" style="margin-top: 8px;">
            <div class="card card-purple">
                <div class="card-title">Inbound Stream &bull; Procure-to-Pay (P2P)</div>
                <p style="font-size: 7.6pt; margin: 0;">
                    1. <strong>Demand:</strong> Sales orders &amp; forecasts feed the MRP engine.<br>
                    2. <strong>Sourcing:</strong> Requisitions convert to RFQs and approved Purchase Orders.<br>
                    3. <strong>Receipt:</strong> Inbound gate entry creates Gate Passes; warehouse receives and tests goods on GRN.<br>
                    4. <strong>Settlement:</strong> Accepted items auto-post to stock; Finance executes 3-Way Matching against vendor bills.
                </p>
            </div>
            <div class="card card-green">
                <div class="card-title">Outbound Stream &bull; Order-to-Cash (O2C)</div>
                <p style="font-size: 7.6pt; margin: 0;">
                    1. <strong>Booking:</strong> Sales Orders pass credit scrutiny &amp; lock soft stock reservations.<br>
                    2. <strong>Production:</strong> Deficits trigger work orders, consuming staged components.<br>
                    3. <strong>WMS Wave:</strong> Pick waves direct mobile scanners; packing tables seal cartons.<br>
                    4. <strong>Logistics &amp; AR:</strong> TMS secures freight; e-Way Bills issue; dispatch triggers tax invoice.
                </p>
            </div>
        </div>
    </div>
    """)

    # 4. MODULE-BY-MODULE SECTIONS (18 MODULES)
    for mod in MODULES_CATALOG:
        svg_diagram = generate_svg_flowchart(mod)
        
        steps_html = []
        for s_title, s_desc in mod["workflow_steps"]:
            steps_html.append(f"<li><strong>{s_title}:</strong> {s_desc}</li>")
        steps_rendered = "\n".join(steps_html)

        up_conn_html = []
        for u_title, u_desc in mod["upstream_conn"]:
            up_conn_html.append(f"<li><span class=\"integration-item-label\">{u_title}</span><span class=\"integration-item-desc\">{u_desc}</span></li>")
        up_conn_rendered = "\n".join(up_conn_html)

        down_conn_html = []
        for d_title, d_desc in mod["downstream_conn"]:
            down_conn_html.append(f"<li><span class=\"integration-item-label\">{d_title}</span><span class=\"integration-item-desc\">{d_desc}</span></li>")
        down_conn_rendered = "\n".join(down_conn_html)

        html.append(f"""
        <div class="page">
            <div class="module-header">
                <div class="module-header-title">
                    <span class="module-title-text">Module {mod['num']}: {mod['name']}</span>
                    <span class="badge badge-blue">{mod['route']}</span>
                </div>
                <div class="module-meta-strip">
                    <span><strong>Entities:</strong> <code>{mod['entities']}</code></span>
                    <span><strong>Primary Actors:</strong> {mod['roles']}</span>
                </div>
            </div>

            <p style="font-size: 8pt; margin-bottom: 6px;">{mod['overview']}</p>

            <div class="svg-container">
                {svg_diagram}
            </div>

            <div class="grid-2">
                <div class="card card-blue">
                    <div class="card-title">Workflow Execution Logic &amp; Business Rules</div>
                    <ul class="steps-list">
                        {steps_rendered}
                    </ul>
                </div>
                <div class="card card-purple">
                    <div class="card-title">Cross-Module Integration Contract</div>
                    <h3 style="color: #6b21a8; margin-top: 0; font-size: 7.5pt;">Upstream Dependencies (Inflows)</h3>
                    <ul class="integration-list">
                        {up_conn_rendered}
                    </ul>
                    <h3 style="color: #065f46; margin-top: 6px; font-size: 7.5pt;">Downstream Integrations (Outflows)</h3>
                    <ul class="integration-list">
                        {down_conn_rendered}
                    </ul>
                    <div style="margin-top: 6px; padding-top: 4px; border-top: 1px solid #e9d5ff; font-size: 7.2pt; color: #475569;">
                        <strong>Lifecycle State Engine:</strong><br>
                        <code style="font-size: 6.8pt; color: #1e293b;">{mod['state_machine']}</code>
                    </div>
                </div>
            </div>
        </div>
        """)

    # 5. COMPREHENSIVE CROSS-MODULE MASTER MATRIX TABLE (PART I & PART II)
    html.append("""
    <div class="page">
        <h2>Cross-Module Master Integration Matrix &bull; Part I: Inbound &amp; Manufacturing</h2>
        <p>This master matrix maps explicit cause-and-effect data relationships across domain boundaries when key business events occur during foundation setup, planning, procurement, receiving, and production.</p>
        
        <table class="spec-table">
            <thead>
                <tr>
                    <th style="width: 15%;">Source Module &amp; Trigger</th>
                    <th style="width: 15%;">Business Event</th>
                    <th style="width: 15%;">Target Module</th>
                    <th style="width: 25%;">Impacted Entity &amp; State Change</th>
                    <th style="width: 30%;">Operational &amp; Financial Impact</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>M01: Identity</strong><br>Login / Session</td>
                    <td>User authenticates via native credentials or MFA</td>
                    <td><strong>All Application Domains</strong></td>
                    <td><code>sessions.is_active = True</code><br>Injects <code>allowed_warehouses</code></td>
                    <td>Enforces row-level site scoping; operators cannot view or manipulate inventory outside authorized facilities.</td>
                </tr>
                <tr>
                    <td><strong>M02: Parties</strong><br>Vendor Blacklist</td>
                    <td>Vendor fails audit or tax registration lapses</td>
                    <td><strong>M07: Procurement &amp;<br>M16: Finance</strong></td>
                    <td><code>parties.status = 'BLOCKED'</code><br><code>party.avl_rating = 'DISQUALIFIED'</code></td>
                    <td>Blocks creation of new Purchase Orders; freezes outstanding AP payment voucher disbursement pending audit.</td>
                </tr>
                <tr>
                    <td><strong>M03: Entities</strong><br>GSTIN Registration</td>
                    <td>New state tax branch entity approved</td>
                    <td><strong>M07: Procurement &amp;<br>M14: Logistics</strong></td>
                    <td><code>business_entities.status = 'ACTIVE'</code><br>Linked to local factory</td>
                    <td>Governs intrastate (CGST+SGST) vs interstate (IGST) tax calculation; populates consignor in e-Way bills.</td>
                </tr>
                <tr>
                    <td><strong>M04: Facilities</strong><br>WMS Bin Lock</td>
                    <td>Bin physical damage or audit freeze</td>
                    <td><strong>M09: GRN Putaway &amp;<br>M13: Wave Picking</strong></td>
                    <td><code>locations.is_locked = True</code></td>
                    <td>Prevents putaway tasks from routing to this bin; redirects pick wave algorithms around locked storage aisles.</td>
                </tr>
                <tr>
                    <td><strong>M05: Products</strong><br>BOM Revision Lock</td>
                    <td>Engineering releases approved BOM v2.0</td>
                    <td><strong>M06: Planning (MRP) &amp;<br>M11: Production</strong></td>
                    <td><code>bom_versions.status = 'ACTIVE'</code><br>Old version marked <code>OBSOLETE</code></td>
                    <td>MRP explodes new component tree; subsequent Work Orders draw revised part quantities; obsoleted parts blocked.</td>
                </tr>
                <tr>
                    <td><strong>M06: Planning</strong><br>MRP Run Complete</td>
                    <td>Time-phased net deficit calculation finishes</td>
                    <td><strong>M07: Procurement &amp;<br>M11: Production</strong></td>
                    <td>Inserts rows into <code>purchase_requisitions</code><br>Inserts rows into <code>production_runs</code></td>
                    <td>Generates planned purchase requisitions with vendor lead-time offsetting; drafts manufacturing orders for assembly lines.</td>
                </tr>
                <tr>
                    <td><strong>M07: Procurement</strong><br>PO Approval</td>
                    <td>Final signature limit sign-off approved</td>
                    <td><strong>M08: Logistics &amp;<br>M09: GRN &amp;<br>M16: Finance</strong></td>
                    <td><code>purchase_orders.status = 'APPROVED'</code><br><code>po_lines.is_locked = True</code></td>
                    <td>Publishes order to Vendor Portal; opens receiving window at warehouse gate; locks price ceiling for 3-way match.</td>
                </tr>
                <tr>
                    <td><strong>M08: Logistics</strong><br>Gate Entry Pass</td>
                    <td>Inbound truck arrives with vendor shipment</td>
                    <td><strong>M09: Warehouse Receiving</strong></td>
                    <td><code>gate_entries.status = 'DOCK_ASSIGNED'</code><br>Generates <code>INW-YYYY-XXXXX</code></td>
                    <td>Permits receiving staff to initialize Draft GRN linked to confirmed gate manifest; starts dock dwell time tracking.</td>
                </tr>
                <tr>
                    <td><strong>M09: Warehouse GRN</strong><br>QC Approval &amp; Putaway</td>
                    <td>Sampling inspection accepts incoming batch</td>
                    <td><strong>M10: Inventory &amp;<br>M16: Finance &amp;<br>M02: Supplier AVL</strong></td>
                    <td><code>grns.status = 'COMPLETED'</code><br>Inserts into <code>stock_ledger</code> &amp; <code>inventory_items</code></td>
                    <td>Increments real-time stock balance; generates QR stickers; registers maximum payable quantity for AP 3-Way Match.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="page">
        <h2>Cross-Module Master Integration Matrix &bull; Part II: Outbound &amp; Finance</h2>
        <p>This section maps downstream cause-and-effect relationships during production completion, order allocation, warehouse wave picking, freight transportation, customer returns, and financial settlement.</p>
        
        <table class="spec-table">
            <thead>
                <tr>
                    <th style="width: 15%;">Source Module &amp; Trigger</th>
                    <th style="width: 15%;">Business Event</th>
                    <th style="width: 15%;">Target Module</th>
                    <th style="width: 25%;">Impacted Entity &amp; State Change</th>
                    <th style="width: 30%;">Operational &amp; Financial Impact</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>M10: Inventory</strong><br>Cycle Count Variance</td>
                    <td>Auditor posts blind count reconciliation</td>
                    <td><strong>M16: Finance (GL) &amp;<br>M18: Audit Trail</strong></td>
                    <td><code>stock_ledger</code> adjustment posted<br>Creates journal voucher</td>
                    <td>Updates physical inventory balances to match truth; posts inventory shrinkage or surplus variance to P&amp;L expense.</td>
                </tr>
                <tr>
                    <td><strong>M11: Production</strong><br>Run Completion</td>
                    <td>Assembly finishes; IPQC passes yield</td>
                    <td><strong>M10: Inventory &amp;<br>M12: Sales Orders &amp;<br>M16: Finance</strong></td>
                    <td>Inserts FG into <code>inventory_items</code><br>Updates <code>finished_good_allocations</code></td>
                    <td>Increments finished goods stock; binds serials to waiting Make-to-Order Sales Orders; posts labor &amp; overhead cost variances.</td>
                </tr>
                <tr>
                    <td><strong>M12: Sales Orders</strong><br>Order Booking</td>
                    <td>Customer signs commercial quote</td>
                    <td><strong>M02: Parties &amp;<br>M10: Inventory &amp;<br>M13: Wave Picking</strong></td>
                    <td><code>orders.status = 'APPROVED'</code><br>Inserts into <code>reservations</code></td>
                    <td>Deducts available credit limit; places soft allocation on inventory; queues order lines on warehouse fulfillment consoles.</td>
                </tr>
                <tr>
                    <td><strong>M13: Wave Picking</strong><br>Packing Complete</td>
                    <td>Cartons packed, weighed, and sealed</td>
                    <td><strong>M10: Inventory &amp;<br>M14: Outbound TMS</strong></td>
                    <td><code>wave_picks.status = 'PACKED'</code><br>Decrements physical <code>stock_balances</code></td>
                    <td>Permanently issues inventory out of warehouse; sends package dimensions and weight to transport shipping engine.</td>
                </tr>
                <tr>
                    <td><strong>M14: Logistics</strong><br>Goods Gate Outward</td>
                    <td>Vehicle leaves with e-Way Bill &amp; Challan</td>
                    <td><strong>M12: Sales Orders &amp;<br>M16: Finance (AR)</strong></td>
                    <td><code>orders.status = 'SHIPPED'</code><br>Auto-generates <code>ar_invoices</code></td>
                    <td>Transitions Sales Order to shipped; automatically generates tax invoice with GST liability; updates customer ledger.</td>
                </tr>
                <tr>
                    <td><strong>M15: Returns</strong><br>RMA QC Disposition</td>
                    <td>Returned unit inspected &amp; approved</td>
                    <td><strong>M10: Inventory &amp;<br>M16: Finance (AR)</strong></td>
                    <td>Restocks unit to <code>stock_balances</code><br>Inserts into <code>credit_notes</code></td>
                    <td>Re-inducts sanitized item into good inventory bin; creates official Credit Note reducing customer outstanding debt.</td>
                </tr>
                <tr>
                    <td><strong>M16: Finance</strong><br>AP 3-Way Match Pass</td>
                    <td>PO, GRN, and Vendor Invoice align</td>
                    <td><strong>M02: Parties Ledger &amp;<br>M18: Bank Integration</strong></td>
                    <td><code>ap_invoices.status = 'APPROVED'</code><br>Queues payment in <code>payments</code></td>
                    <td>Credits accounts payable ledger; queues disbursement in upcoming bank NEFT/RTGS payment run.</td>
                </tr>
                <tr>
                    <td><strong>M17: Landed Cost</strong><br>LCV Voucher Post</td>
                    <td>Customs and maritime freight allocated</td>
                    <td><strong>M10: Inventory Balances &amp;<br>M16: Finance GL</strong></td>
                    <td>Updates <code>stock_ledger.valuation_rate</code><br>Debits Inventory Asset Account</td>
                    <td>Capitalizes shipping duties into true inventory cost; adjusts balance sheet asset valuation; refines gross margin accuracy.</td>
                </tr>
                <tr>
                    <td><strong>M18: Platform</strong><br>Document Generated</td>
                    <td>Async PDF render completes</td>
                    <td><strong>External Parties &amp;<br>Documents Archive</strong></td>
                    <td>Updates <code>documents.status = 'READY'</code><br>Dispatches email notification</td>
                    <td>Delivers digitally signed PDF copy to supplier/customer inbox; archives encrypted copy in immutable S3 storage.</td>
                </tr>
            </tbody>
        </table>
    </div>
    """)

    # 6. END-TO-END VALUE STREAM WALKTHROUGHS & AUDIT ARCHITECTURE
    html.append("""
    <div class="page">
        <h2>End-to-End Enterprise Value Streams &amp; Governance</h2>
        <p>In enterprise operations, business activities cross multiple domain modules concurrently. Below are detailed architectural walkthroughs for the two primary commercial engines of the system.</p>

        <div class="card card-purple" style="margin-bottom: 10px;">
            <div class="card-title">1. The Procure-to-Pay (P2P) Complete Operational Journey</div>
            <p style="font-size: 7.7pt; line-height: 1.4; margin: 0;">
                <strong>Phase 1: Demand &amp; Sourcing (M06 &rarr; M07 &rarr; M02):</strong> The MRP engine nets sales demand against stock and emits a Requisition. Buyer initiates an RFQ to Approved Vendor List (AVL) suppliers. The lowest qualified bid converts into an official Purchase Order. Approval rules require Director sign-off based on spend limits. The PO is digitally issued to the vendor.<br>
                <strong>Phase 2: Inbound Delivery &amp; Gate Verification (M08 &rarr; M09):</strong> The vendor ships goods with an ASN. Upon arrival, Security verifies vehicle seals, records gross weighbridge tonnage, and mints an Inward Gate Entry Pass. The truck unloads at the assigned receiving dock.<br>
                <strong>Phase 3: Receipt, QC &amp; Inventory Induction (M09 &rarr; M10 &rarr; M18):</strong> Receiving verifies PO lines against over-receipt tolerance. QC pulls test samples; upon approval, thermal QR stickers are printed and affixed. Forklifts put away pallets into WMS bins. Stock ledger records the receipt, increasing available inventory.<br>
                <strong>Phase 4: Financial Matching &amp; Disbursement (M16 &rarr; M17 &rarr; M02):</strong> Vendor submits electronic bill. System executes 3-Way Matching: PO unit price vs Invoice price, GRN accepted quantity vs Invoiced quantity. If matching succeeds within tolerance, AP invoice approves. Landed cost freight vouchers capitalize into inventory value. Bank payment voucher disburses funds.
            </p>
        </div>

        <div class="card card-green" style="margin-bottom: 10px;">
            <div class="card-title">2. The Order-to-Cash (O2C) Complete Operational Journey</div>
            <p style="font-size: 7.7pt; line-height: 1.4; margin: 0;">
                <strong>Phase 1: Intake &amp; Credit Clearance (M02 &rarr; M12 &rarr; M03):</strong> Customer submits commercial order. System checks party credit ceiling: total unpaid AR + open orders cannot exceed the limit. Pricing engine applies volume tiers and GST rates based on seller business entity.<br>
                <strong>Phase 2: Inventory Allocation &amp; Manufacturing Trigger (M12 &rarr; M10 &rarr; M11):</strong> System evaluates Available-to-Promise (ATP). Available inventory is locked with a hard reservation. Any inventory deficit automatically triggers a Work Order in Production, pulling BOM recipes and staging raw materials.<br>
                <strong>Phase 3: Warehouse Wave Picking &amp; Packaging (M13 &rarr; M10 &rarr; M04):</strong> Fulfillment generates pick waves. Mobile RF scanners guide pickers along shortest bin paths. Packing tables scan-verify 100% item accuracy, pack into shipping cartons, capture gross scale weights, and print carton barcodes.<br>
                <strong>Phase 4: TMS Dispatch, Statutory e-Way Bill &amp; Invoicing (M14 &rarr; M16 &rarr; M18):</strong> Transporter RFQ secures freight carrier. System calls government API to generate electronic e-Way Bill and Tax Invoice (IRN). Gate officer verifies outward pass. Upon delivery, driver uploads signed Proof of Delivery (POD), completing the commercial transaction.
            </p>
        </div>

        <div class="card card-blue">
            <div class="card-title">System Reliability, ACID Transactions &amp; PostgreSQL Analytics</div>
            <p style="font-size: 7.7pt; line-height: 1.4; margin: 0;">
                &bull; <strong>ACID Transaction Isolation:</strong> Multi-table operations (e.g., GRN posting creating stock ledger entries, inventory items, and updating PO line balances) execute inside atomic database transactions (`session.begin()`). Any mid-flight failure rolls back all mutations completely.<br>
                &bull; <strong>Idempotency Enforcement:</strong> All mutation endpoints support `Idempotency-Key` headers stored in Redis/PostgreSQL, preventing double-posting of receipts, invoices, or payments during network timeouts.<br>
                &bull; <strong>High-Performance PostgreSQL Analytics:</strong> Operational transactional tables leverage optimized composite indexing, PostgreSQL window functions, and real-time aggregation views, empowering executive Control Tower BI dashboards without impacting OLTP database performance.
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
    print("Axon ERP: Compiling Technical Specification PDF...")
    print("==================================================================")

    output_pdf_path = os.path.abspath("Axon_ERP_Workflows_and_Module_Integration.pdf")
    
    print("[1/3] Generating comprehensive HTML specification with vector SVG flowcharts...")
    html_content = generate_html()

    # Save HTML scratch file for reference / debugging if needed
    html_debug_path = os.path.abspath("workflow_spec_debug.html")
    with open(html_debug_path, "w", encoding="utf-8") as f:
        f.write(html_content)
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
