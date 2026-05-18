const AUTH_TOKEN_KEY = "vinegapdetect.auth.token";
export function getStoredAuthToken(): string | null { return window.localStorage.getItem(AUTH_TOKEN_KEY); }
export function storeAuthToken(token: string): void { window.localStorage.setItem(AUTH_TOKEN_KEY, token); }
export function clearStoredAuthToken(): void { window.localStorage.removeItem(AUTH_TOKEN_KEY); }
