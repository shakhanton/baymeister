import {
  catalogApi,
  customersApi,
  vehiclesApi,
  workOrdersApi,
  type WorkOrdersSchemas,
} from '@baymeister/api-client';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type Order = WorkOrdersSchemas['schemas']['Order'];
export type OrderCreate = WorkOrdersSchemas['schemas']['OrderCreate'];
export type OrderStatus = WorkOrdersSchemas['schemas']['OrderStatus'];
export type Line = WorkOrdersSchemas['schemas']['Line'];

export interface ListParams {
  search?: string;
  status?: OrderStatus;
  limit?: number;
  offset?: number;
}

const keys = {
  all: ['work-orders'] as const,
  list: (params: ListParams) => [...keys.all, 'list', params] as const,
  one: (id: string) => [...keys.all, 'one', id] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

export function useOrders(params: ListParams) {
  return useQuery({
    queryKey: keys.list(params),
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await workOrdersApi.GET('/work-orders', { params: { query: params } });
      if (error) fail(error, 'Не вдалося завантажити наряди');
      return data;
    },
  });
}

export function useOrder(orderId: string) {
  return useQuery({
    queryKey: keys.one(orderId),
    queryFn: async () => {
      const { data, error } = await workOrdersApi.GET('/work-orders/{orderId}', {
        params: { path: { orderId } },
      });
      if (error) fail(error, 'Не вдалося завантажити наряд');
      return data;
    },
  });
}

/** Кожна зміна повертає весь наряд — кладемо його в кеш без зайвого запиту. */
function useOrderMutation<T>(orderId: string, run: (arg: T) => Promise<Order>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (order) => {
      queryClient.setQueryData(keys.one(orderId), order);
      void queryClient.invalidateQueries({ queryKey: [...keys.all, 'list'] });
    },
  });
}

export function useOpenOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: OrderCreate) => {
      const { data, error } = await workOrdersApi.POST('/work-orders', { body });
      if (error) fail(error, 'Не вдалося відкрити наряд');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useChangeStatus(orderId: string) {
  return useOrderMutation(orderId, async (status: OrderStatus) => {
    const { data, error } = await workOrdersApi.POST('/work-orders/{orderId}/status', {
      params: { path: { orderId } },
      body: { status },
    });
    if (error) fail(error, 'Не вдалося змінити статус');
    return data;
  });
}

export function useUpdateOrder(orderId: string) {
  return useOrderMutation(
    orderId,
    async (body: { complaint?: string | null; mileage_km?: number | null; notes?: string | null }) => {
      const { data, error } = await workOrdersApi.PATCH('/work-orders/{orderId}', {
        params: { path: { orderId } },
        body,
      });
      if (error) fail(error, 'Не вдалося зберегти');
      return data;
    },
  );
}

export function useAddLine(orderId: string) {
  return useOrderMutation(
    orderId,
    async (body: { kind: 'service' | 'part'; catalog_id: string; qty?: string }) => {
      const { data, error } = await workOrdersApi.POST('/work-orders/{orderId}/lines', {
        params: { path: { orderId } },
        body,
      });
      if (error) fail(error, 'Не вдалося додати рядок');
      return data;
    },
  );
}

export function useUpdateLine(orderId: string) {
  return useOrderMutation(orderId, async ({ lineId, qty }: { lineId: string; qty: string }) => {
    const { data, error } = await workOrdersApi.PATCH('/work-orders/{orderId}/lines/{lineId}', {
      params: { path: { orderId, lineId } },
      body: { qty },
    });
    if (error) fail(error, 'Не вдалося змінити кількість');
    return data;
  });
}

export function useRemoveLine(orderId: string) {
  return useOrderMutation(orderId, async (lineId: string) => {
    const { data, error } = await workOrdersApi.DELETE('/work-orders/{orderId}/lines/{lineId}', {
      params: { path: { orderId, lineId } },
    });
    if (error) fail(error, 'Не вдалося прибрати рядок');
    return data;
  });
}

// ── Сусідні блоки — через їхні публічні API, не через код модулів ─────────────

export function useCustomerSearch(search: string) {
  return useQuery({
    queryKey: ['work-orders', 'customer-search', search],
    enabled: search.trim().length >= 2,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await customersApi.GET('/customers', {
        params: { query: { search: search.trim(), limit: 8 } },
      });
      if (error) fail(error, 'Не вдалося знайти клієнтів');
      return data.items;
    },
  });
}

export function useCustomer(customerId: string | null) {
  return useQuery({
    queryKey: ['work-orders', 'customer', customerId],
    enabled: customerId !== null,
    queryFn: async () => {
      const { data, error } = await customersApi.GET('/customers/{customerId}', {
        params: { path: { customerId: customerId ?? '' } },
      });
      if (error) fail(error, 'Не вдалося завантажити клієнта');
      return data;
    },
  });
}

export function useCustomerVehicles(customerId: string | null) {
  return useQuery({
    queryKey: ['work-orders', 'customer-vehicles', customerId],
    enabled: customerId !== null,
    queryFn: async () => {
      const { data, error } = await vehiclesApi.GET('/vehicles', {
        params: { query: { customer_id: customerId ?? undefined, limit: 50 } },
      });
      if (error) fail(error, 'Не вдалося завантажити автомобілі');
      return data.items;
    },
  });
}

export function useCatalogSearch(kind: 'service' | 'part', search: string) {
  return useQuery({
    queryKey: ['work-orders', 'catalog', kind, search],
    enabled: search.trim().length >= 1,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const query = { search: search.trim(), limit: 8 };
      if (kind === 'service') {
        const { data, error } = await catalogApi.GET('/catalog/services', { params: { query } });
        if (error) fail(error, 'Не вдалося знайти роботи');
        return data.items.map((s) => ({ id: s.id, code: s.code, name: s.name, price: s.price }));
      }
      const { data, error } = await catalogApi.GET('/catalog/parts', { params: { query } });
      if (error) fail(error, 'Не вдалося знайти запчастини');
      return data.items.map((p) => ({
        id: p.id,
        code: `${p.brand} ${p.sku}`,
        name: p.name,
        price: p.price as string | null,
      }));
    },
  });
}
