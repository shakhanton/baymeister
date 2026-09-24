import { identityApi, type IdentitySchemas } from '@baymeister/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export type User = IdentitySchemas['schemas']['User'];
export type UserCreate = IdentitySchemas['schemas']['UserCreate'];
export type UserUpdate = IdentitySchemas['schemas']['UserUpdate'];
export type RoleId = IdentitySchemas['schemas']['RoleId'];
export type Role = IdentitySchemas['schemas']['Role'];

export interface ListParams {
  search?: string;
  inactive?: boolean;
  limit?: number;
  offset?: number;
}

const keys = {
  all: ['identity'] as const,
  roles: () => [...keys.all, 'roles'] as const,
  list: (params: ListParams) => [...keys.all, 'list', params] as const,
  one: (id: string) => [...keys.all, 'one', id] as const,
};

/** Помилки бекенда приходять як {detail}. Показуємо саме detail, а не код. */
function fail(error: unknown, fallback: string): never {
  const detail = (error as { detail?: string } | undefined)?.detail;
  throw new Error(detail ?? fallback);
}

/** Ролі змінюються тільки з релізом identity — кешуємо на всю сесію. */
export function useRoles() {
  return useQuery({
    queryKey: keys.roles(),
    staleTime: Infinity,
    queryFn: async () => {
      const { data, error } = await identityApi.GET('/identity/roles');
      if (error) fail(error, 'Не вдалося завантажити ролі');
      return data;
    },
  });
}

export function useUsers(params: ListParams) {
  return useQuery({
    queryKey: keys.list(params),
    queryFn: async () => {
      const { data, error } = await identityApi.GET('/identity/users', {
        params: { query: params },
      });
      if (error) fail(error, 'Не вдалося завантажити список співробітників');
      return data;
    },
  });
}

export function useUser(userId: string) {
  return useQuery({
    queryKey: keys.one(userId),
    queryFn: async () => {
      const { data, error } = await identityApi.GET('/identity/users/{userId}', {
        params: { path: { userId } },
      });
      if (error) fail(error, 'Не вдалося завантажити співробітника');
      return data;
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: UserCreate) => {
      const { data, error } = await identityApi.POST('/identity/users', { body });
      if (error) fail(error, 'Не вдалося створити співробітника');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useUpdateUser(userId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: UserUpdate) => {
      const { data, error } = await identityApi.PATCH('/identity/users/{userId}', {
        params: { path: { userId } },
        body,
      });
      if (error) fail(error, 'Не вдалося зберегти зміни');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useSetUserActive(userId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (active: boolean) => {
      const path = active ? '/identity/users/{userId}/activate' : '/identity/users/{userId}/deactivate';
      const { data, error } = await identityApi.POST(path, {
        params: { path: { userId } },
      });
      if (error) fail(error, active ? 'Не вдалося увімкнути' : 'Не вдалося вимкнути');
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  });
}
