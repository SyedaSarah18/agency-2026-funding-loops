import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this directory. Without this, Next.js 16 walks
  // up the tree and picks the first package-lock.json it finds — which on this
  // machine is an orphan stub at C:\Users\SarahSyeda\package-lock.json, making
  // the dev server resolve from the wrong directory and the app/api/* routes
  // 404. Pinning makes Next.js resolve from frontend/.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
