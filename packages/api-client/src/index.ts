import createClient, { type Middleware } from 'openapi-fetch';
import type { paths as CustomersPaths } from './generated/customers';
import type { paths as IdentityPaths } from './generated/identity';

export type { CustomersPaths, IdentityPaths };
export type { components as CustomersSchemas } from './generated/customers';
export type { components as IdentitySchemas } from './generated/identity';

/**
 * Усі запити йдуть через gateway — жодного прямого звернення до сервісу.
 * У дев-режимі роль gateway виконує проксі Vite.
 */
const BASE_URL = '/api';

/** Підставляє токен у кожен запит. Джерело токена задає каркас. */
let getToken: () => string | null = () => null;

export function setTokenProvider(provider: () => string | null): void {
  getToken = provider;
}

/**
 * Що робити, коли gateway відповів 401: токен прострочений або людину вимкнули.
 * Каркас передає сюди вихід на екран входу; модулі про це не знають.
 */
let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

const auth: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    // Лише якщо токен був: 401 на сам вхід — це «невірний пароль», а не вихід.
    if (response.status === 401 && getToken()) onUnauthorized();
    return response;
  },
};

function makeClient<T extends object>() {
  const client = createClient<T>({ baseUrl: BASE_URL });
  client.use(auth);
  return client;
}

/** Клієнт блоку `customers`. Типи згенеровані з contracts/customers.yaml. */
export const customersApi = makeClient<CustomersPaths>();

/** Клієнт блоку `identity`. Типи згенеровані з contracts/identity.yaml. */
export const identityApi = makeClient<IdentityPaths>();
