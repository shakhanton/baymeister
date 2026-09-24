import importX, { createNodeResolver } from 'eslint-plugin-import-x';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

/**
 * Межі між пакетами — головне, що тут перевіряється.
 *
 * Блок не імпортує код іншого блоку і не знає про каркас: спільне живе тільки
 * в packages/ui і packages/module-kit. Каркас підключає модулі в одному місці —
 * реєстрі. Порушення цих меж — помилка лінту, а не тема для рев'ю.
 */
// Пакети блоків: @baymeister/module-<блок>, але не module-kit — він спільний.
const MODULE_PACKAGE_REGEX = '^@baymeister/module-(?!kit($|/))';

const MODULE_PACKAGES = {
  regex: MODULE_PACKAGE_REGEX,
  message: 'Блок не імпортує інший блок. Спільне — у @baymeister/ui або @baymeister/module-kit, дані — через API або події.',
};

const SHELL_PACKAGE = {
  group: ['@baymeister/shell', '@baymeister/shell/*'],
  message: 'Каркас знає про модулі, модулі про каркас — ні. Потрібне від каркаса передається через module-kit.',
};

export default tseslint.config(
  {
    ignores: ['**/dist/**', '**/node_modules/**', '**/.turbo/**', 'packages/api-client/src/generated/**', 'services/**'],
  },

  ...tseslint.configs.recommended,

  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    settings: {
      // Без резолвера з .ts/.tsx правило не знає, куди веде відносний шлях, і мовчить.
      'import-x/resolver-next': [
        createNodeResolver({ extensions: ['.ts', '.tsx', '.js', '.mjs', '.json'] }),
      ],
    },
    plugins: {
      'import-x': importX,
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Відносний шлях у сусідній пакет обходить межу так само, як імпорт за іменем.
      'import-x/no-relative-packages': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },

  // Модулі блоків: ні інших блоків, ні каркаса.
  {
    files: ['packages/modules/*/src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [MODULE_PACKAGES, SHELL_PACKAGE] }],
    },
  },

  // Спільні пакети — фундамент: вони не можуть залежати від блоків чи каркаса.
  {
    files: ['packages/{ui,module-kit,api-client}/src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [MODULE_PACKAGES, SHELL_PACKAGE] }],
    },
  },

  // Каркас підключає модулі тільки в реєстрі — «один рядок на блок».
  {
    files: ['apps/shell/src/**/*.{ts,tsx}'],
    ignores: ['apps/shell/src/modules/registry.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              regex: MODULE_PACKAGE_REGEX,
              message: 'Модулі підключаються тільки в apps/shell/src/modules/registry.ts.',
            },
          ],
        },
      ],
    },
  },

  // Конфіги й скрипти збірки виконуються в Node, не в браузері.
  {
    files: ['**/*.config.{js,ts}', '**/scripts/**/*.{js,mjs}'],
    languageOptions: { globals: globals.node },
  },
);
