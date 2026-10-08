import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await login({ email, password });
      const target = (location.state as { from?: Location })?.from?.pathname;
      navigate(target ?? (result.role === "FACULTY" ? "/faculty/dashboard" : "/student/dashboard"));
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-paper px-4 py-10">
      <section className="w-full max-w-md">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted">Academic AI</p>
        <h1 className="font-display text-5xl text-ink">Welcome back.</h1>
        <p className="mt-4 text-sm leading-6 text-muted">Sign in to review assessments, submit coursework, and understand performance with calm clarity.</p>
        <form onSubmit={onSubmit} className="mt-8 space-y-5 rounded-lg border border-line bg-white p-6 shadow-soft">
          <Field label="Email">
            <Input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          </Field>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <Button className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </Button>
          <p className="text-center text-sm text-muted">
            New here? <Link className="font-medium text-ink underline" to="/register">Create an account</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
