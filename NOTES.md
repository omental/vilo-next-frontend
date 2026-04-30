# Vuexy Pattern Notes

Source inspected: saved Vuexy analytics dashboard reference markup.

Patterns extracted from the saved Vuexy page:

- Dashboard shell: a fixed vertical menu on the left, a detached sticky navbar, and a padded content container.
- Sidebar: grouped navigation sections with expandable headings, active child links, brand mark, and small count badges.
- Navbar: search-first utility row with compact action buttons, notifications, and user affordances.
- Cards: soft borders, rounded corners, light shadows, clear card header/body split, and mixed content types inside the same card frame.
- Tables: search toolbar above a compact table, project identity cell, avatar stack, inline progress bar, and trailing row action.
- Charts: Vuexy embeds ApexCharts markup, but the reusable pattern is really lightweight summary charts inside cards. In React, these are better expressed as plain SVG or a chart wrapper component instead of copied vendor DOM.

Implementation in this workspace:

- `app/*`: Next.js App Router entrypoints and global styles
- `components/layout/*`: shell, sidebar, and navbar
- `components/dashboard/*`: dashboard-specific sections built with static mock data
