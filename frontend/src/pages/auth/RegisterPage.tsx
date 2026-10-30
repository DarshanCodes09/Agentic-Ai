import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { AuthLayout } from "../../components/auth/AuthLayout";
import type { UserRole } from "../../types/api";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<UserRole>("STUDENT");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match. Please ensure both passwords are identical.");
      return;
    }

    setLoading(true);
    try {
      await register({
        full_name: fullName,
        email,
        password,
        role,
      });
      navigate("/login");
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Create Account"
      subtitle="Continue to create your dashboard account."
      footerPrompt="Already have an account?"
      footerLinkText="Sign In"
      footerLinkTo="/login"
    >
      <div className="space-y-4">
        {/* Google OAuth Button */}
        <button
          type="button"
          onClick={() =>
            setNotice(
              "Institutional Google Single Sign-On (SSO) is currently disabled for this domain. Please register using your academic email and password."
            )
          }
          className="w-full flex items-center justify-center gap-3 py-2.5 px-4 rounded-xl border border-stone-200/90 text-xs sm:text-sm font-medium text-stone-700 bg-white hover:bg-stone-50 hover:border-stone-300 transition-all focus:outline-none focus:ring-2 focus:ring-black/10 active:scale-[0.99]"
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>Sign up with Google</span>
        </button>

        {/* Divider */}
        <div className="relative my-3 flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-stone-200" />
          </div>
          <span className="relative bg-white px-3 text-[11px] font-medium tracking-wider text-stone-400 uppercase">
            or
          </span>
        </div>

        {/* Registration Form */}
        <form onSubmit={onSubmit} className="space-y-2.5 sm:space-y-3">
          {/* Role Segmented Toggle */}
          <div>
            <label className="block text-xs font-semibold text-neutral-800 mb-1">
              Account Role
            </label>
            <div className="grid grid-cols-2 p-0.5 bg-stone-100/90 rounded-xl border border-stone-200/50">
              <button
                type="button"
                onClick={() => setRole("STUDENT")}
                className={`py-1 text-xs font-semibold rounded-lg transition-all ${
                  role === "STUDENT"
                    ? "bg-white text-black shadow-xs"
                    : "text-stone-500 hover:text-black"
                }`}
              >
                Student
              </button>
              <button
                type="button"
                onClick={() => setRole("FACULTY")}
                className={`py-1 text-xs font-semibold rounded-lg transition-all ${
                  role === "FACULTY"
                    ? "bg-white text-black shadow-xs"
                    : "text-stone-500 hover:text-black"
                }`}
              >
                Faculty
              </button>
            </div>
          </div>

          {/* Full Name Field */}
          <div>
            <label
              htmlFor="fullName"
              className="block text-xs font-semibold text-neutral-800 mb-1"
            >
              Full Name
            </label>
            <input
              id="fullName"
              type="text"
              required
              minLength={2}
              placeholder="Enter your full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm text-neutral-900 bg-white border border-stone-200 rounded-xl placeholder:text-stone-400 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-colors"
            />
          </div>

          {/* Email Field */}
          <div>
            <label
              htmlFor="email"
              className="block text-xs font-semibold text-neutral-800 mb-1"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm text-neutral-900 bg-white border border-stone-200 rounded-xl placeholder:text-stone-400 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-colors"
            />
          </div>

          {/* Password Field */}
          <div>
            <label
              htmlFor="password"
              className="block text-xs font-semibold text-neutral-800 mb-1"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm text-neutral-900 bg-white border border-stone-200 rounded-xl placeholder:text-stone-400 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-colors"
            />
          </div>

          {/* Confirm Password Field */}
          <div>
            <label
              htmlFor="confirmPassword"
              className="block text-xs font-semibold text-neutral-800 mb-1"
            >
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              minLength={8}
              placeholder="Confirm your password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 text-xs sm:text-sm text-neutral-900 bg-white border border-stone-200 rounded-xl placeholder:text-stone-400 focus:outline-none focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900 transition-colors"
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-2.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 leading-relaxed">
              {error}
            </div>
          )}

          {/* Action Button: Black Pill */}
          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 sm:py-3 px-6 rounded-full bg-black text-white text-xs sm:text-sm font-semibold tracking-wide hover:bg-neutral-800 active:scale-[0.99] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </form>
      </div>

      {/* Minimal Informative Modal for SSO */}
      {notice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl border border-stone-200">
            <h3 className="text-base font-semibold text-neutral-900 mb-2">Notice</h3>
            <p className="text-xs sm:text-sm text-neutral-600 leading-relaxed mb-5">
              {notice}
            </p>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="w-full py-2.5 rounded-full bg-black text-white text-xs font-semibold hover:bg-neutral-800 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </AuthLayout>
  );
}
