import {
  customersApi,
  schedulingApi,
  vehiclesApi,
  type SchedulingSchemas,
} from '@baymeister/api-client';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type Bay = SchedulingSchemas['schemas']['Bay'];
export type BayKind = SchedulingSchemas['schemas']['BayKind'];
export type Appointment = SchedulingSchemas['schemas']['Appointment'];
export type AppointmentCreate = SchedulingSchemas['schemas']['AppointmentCreate'];
export type AppointmentStatus = SchedulingSchemas['schemas']['AppointmentStatus'];

const keys = {
  all: ['scheduling'] as const,
  bays: () => [...keys.all, 'bays'] as const,
  day: (from: string, to: string) => [...keys.all, 'day', from, to] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

export function useBays() {
  return useQuery({
    queryKey: keys.bays(),
    queryFn: async () => {
      const { data, error } = await schedulingApi.GET('/scheduling/bays');
      if (error) fail(error, 'Не вдалося завантажити пости');
      return data;
    },
  });
}

export function useCreateBay() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { name: string; kind: BayKind; position: number }) => {
      const { data, error } = await schedulingApi.POST('/scheduling/bays', { body });
      if (error) fail(error, 'Не вдалося додати пост');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.bays() }),
  });
}

/** Записи, що перетинають день [from, to). Дошка оновлюється раз на хвилину. */
export function useDay(from: string, to: string) {
  return useQuery({
    queryKey: keys.day(from, to),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    queryFn: async () => {
      const { data, error } = await schedulingApi.GET('/scheduling/appointments', {
        params: { query: { from, to } },
      });
      if (error) fail(error, 'Не вдалося завантажити записи');
      return data;
    },
  });
}

export function useBook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AppointmentCreate) => {
      const { data, error } = await schedulingApi.POST('/scheduling/appointments', { body });
      if (error) fail(error, 'Не вдалося записати');
      return data;
    },
    // І успіх, і конфлікт — привід перечитати дошку: хтось міг щойно зайняти слот.
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useChangeStatus(appointmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (status: AppointmentStatus) => {
      const { data, error } = await schedulingApi.POST(
        '/scheduling/appointments/{appointmentId}/status',
        { params: { path: { appointmentId } }, body: { status } },
      );
      if (error) fail(error, 'Не вдалося змінити статус');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

/** Клієнти й авто — через публічні API їхніх блоків, не через код модулів. */
export function useCustomerSearch(search: string) {
  return useQuery({
    queryKey: ['scheduling', 'customer-search', search],
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

export function useCustomerVehicles(customerId: string | null) {
  return useQuery({
    queryKey: ['scheduling', 'customer-vehicles', customerId],
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
