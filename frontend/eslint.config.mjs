import { dirname } from 'path';
import { fileURLToPath } from 'url';
import { FlatCompat } from '@eslint/eslintrc';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({ baseDirectory: __dirname });

const config = [
  {
    // `.next-docker` is the compose dev container's build output.
    ignores: ['.next/**', '.next-docker/**', 'node_modules/**', 'next-env.d.ts'],
  },
  ...compat.extends('next/core-web-vitals', 'next/typescript', 'prettier'),
  {
    rules: {
      // Physical-direction Tailwind utilities break RTL. `npm run lint:rtl`
      // does the thorough scan; this catches the common inline cases early.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "JSXAttribute[name.name='className'] > Literal[value=/(^|\\s)(-?(ml|mr|pl|pr|left|right|border-l|border-r|rounded-l|rounded-r|text-left|text-right|float-left|float-right)(-|\\s|$))/]",
          message:
            'Use logical Tailwind utilities (ms-/me-/ps-/pe-/start-/end-/text-start) so the UI works in both RTL and LTR.',
        },
      ],
    },
  },
];

export default config;
