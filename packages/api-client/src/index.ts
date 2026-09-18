import createClient, { type Middleware } from 'openapi-fetch';
import type { paths as CustomersPaths } from './generated/customers';

export type { CustomersPaths };
export type { components as CustomersSchemas } from './generated/customers';

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

const auth: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
};

function makeClient<T extends {}>() {
  const client = createClient<T>({ baseUrl: BASE_URL });
  client.use(auth);
  return client;
}

/** Клієнт блоку `customers`. Типи згенеровані з contracts/customers.yaml. */
export const customersApi = makeClient<CustomersPaths>();
