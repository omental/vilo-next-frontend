# Vuexy Pattern Notes

Source inspected: `/Users/muba/Desktop/vuexy/Demo_ Dashboard - Analytics _ Vuexy - Bootstrap Dashboard PRO.html`

Patterns extracted from the saved Vuexy page:

- Dashboard shell: a fixed vertical menu on the left, a detached sticky navbar, and a padded content container.
- Sidebar: grouped navigation sections with expandable headings, active child links, brand mark, and small count badges.
- Navbar: search-first utility row with compact action buttons, notifications, and user affordances.
- Cards: soft borders, rounded corners, light shadows, clear card header/body split, and mixed content types inside the same card frame.
- Tables: search toolbar above a compact table, project identity cell, avatar stack, inline progress bar, and trailing row action.
- Charts: Vuexy embeds ApexCharts markup, but the reusable pattern is really lightweight summary charts inside cards. In React, these are better expressed as plain SVG or a chart wrapper component instead of copied vendor DOM.

Implementation in this workspace:

- `src/components/layout/*`: shell, sidebar, and navbar
- `src/components/ui/*`: generic card and data table primitives
- `src/components/charts/*`: small React chart components built with SVG/divs
- `src/components/patterns/*`: dashboard-specific compositions built on top of the primitives
- `src/App.jsx`: demo page showing the extracted patterns working together
