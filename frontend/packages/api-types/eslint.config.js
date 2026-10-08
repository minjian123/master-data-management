import js from '@eslint/js'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { name: 'api-types/files-to-lint', files: ['**/*.{ts,mts,mjs}'] },
  {
    name: 'api-types/files-to-ignore',
    ignores: ['**/node_modules/**', '**/coverage/**'],
  },
  {
    // 显式锚定 TS 配置根：monorepo 下工具工作目录不确定时避免解析器报「多个候选 TSConfigRootDirs」
    name: 'api-types/tsconfig-root',
    files: ['**/*.{ts,mts,mjs}'],
    languageOptions: { parserOptions: { tsconfigRootDir: import.meta.dirname } },
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    name: 'api-types/node-scripts',
    files: ['scripts/**/*.mjs'],
    languageOptions: { globals: { console: 'readonly', process: 'readonly' } },
  },
  skipFormatting,
)
