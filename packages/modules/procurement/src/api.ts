import { catalogApi, procurementApi, type ProcurementSchemas } from '@baymeister/api-client';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

type S = ProcurementSchemas['schemas'];
export type Supplier = S['Supplier'];
export type Order = S['Order'];
export type OrderSummary = S['OrderSummary'];
export type Line = S['Line'];
export type Need = S['Need'];
export type OrderStatus = S['Status'];

const keys = {
  all: ['procurement'] as const,
  orders: (search: string, status: OrderStatus | null) => [...keys.all, 'orders', search, status] as const,
  order: (id: string) => [...keys.all, 'order', id] as const,
  suppliers: (search: string, archived: boolean) => [...keys.all, 'suppliers', search, archived] as const,
  needs: () => [...keys.all, 'needs'] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  throw new Error(typeof detail === 'string' ? detail : fallback);
}

// ── Читання ────────────────────────────────────────────────────────────────

export function useOrders(search: string, status: OrderStatus | null) {
  return useQuery({
    queryKey: keys.orders(search, status),
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await procurementApi.GET('/procurement/orders', {
        params: { query: { search: search || undefined, status: status ?? undefined, limit: 100 } },
      });
      if (error) fail(error, 'Не вдалося завантажити замовлення');
      return data;
    },
  });
}

export function useOrder(orderId: string) {
  return useQuery({
    queryKey: keys.order(orderId),
    queryFn: async () => {
      const { data, error } = await procurementApi.GET('/procurement/orders/{orderId}', {
        params: { path: { orderId } },
      });
      if (error) fail(error, 'Не вдалося завантажити замовлення');
      return data;
    },
  });
}

export function useSuppliers(search = '', archived = false) {
  return useQuery({
    queryKey: keys.suppliers(search, archived),
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await procurementApi.GET('/procurement/suppliers', {
        params: { query: { search: search || undefined, archived, limit: 200 } },
      });
      if (error) fail(error, 'Не вдалося завантажити постачальників');
      return data;
    },
  });
}

export function useNeeds() {
  return useQuery({
    queryKey: keys.needs(),
    // Потреби приходять подіями від складу — список живе сам.
    refetchInterval: 30_000,
    queryFn: async () => {
      const { data, error } = await procurementApi.GET('/procurement/needs');
      if (error) fail(error, 'Не вдалося завантажити потреби');
      return data;
    },
  });
}

/** Деталь для рядка — з прайсу, через публічний API блоку catalog. */
export function usePartSearch(search: string) {
  return useQuery({
    queryKey: ['procurement', 'part-search', search],
    enabled: search.trim().length >= 1,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error } = await catalogApi.GET('/catalog/parts', {
        params: { query: { search: search.trim(), limit: 8 } },
      });
      if (error) fail(error, 'Не вдалося знайти деталь у прайсі');
      return data.items;
    },
  });
}

// ── Зміни ──────────────────────────────────────────────────────────────────

function useInvalidating<T, R>(run: (arg: T) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useCreateSupplier() {
  return useInvalidating(async (body: S['SupplierCreate']) => {
    const { data, error } = await procurementApi.POST('/procurement/suppliers', { body });
    if (error) fail(error, 'Не вдалося додати постачальника');
    return data;
  });
}

export function useUpdateSupplier() {
  return useInvalidating(async ({ id, ...body }: S['SupplierUpdate'] & { id: string }) => {
    const { data, error } = await procurementApi.PATCH('/procurement/suppliers/{supplierId}', {
      params: { path: { supplierId: id } },
      body,
    });
    if (error) fail(error, 'Не вдалося зберегти постачальника');
    return data;
  });
}

export function useCreateOrder() {
  return useInvalidating(async (body: S['OrderCreate']) => {
    const { data, error } = await procurementApi.POST('/procurement/orders', { body });
    if (error) fail(error, 'Не вдалося створити замовлення');
    return data;
  });
}

export function useUpdateOrder(orderId: string) {
  return useInvalidating(async (body: S['OrderUpdate']) => {
    const { data, error } = await procurementApi.PATCH('/procurement/orders/{orderId}', {
      params: { path: { orderId } },
      body,
    });
    if (error) fail(error, 'Не вдалося зберегти замовлення');
    return data;
  });
}

export function useChangeStatus(orderId: string) {
  return useInvalidating(async (status: S['StatusChange']['status']) => {
    const { data, error } = await procurementApi.POST('/procurement/orders/{orderId}/status', {
      params: { path: { orderId } },
      body: { status },
    });
    if (error) fail(error, 'Не вдалося змінити статус');
    return data;
  });
}

export function useAddLine(orderId: string) {
  return useInvalidating(async (body: S['LineCreate']) => {
    const { data, error } = await procurementApi.POST('/procurement/orders/{orderId}/lines', {
      params: { path: { orderId } },
      body,
    });
    if (error) fail(error, 'Не вдалося додати деталь');
    return data;
  });
}

export function useUpdateLine(orderId: string) {
  return useInvalidating(async ({ lineId, ...body }: S['LineUpdate'] & { lineId: string }) => {
    const { data, error } = await procurementApi.PATCH('/procurement/orders/{orderId}/lines/{lineId}', {
      params: { path: { orderId, lineId } },
      body,
    });
    if (error) fail(error, 'Не вдалося змінити рядок');
    return data;
  });
}

export function useRemoveLine(orderId: string) {
  return useInvalidating(async (lineId: string) => {
    const { data, error } = await procurementApi.DELETE('/procurement/orders/{orderId}/lines/{lineId}', {
      params: { path: { orderId, lineId } },
    });
    if (error) fail(error, 'Не вдалося прибрати рядок');
    return data;
  });
}

export function useReceive(orderId: string) {
  return useInvalidating(async (body: S['ReceiptCreate']) => {
    const { data, error } = await procurementApi.POST('/procurement/orders/{orderId}/receipts', {
      params: { path: { orderId } },
      body,
    });
    if (error) fail(error, 'Не вдалося оприбуткувати');
    return data;
  });
}

export function useOrderNeed() {
  return useInvalidating(async ({ partId, supplierId }: { partId: string; supplierId: string }) => {
    const { data, error } = await procurementApi.POST('/procurement/needs/{partId}/order', {
      params: { path: { partId } },
      body: { supplier_id: supplierId },
    });
    if (error) fail(error, 'Не вдалося додати в замовлення');
    return data;
  });
}

export function useDismissNeed() {
  return useInvalidating(async (partId: string) => {
    const { error } = await procurementApi.DELETE('/procurement/needs/{partId}', {
      params: { path: { partId } },
    });
    if (error) fail(error, 'Не вдалося закрити потребу');
  });
}
