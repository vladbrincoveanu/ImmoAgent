import type { Config } from 'jest';

const config: Config = {
  testEnvironment: 'node',
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        module: 'commonjs',
      },
    }],
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
};

export default config;
