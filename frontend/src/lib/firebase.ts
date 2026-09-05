import { initializeApp, getApps } from 'firebase/app';
import { 
  getAuth, 
  signInWithEmailAndPassword, 
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged,
  type User
} from 'firebase/auth';

// Firebase configuration - pulled from environment variables for security
// Set VITE_FIREBASE_* in your .env file
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyAf6kxH4ow0O8fDuDwDMJV7yvePm0P508A",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "co-penny.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "co-penny",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "co-penny.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "283095051490",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:283095051490:web:4ca8d62e782b8a653202bb",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-P6GNHSG1JS"
};

// Initialize Firebase only once
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

/**
 * Sync user with our backend after Firebase auth.
 * Backend verifies the Firebase ID Token and sets a cookie.
 */
export async function syncWithBackend(user: User, name?: string): Promise<boolean> {
  const displayName = name || user.displayName || user.email?.split('@')[0] || 'Investor';
  try {
    const idToken = await user.getIdToken();
    // Ensure auth cookie is present on client
    document.cookie = `copenny_auth=${encodeURIComponent(idToken)}; path=/; max-age=604800; SameSite=Lax`;

    const res = await fetch('/auth/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken, name: displayName }),
      credentials: 'include',
    });

    if (res.ok) {
      const data = await res.json();
      if (data.success !== false) {
        localStorage.setItem('copenny_authenticated', 'true');
        localStorage.setItem('copenny_user_id', data.user_id || user.uid);
        localStorage.setItem('copenny_user_name', data.name || displayName);
        return true;
      }
    }
    // Fallback: If backend sync had an issue, still authenticate on client since Firebase verified credentials
    localStorage.setItem('copenny_authenticated', 'true');
    localStorage.setItem('copenny_user_id', user.uid);
    localStorage.setItem('copenny_user_name', displayName);
    return true;
  } catch (e) {
    console.warn('[Auth] Backend sync network fallback:', e);
    // Graceful offline/network fallback
    localStorage.setItem('copenny_authenticated', 'true');
    localStorage.setItem('copenny_user_id', user.uid);
    localStorage.setItem('copenny_user_name', displayName);
    return true;
  }
}

export async function signInWithGoogle(): Promise<{ user: User | null; error?: string }> {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const synced = await syncWithBackend(result.user);
    if (synced) return { user: result.user };
    return { user: null, error: 'Backend sync failed' };
  } catch (e: any) {
    return { user: null, error: e.message || 'Google sign-in failed' };
  }
}

export async function signInWithEmail(email: string, password: string): Promise<{ user: User | null; error?: string }> {
  try {
    const result = await signInWithEmailAndPassword(auth, email, password);
    const synced = await syncWithBackend(result.user);
    if (synced) return { user: result.user };
    return { user: null, error: 'Backend sync failed' };
  } catch (e: any) {
    const msg = e.code === 'auth/wrong-password' || e.code === 'auth/user-not-found'
      ? 'Invalid email or password.'
      : e.code === 'auth/too-many-requests'
      ? 'Too many attempts. Try again later.'
      : e.message || 'Sign-in failed';
    return { user: null, error: msg };
  }
}

export async function registerWithEmail(email: string, password: string, name: string): Promise<{ user: User | null; error?: string }> {
  try {
    const result = await createUserWithEmailAndPassword(auth, email, password);
    const synced = await syncWithBackend(result.user, name);
    if (synced) return { user: result.user };
    return { user: null, error: 'Backend sync failed' };
  } catch (e: any) {
    const msg = e.code === 'auth/email-already-in-use'
      ? 'Email already in use. Try logging in.'
      : e.code === 'auth/weak-password'
      ? 'Password must be at least 6 characters.'
      : e.message || 'Registration failed';
    return { user: null, error: msg };
  }
}

export async function activateDemoMode(): Promise<boolean> {
  try {
    const res = await fetch('/demo/activate', { credentials: 'include' });
    const data = await res.json();
    if (data.success) {
      localStorage.setItem('copenny_authenticated', 'true');
      localStorage.setItem('copenny_user_id', data.user_id);
      localStorage.setItem('copenny_user_name', data.user_name || 'Demo Investor');
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export async function logOut(): Promise<void> {
  await signOut(auth);
  localStorage.removeItem('copenny_authenticated');
  localStorage.removeItem('copenny_user_id');
  localStorage.removeItem('copenny_user_name');
  // Clear the backend cookie by calling logout
  await fetch('/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
  window.location.href = '/landing';
}

export { onAuthStateChanged };
export type { User };
