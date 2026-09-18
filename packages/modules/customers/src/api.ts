import { customersApi, type CustomersSchemas } from '@baymeister/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type Customer = CustomersSchemas['schemas']['Customer'];
export type CustomerCreate = CustomersSchemas['schemas']['CustomerCreate'];
export type CustomerUpdate = CustomersSchemas['schemas']['CustomerUpdate'];
export type CustomerType = CustomersSchemas['schemas']['CustomerType'];

export interface ListParams {
  search?: string;
  type?: CustomerType;
  archived?: boolean;
  limit?: number;
  offset?: number;
}

const keys = {
  all: ['customers'] as const,
  list: (params: ListParams) => [...keys.all, 'list', params] as const,
  one: (id: string) => [...keys.all, 'one', id] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

export function useCustomers(params: ListParams) {
  return useQuery({
    queryKey: keys.list(params),
    queryFn: async () => {
      const { data, error } = await customersApi.GET('/customers', {
        params: { query: params },
      });
      if (error) fail(error, 'Не вдалося завантажити список клієнтів');
      return data;
    },
  });
}

export function useCustomer(customerId: string) {
  return useQuery({
    queryKey: keys.one(customerId),
    queryFn: async () => {
      const { data, error } = await customersApi.GET('/customers/{customerId}', {
        params: { path: { customerId } },
      });
      if (error) fail(error, 'Не вдалося завантажити клієнта');
      return data;
    },
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CustomerCreate) => {
      const { data, error } = await customersApi.POST('/customers', { body });
      if (error) fail(error, 'Не вдалося створити клієнта');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateCustomer(customerId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: CustomerUpdate) => {
      const { data, error } = await customersApi.PATCH('/customers/{customerId}', {
        params: { path: { customerId } },
        body,
      });
      if (error) fail(error, 'Не вдалося зберегти зміни');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useArchiveCustomer(customerId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const { data, error } = await customersApi.POST('/customers/{customerId}/archive', {
        params: { path: { customerId } },
      });
      if (error) fail(error, 'Не вдалося архівувати клієнта');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}
