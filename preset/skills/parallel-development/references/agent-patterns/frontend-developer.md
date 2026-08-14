# Frontend Code Patterns

Comprehensive code patterns for Vue 3 and React development.

## Vue 3 Components

### Basic Component with Script Setup

```vue
<script setup lang="ts">
interface Props {
  title: string;
  value: string | number;
  loading?: boolean;
}

const props = defineProps<Props>();
</script>

<template>
  <el-card v-loading="loading">
    <template #header>
      <span>{{ title }}</span>
    </template>
    <div class="card-value">{{ value }}</div>
  </el-card>
</template>
```

### Vue 3 Composable

```typescript
// src/composables/useStatus.ts
import { ref, onMounted } from 'vue';
import { statusService } from '../services/status';

export function useStatus(pollInterval = 5000) {
  const status = ref<unknown>(null);
  const loading = ref(true);
  const error = ref<Error | null>(null);

  async function fetchStatus() {
    try {
      status.value = await statusService.getStatus();
    } catch (e) {
      error.value = e as Error;
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    fetchStatus();
    setInterval(fetchStatus, pollInterval);
  });

  return { status, loading, error };
}
```

## React Components

### Functional Component

```typescript
// src/components/Example.tsx
import { useState, useEffect } from 'react';

interface Props {
  id: string;
  onAction?: () => void;
}

export function Example({ id, onAction }: Props) {
  const [data, setData] = useState<unknown>(null);

  useEffect(() => {
    async function fetchData() {
      const result = await fetchDataFromStore(id);
      setData(result);
    }
    fetchData();
  }, [id]);

  if (!data) return <Loading />;

  return (
    <div className="example-container">
      <h2>{data.title}</h2>
      <button onClick={onAction}>Action</button>
    </div>
  );
}
```

### React Custom Hook

```typescript
// src/hooks/useStatus.ts
import { useQuery } from '@tanstack/react-query';
import { statusService } from '../services/status';

export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: statusService.getStatus,
    refetchInterval: 5000,
  });
}
```

## State Management

### Vue 3 + Pinia

```typescript
// src/stores/authStore.ts
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { authService } from "../services/authService";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<string | null>(null);
  const isAuthenticated = ref(false);

  async function login(username: string, password: string) {
    const result = await authService.login({ username, password });
    user.value = result.user;
    isAuthenticated.value = true;
  }

  function logout() {
    user.value = null;
    isAuthenticated.value = false;
  }

  const isLoggedIn = computed(() => isAuthenticated.value);
  return { user, isAuthenticated, isLoggedIn, login, logout };
});
```

### React + Zustand

```typescript
// src/stores/authStore.ts
import { create } from 'zustand';

interface AuthState {
  user: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  login: async (username, password) => {
    const result = await authService.login({ username, password });
    set({ isAuthenticated: true, user: result.user });
  },
  logout: () => set({ isAuthenticated: false, user: null }),
}));
```

### React + Redux Toolkit

```typescript
// src/store/authSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const login = createAsyncThunk(
  'auth/login',
  async ({ username, password }: Credentials) => {
    return await authService.login({ username, password });
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState: { user: null, isAuthenticated: false },
  reducers: {
    logout: (state) => {
      state.user = null;
      state;
    },
 .isAuthenticated = false },
  extraReducers: (builder) => {
    builder.addCase(login.fulfilled, (state, action) => {
      state.user = action.payload.user;
      state.isAuthenticated = true;
    });
  },
});
```

## Routing

### Vue 3 Router

```typescript
// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/authStore';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/', component: DashboardView, meta: { requiresAuth: true } },
  ],
});

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login');
  } else {
    next();
  }
});
```

### React Router

```typescript
// src/router/index.tsx
import { createBrowserRouter } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginView /> },
  {
    path: '/',
    element: <ProtectedRoute><DashboardView /></ProtectedRoute>,
  },
]);
```

## Testing

### Vue 3 + Vitest

```typescript
// src/components/__tests__/StatusCard.spec.ts
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import { StatusCard } from '../StatusCard';

describe('StatusCard', () => {
  it('renders title and value', () => {
    const wrapper = mount(StatusCard, {
      props: { title: 'Uptime', value: '99.9%' },
    });
    expect(wrapper.text()).toContain('Uptime');
  });
});
```

### React + Vitest

```typescript
// src/components/__tests__/StatusCard.spec.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatusCard } from '../StatusCard';

describe('StatusCard', () => {
  it('renders title and value', () => {
    render(<StatusCard title="Uptime" value="99.9%" />);
    expect(screen.getByText('Uptime')).toBeInTheDocument();
  });
});
```

### Playwright E2E

```typescript
// tests/e2e/login.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('should login successfully', async ({ page }) => {
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[type="password"]', 'password');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL('/');
  });
});
```

## Project Structure

```text
src/
├── components/        # Reusable components
│   ├── ui/           # Base UI components
│   ├── layout/       # Layout components
│   └── forms/        # Form components
├── views/ or pages/   # Page components
├── hooks/             # Custom hooks
├── stores/            # State management
├── services/          # API services
├── types/             # TypeScript types
└── utils/             # Utility functions
```

## See Also

- [memory-protocol.md](../skills/parallel-dev/references/memory-protocol.md)
