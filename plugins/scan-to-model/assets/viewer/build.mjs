import { build } from 'esbuild';

// Keep the viewer's libraries, geometry and textures available to local file URLs.
await build({
  entryPoints: ['viewer.js'],
  outfile: 'viewer.bundle.js',
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: 'es2020',
  loader: { '.glb': 'binary' },
  minify: true,
  legalComments: 'linked',
});
