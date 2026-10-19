# -*- coding: utf-8 -*-
"""SVG source for the application icon.

The icon is a blue/white USB 2.4G receiver: a USB-A plug, a rounded body
with a "2.4G" label and small wireless arcs.  Keeping it as SVG means the
same artwork drives the window icon, the About logo and assets/app.ico.
"""

APP_ICON_SVG = r"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#5aa8ff"/>
      <stop offset="0.55" stop-color="#2f7df6"/>
      <stop offset="1" stop-color="#1a5fd6"/>
    </linearGradient>
    <linearGradient id="body" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#e9f3ff"/>
    </linearGradient>
    <linearGradient id="label" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#4a94ff"/>
      <stop offset="1" stop-color="#2a6fe0"/>
    </linearGradient>
    <linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect x="8" y="8" width="240" height="240" rx="58" fill="url(#tile)"/>
  <path d="M24 92 C54 30 202 30 232 92 L232 66 C232 32 200 8 166 8 L90 8 C56 8 24 32 24 66 Z"
        fill="url(#gloss)"/>

  <!-- wireless arcs -->
  <g fill="none" stroke="#ffffff" stroke-linecap="round">
    <path d="M66 96 C55 110 55 138 66 152" stroke-width="6" opacity="0.85"/>
    <path d="M52 84 C33 106 33 142 52 164" stroke-width="6" opacity="0.45"/>
    <path d="M190 96 C201 110 201 138 190 152" stroke-width="6" opacity="0.85"/>
    <path d="M204 84 C223 106 223 142 204 164" stroke-width="6" opacity="0.45"/>
  </g>

  <!-- receiver shadow -->
  <rect x="90" y="48" width="76" height="160" rx="26" fill="#0b3d91" opacity="0.24"/>

  <!-- USB-A plug -->
  <rect x="99" y="36" width="58" height="58" rx="10" fill="#ffffff" stroke="#d7e7fa" stroke-width="2"/>
  <rect x="112" y="52" width="14" height="14" rx="3.5" fill="#2f7df6"/>
  <rect x="130" y="52" width="14" height="14" rx="3.5" fill="#2f7df6"/>
  <rect x="112" y="72" width="32" height="4" rx="2" fill="#dceafc"/>

  <!-- rounded body -->
  <rect x="84" y="86" width="88" height="116" rx="24" fill="url(#body)" stroke="#d7e7fa" stroke-width="2"/>
  <rect x="95" y="126" width="66" height="44" rx="13" fill="url(#label)"/>
  <text x="128" y="158" text-anchor="middle"
        font-family="Segoe UI"
        font-size="26" font-weight="700" letter-spacing="0.4"
        fill="#ffffff">2.4G</text>
  <circle cx="128" cy="188" r="5" fill="#a9d4ff"/>
  <circle cx="128" cy="188" r="2.2" fill="#ffffff" opacity="0.85"/>
</svg>
"""
