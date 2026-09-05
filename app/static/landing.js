function openModal(type) {
  document.getElementById('authModal').classList.remove('hidden');
  document.getElementById('authModal').classList.add('flex');
  switchAuth(type);
}

function closeModal() {
  document.getElementById('authModal').classList.add('hidden');
  document.getElementById('authModal').classList.remove('flex');
}

function switchAuth(type) {
  document.getElementById('loginForm').classList.toggle('hidden', type !== 'login');
  document.getElementById('signupForm').classList.toggle('hidden', type !== 'signup');
}


/**
 * Helper to sync Firebase Auth state with we FastAPI backend
 */
async function syncWithBackend(user, idToken, name = null) {
  try {
    const response = await fetch('/auth/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id_token: idToken,
        name: name || user.displayName
      })
    });

    const data = await response.json();

    if (response.ok && data.success) {
      localStorage.setItem('copenny_authenticated', 'true');
      localStorage.setItem('copenny_user_id', data.user_id);
      localStorage.setItem('copenny_user_name', data.name || user.displayName || 'User');
      localStorage.setItem('copenny_user_email', user.email);

      return data;
    } else {
      // Backend might return detail (FastAPI) or error
      const errorMsg = data.error || data.detail || 'Backend sync failed';
      throw new Error(errorMsg);
    }
  } catch (err) {
    console.error('Sync error:', err);
    throw err;
  }
}

async function handleGoogleLogin() {
  if (!window.firebaseAuth) {
    alert('Firebase is not yet initialized. Please check your configuration in landing.html.');
    return;
  }

  const { auth, GoogleAuthProvider, signInWithPopup } = window.firebaseAuth;
  const provider = new GoogleAuthProvider();

  try {
    const result = await signInWithPopup(auth, provider);
    const idToken = await result.user.getIdToken();

    const syncData = await syncWithBackend(result.user, idToken);

    // Redirect to dashboard
    window.location.href = '/ui';
  } catch (error) {
    console.error('Google Login Error:', error);
    if (error.code !== 'auth/popup-closed-by-user') {
      alert('Google Sign-In failed: ' + error.message);
    }
  }
}

async function handleLogin() {
  if (!window.firebaseAuth) {
    alert('Firebase is not yet initialized.');
    return;
  }

  const { auth, signInWithEmailAndPassword, createUserWithEmailAndPassword } = window.firebaseAuth;

  const loginForm = document.getElementById('loginForm');
  const isLogin = !loginForm.classList.contains('hidden');

  const emailId = isLogin ? 'loginEmail' : 'signupEmail';
  const passId = isLogin ? 'loginPass' : 'signupPass';
  const nameId = 'signupName';

  const email = document.getElementById(emailId).value.trim();
  const password = document.getElementById(passId).value.trim();
  const name = isLogin ? '' : document.getElementById(nameId).value.trim();

  const errorDivId = isLogin ? 'loginError' : 'signupError';
  const errorDiv = document.getElementById(errorDivId);
  
  if (errorDiv) {
    errorDiv.classList.add('hidden');
    errorDiv.innerText = '';
  }

  if (!email || !password) {
    if (errorDiv) {
      errorDiv.innerText = 'Please fill in all fields.';
      errorDiv.classList.remove('hidden');
    } else {
      alert('Please fill in all fields.');
    }
    return;
  }

  try {
    let userCredential;
    if (isLogin) {
      userCredential = await signInWithEmailAndPassword(auth, email, password);
    } else {
      if (!name) { 
        if (errorDiv) {
          errorDiv.innerText = 'Please enter your name.';
          errorDiv.classList.remove('hidden');
        } else {
          alert('Please enter your name.');
        }
        return; 
      }
      userCredential = await createUserWithEmailAndPassword(auth, email, password);
    }

    const idToken = await userCredential.user.getIdToken();
    const syncData = await syncWithBackend(userCredential.user, idToken, name);

    if (isLogin) {
      window.location.href = '/ui';
    } else {
      closeModal();
      showPlanModal();
    }
  } catch (error) {
    console.error('Auth Error:', error);
    let msg = error.message;
    if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password' || error.code === 'auth/invalid-credential') {
      msg = 'Invalid email or password.';
    } else if (error.code === 'auth/email-already-in-use') {
      msg = 'An account with this email already exists.';
    } else if (msg.includes('Firebase token')) {
      msg = 'Backend authentication failed. Please try again.';
    }

    if (errorDiv) {
      errorDiv.innerText = msg;
      errorDiv.classList.remove('hidden');
    } else {
      alert(msg);
    }
  }
}

function showPlanModal() {
  const modal = document.getElementById('planModal');
  if (modal) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
}

async function selectPlan(tier) {
  const userId = localStorage.getItem('copenny_user_id');
  if (!userId) return;

  try {
    const response = await fetch('/subscription/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        tier: tier,
        months: 1
      })
    });

    const data = await response.json();
    if (data.success) {
      localStorage.setItem('copenny_user_tier', tier);
      window.location.href = '/ui';
    } else {
      alert('Error selecting plan: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    console.error('Plan selection error:', err);
    alert('Failed to save plan selection.');
  }
}

function enterDashboard() {
  // Always attempt to go to the UI, the backend will redirect if not authorized
  window.location.href = '/ui';
}

async function activateDemoAndEnter() {
  try {
    const res = await fetch('/demo/activate');
    const data = await res.json();
    if (data.success) {
      localStorage.setItem('copenny_authenticated', 'true');
      localStorage.setItem('copenny_user_id', data.user_id);
      localStorage.setItem('copenny_user_name', data.user_name || 'Demo Investor');
    }
  } catch (e) {
    // Even if activate call fails, fallback gracefully
    localStorage.setItem('copenny_authenticated', 'true');
    localStorage.setItem('copenny_user_id', 'demo_user');
    localStorage.setItem('copenny_user_name', 'Demo Investor');
  }
  window.location.href = '/ui';
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {

  const authModal = document.getElementById('authModal');
  if (authModal) {
    authModal.addEventListener('click', (e) => {
      if (e.target === authModal) closeModal();
    });
  }

  // Handle errors from backend redirects
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('error') === 'unauthorized') {
    openModal('login');
  }
});
