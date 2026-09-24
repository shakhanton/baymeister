import { customersApi, vehiclesApi, type VehiclesSchemas } from '@baymeister/api-client';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type Vehicle = VehiclesSchemas['schemas']['Vehicle'];
export type VehicleCreate = VehiclesSchemas['schemas']['VehicleCreate'];
export type VehicleUpdate = VehiclesSchemas['schemas']['VehicleUpdate'];
export type MileageReading = VehiclesSchemas['schemas']['MileageReading'];

export interface ListParams {
  search?: string;
  customer_id?: string;
  archived?: boolean;
  limit?: number;
  offset?: number;
}

const keys = {
  all: ['vehicles'] as const,
  list: (params: ListParams) => [...keys.all, 'list', params] as const,
  one: (id: string) => [...keys.all, 'one', id] as const,
  mileage: (id: string) => [...keys.all, 'mileage', id] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

export function useVehicles(params: ListParams) {
  return useQuery({
    queryKey: keys.list(params),
    queryFn: async () => {
      const { data, error } = await vehiclesApi.GET('/vehicles', { params: { query: params } });
      if (error) fail(error, 'Не вдалося завантажити список автомобілів');
      return data;
    },
  });
}

export function useVehicle(vehicleId: string) {
  return useQuery({
    queryKey: keys.one(vehicleId),
    queryFn: async () => {
      const { data, error } = await vehiclesApi.GET('/vehicles/{vehicleId}', {
        params: { path: { vehicleId } },
      });
      if (error) fail(error, 'Не вдалося завантажити автомобіль');
      return data;
    },
  });
}

export function useMileage(vehicleId: string) {
  return useQuery({
    queryKey: keys.mileage(vehicleId),
    queryFn: async () => {
      const { data, error } = await vehiclesApi.GET('/vehicles/{vehicleId}/mileage', {
        params: { path: { vehicleId } },
      });
      if (error) fail(error, 'Не вдалося завантажити історію пробігу');
      return data;
    },
  });
}

export function useCreateVehicle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: VehicleCreate) => {
      const { data, error } = await vehiclesApi.POST('/vehicles', { body });
      if (error) fail(error, 'Не вдалося додати автомобіль');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateVehicle(vehicleId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: VehicleUpdate) => {
      const { data, error } = await vehiclesApi.PATCH('/vehicles/{vehicleId}', {
        params: { path: { vehicleId } },
        body,
      });
      if (error) fail(error, 'Не вдалося зберегти зміни');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useArchiveVehicle(vehicleId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const { data, error } = await vehiclesApi.POST('/vehicles/{vehicleId}/archive', {
        params: { path: { vehicleId } },
      });
      if (error) fail(error, 'Не вдалося архівувати автомобіль');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useRecordMileage(vehicleId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: { km: number; note?: string | null }) => {
      const { data, error } = await vehiclesApi.POST('/vehicles/{vehicleId}/mileage', {
        params: { path: { vehicleId } },
        body,
      });
      if (error) fail(error, 'Не вдалося записати пробіг');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

/**
 * Пошук власника. Блок читає публічний API `customers` через спільний
 * api-client — не код модуля customers. Межа між блоками — контракт.
 */
export function useCustomerSearch(search: string) {
  return useQuery({
    queryKey: ['vehicles', 'owner-search', search],
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
