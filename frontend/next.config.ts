import path from 'node:path';

import createNextIntlPlugin from 'next-intl/plugin';
import type { NextConfig } from 'next';

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The docker dev container bind-mounts this directory, so it builds into its
  // own folder rather than trampling a host-side build.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  // This app is deployed with `next start` behind a reverse proxy (see
  // docs/deployment.md), not as a standalone server bundle.
  outputFileTracingRoot: path.join(__dirname),
  eslint: {
    // Lint is a separate, explicit step (`npm run lint`) so builds stay fast.
    ignoreDuringBuilds: true,
  },
};

export default withNextIntl(nextConfig);
