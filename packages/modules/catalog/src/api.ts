import { catalogApi, type CatalogSchemas } from '@baymeister/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type Service = CatalogSchemas['schemas']['Service'];
export type ServiceCreate = CatalogSchemas['schemas']['ServiceCreate'];
export type ServiceUpdate = CatalogSchemas['schemas']['ServiceUpdate'];
export type Part = CatalogSchemas['schemas']['Part'];
export type PartCreate = CatalogSchemas['schemas']['PartCreate'];
export type PartUpdate = CatalogSchemas['schemas']['PartUpdate'];
export type Unit = Part['unit'];

export interface ListParams {
  search?: string;
  archived?: boolean;
  limit?: number;
  offset?: number;
}

const keys = {
  all: ['catalog'] as const,
  rate: () => [...keys.all, 'rate'] as const,
  services: (params: ListParams) => [...keys.all, 'services', params] as const,
  parts: (params: ListParams) => [...keys.all, 'parts', params] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

/** Поточна ставка. null — ще не задана (бекенд відповідає 404). */
export function useLaborRate() {
  return useQuery({
    queryKey: keys.rate(),
    queryFn: async () => {
      const { data, error, response } = await catalogApi.GET('/catalog/labor-rate');
      if (response.status === 404) return null;
      if (error) fail(error, 'Не вдалося завантажити ставку');
      return data;
    },
  });
}

export function useSetLaborRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (amount: string) => {
      const { data, error } = await catalogApi.PUT('/catalog/labor-rate', { body: { amount } });
      if (error) fail(error, 'Не вдалося змінити ставку');
      return data;
    },
    // Ставка змінює ціни всіх робіт — перечитуємо весь прайс.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useServices(params: ListParams) {
  return useQuery({
    queryKey: keys.services(params),
    queryFn: async () => {
      const { data, error } = await catalogApi.GET('/catalog/services', {
        params: { query: params },
      });
      if (error) fail(error, 'Не вдалося завантажити роботи');
      return data;
    },
  });
}

export function useSaveService(serviceId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ServiceCreate) => {
      const result = serviceId
        ? await catalogApi.PATCH('/catalog/services/{serviceId}', {
            params: { path: { serviceId } },
            body,
          })
        : await catalogApi.POST('/catalog/services', { body });
      if (result.error) fail(result.error, 'Не вдалося зберегти роботу');
      return result.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useArchiveService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (serviceId: string) => {
      const { data, error } = await catalogApi.POST('/catalog/services/{serviceId}/archive', {
        params: { path: { serviceId } },
      });
      if (error) fail(error, 'Не вдалося архівувати роботу');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useParts(params: ListParams) {
  return useQuery({
    queryKey: keys.parts(params),
    queryFn: async () => {
      const { data, error } = await catalogApi.GET('/catalog/parts', {
        params: { query: params },
      });
      if (error) fail(error, 'Не вдалося завантажити запчастини');
      return data;
    },
  });
}

export function useSavePart(partId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: PartCreate) => {
      const result = partId
        ? await catalogApi.PATCH('/catalog/parts/{partId}', {
            params: { path: { partId } },
            body,
          })
        : await catalogApi.POST('/catalog/parts', { body });
      if (result.error) fail(result.error, 'Не вдалося зберегти запчастину');
      return result.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useArchivePart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (partId: string) => {
      const { data, error } = await catalogApi.POST('/catalog/parts/{partId}/archive', {
        params: { path: { partId } },
      });
      if (error) fail(error, 'Не вдалося архівувати запчастину');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}
