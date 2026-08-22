/**
 * Speechly Authentication Module
 * Handles user authentication with Supabase
 */

const AUTH_TOKEN_KEY = 'speechly_access_token';
const REFRESH_TOKEN_KEY = 'speechly_refresh_token';
const USER_KEY = 'speechly_user';

// Switch between sign in and sign up tabs
function switchAuthTab(tab) {
    const signinForm = document.getElementById('signinForm');
    const signupForm = document.getElementById('signupForm');
    const tabs = document.querySelectorAll('.auth-tab');

    // Clear messages
    hideError();
    hideSuccess();

    tabs.forEach(t => t.classList.remove('active'));

    if (tab === 'signin') {
        signinForm.classList.remove('hidden');
        signupForm.classList.add('hidden');
        tabs[0].classList.add('active');
    } else {
        signinForm.classList.add('hidden');
        signupForm.classList.remove('hidden');
        tabs[1].classList.add('active');
    }
}

// Toggle password visibility
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.parentElement.querySelector('.password-toggle i');

    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Show error message
function showError(message) {
    const errorEl = document.getElementById('authError');
    errorEl.textContent = message;
    errorEl.classList.add('visible');
}

// Hide error message
function hideError() {
    const errorEl = document.getElementById('authError');
    errorEl.classList.remove('visible');
}

// Show success message
function showSuccess(message) {
    const successEl = document.getElementById('authSuccess');
    successEl.textContent = message;
    successEl.classList.add('visible');
}

// Hide success message
function hideSuccess() {
    const successEl = document.getElementById('authSuccess');
    successEl.classList.remove('visible');
}

// Handle sign in form submission
async function handleSignIn(event) {
    event.preventDefault();
    hideError();
    hideSuccess();

    const email = document.getElementById('signinEmail').value;
    const password = document.getElementById('signinPassword').value;
    const btn = document.getElementById('signinBtn');

    btn.disabled = true;
    btn.textContent = 'Signing in...';

    try {
        const response = await fetch('/api/auth/signin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });

        const data = await response.json();

        if (data.success) {
            // Store tokens
            localStorage.setItem(AUTH_TOKEN_KEY, data.session.access_token);
            localStorage.setItem(REFRESH_TOKEN_KEY, data.session.refresh_token);
            localStorage.setItem(USER_KEY, JSON.stringify(data.user));

            // Redirect to main app
            window.location.href = '/';
        } else {
            showError(data.error || 'Sign in failed');
        }
    } catch (error) {
        showError('Network error. Please try again.');
        console.error('Sign in error:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Sign In';
    }
}

// Handle sign up form submission
async function handleSignUp(event) {
    event.preventDefault();
    hideError();
    hideSuccess();

    const email = document.getElementById('signupEmail').value;
    const password = document.getElementById('signupPassword').value;
    const confirmPassword = document.getElementById('signupConfirmPassword').value;
    const btn = document.getElementById('signupBtn');

    // Validate passwords match
    if (password !== confirmPassword) {
        showError('Passwords do not match');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Creating account...';

    try {
        const response = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password }),
        });

        const data = await response.json();

        if (data.success) {
            if (data.session) {
                // Auto sign in (email confirmation disabled in Supabase)
                localStorage.setItem(AUTH_TOKEN_KEY, data.session.access_token);
                localStorage.setItem(REFRESH_TOKEN_KEY, data.session.refresh_token);
                localStorage.setItem(USER_KEY, JSON.stringify(data.user));
                window.location.href = '/';
            } else {
                // Email confirmation required
                showSuccess(data.message || 'Check your email for confirmation link');
                switchAuthTab('signin');
            }
        } else {
            showError(data.error || 'Sign up failed');
        }
    } catch (error) {
        showError('Network error. Please try again.');
        console.error('Sign up error:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create Account';
    }
}

// Handle Google sign in
async function handleGoogleSignIn() {
    const btn = document.getElementById('googleBtn');
    btn.disabled = true;

    try {
        // Redirect to Google OAuth
        window.location.href = '/api/auth/oauth/google?redirect_url=' + encodeURIComponent(window.location.origin);
    } catch (error) {
        showError('Failed to initiate Google sign in');
        console.error('Google sign in error:', error);
        btn.disabled = false;
    }
}

// Check if user is already logged in
async function checkAuth() {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);

    if (token) {
        try {
            const response = await fetch('/api/auth/verify', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            const data = await response.json();

            if (data.valid) {
                // Already logged in, redirect to main app
                window.location.href = '/';
                return;
            }
        } catch (error) {
            console.error('Auth check error:', error);
        }

        // Token invalid, clear storage
        localStorage.removeItem(AUTH_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});
