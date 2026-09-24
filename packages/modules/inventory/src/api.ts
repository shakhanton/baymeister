import { catalogApi, inventoryApi, type InventorySchemas } from '@baymeister/api-client';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type StockItem = InventorySchemas['schemas']['StockItem'];
export type StockDetail = InventorySchemas['schemas']['StockDetail'];
export type Movement = InventorySchemas['schemas']['Movement'];

const keys = {
  all: ['inventory'] as const,
  list: (search: string, low: boolean) => [...keys.all, 'list', search, low] as const,
  one: (id: string) => [...keys.all, 'one', id] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

export function useStock(search: string, low: boolean) {
  return useQuery({
    queryKey: keys.list(search, low),
    placeholderData: keepPreviousData,
    // Резерви й списання приходять подіями від нарядів — список живе сам.
    refetchInterval: 30_000,
    queryFn: async () => {
      const { data, error } = await inventoryApi.GET('/inventory/stock', {
        params: { query: { search: search || undefined, low, limit: 100 } },
      });
      if (error) fail(error, 'Не вдалося завантажити залишки');
      return data;
    },
  });
}

export function useStockItem(partId: string) {
  return useQuery({
    queryKey: keys.one(partId),
    refetchInterval: 30_000,
    queryFn: async () => {
      const { data, error } = await inventoryApi.GET('/inventory/stock/{partId}', {
        params: { path: { partId } },
      });
      if (error) fail(error, 'Не вдалося завантажити деталь');
      return data;
    },
  });
}

function useInvalidating<T>(run: (arg: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useReceive() {
  return useInvalidating(
    async (body: { part_id: string; qty: string; unit_cost: string; note: string | null }) => {
      const { data, error } = await inventoryApi.POST('/inventory/receipts', { body });
      if (error) fail(error, 'Не вдалося оприбуткувати');
      return data;
    },
  );
}

export function useUpdateItem(partId: string) {
  return useInvalidating(async (body: { location?: string | null; min_qty?: string }) => {
    const { data, error } = await inventoryApi.PATCH('/inventory/stock/{partId}', {
      params: { path: { partId } },
      body,
    });
    if (error) fail(error, 'Не вдалося зберегти');
    return data;
  });
}

export function useCount(partId: string) {
  return useInvalidating(async (body: { counted: string; note: string | null }) => {
    const { data, error } = await inventoryApi.POST('/inventory/stock/{partId}/count', {
      params: { path: { partId } },
      body,
    });
    if (error) fail(error, 'Не вдалося провести інвентаризацію');
    return data;
  });
}

/** Деталь для приходу — з прайсу, через публічний API блоку catalog. */
export function usePartSearch(search: string) {
  return useQuery({
    queryKey: ['inventory', 'part-search', search],
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
