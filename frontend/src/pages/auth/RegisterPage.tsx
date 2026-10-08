import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getApiErrorMessage } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Field, Input, Select } from "../../components/ui/Input";
import { useAuth } from "../../context/AuthContext";
import type { UserRole } from "../../types/api";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "STUDENT" as UserRole });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await register(form);
      navigate("/login");
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-paper px-4 py-10">
      <section className="w-full max-w-md">
        <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted">Join the portal</p>
        <h1 className="font-display text-5xl text-ink">Create account.</h1>
        <form onSubmit={onSubmit} className="mt-8 space-y-5 rounded-lg border border-line bg-white p-6 shadow-soft">
          <Field label="Full name"><Input required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Email"><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Password" hint="Use at least 8 characters with uppercase, lowercase, and a number."><Input type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <Field label="Role">
            <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
              <option value="STUDENT">Student</option>
              <option value="FACULTY">Faculty</option>
            </Select>
          </Field>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <Button className="w-full" disabled={loading}>{loading ? "Creating..." : "Create account"}</Button>
          <p className="text-center text-sm text-muted">
            Already registered? <Link className="font-medium text-ink underline" to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
