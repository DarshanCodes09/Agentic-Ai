import { BookOpen, FileText, GraduationCap, LayoutDashboard, LogOut, Menu, PieChart, Upload, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/Button";

const studentLinks = [
  { to: "/student/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/student/subjects", label: "Subjects", icon: BookOpen },
  { to: "/student/submissions", label: "Submissions", icon: FileText },
  { to: "/student/analytics", label: "Analytics", icon: PieChart }
];

const facultyLinks = [
  { to: "/faculty/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/faculty/subjects", label: "Subjects", icon: BookOpen },
  { to: "/faculty/analytics", label: "Analytics", icon: PieChart },
  { to: "/faculty/subjects", label: "Materials", icon: Upload }
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const links = user?.role === "FACULTY" ? facultyLinks : studentLinks;

  const sidebar = (
    <aside className="flex h-full flex-col border-r border-line bg-paper/95 px-4 py-5">
      <div className="mb-8 flex items-center gap-3 px-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-ink text-white">
          <GraduationCap className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold text-ink">Academic AI</p>
          <p className="text-xs text-muted">Assessment Portal</p>
        </div>
      </div>
      <nav className="space-y-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={`${to}-${label}`}
            to={to}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition ${
                isActive ? "bg-ink text-white" : "text-muted hover:bg-white hover:text-ink"
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto rounded-lg border border-line bg-white p-3 text-xs text-muted">
        <p className="font-medium text-ink">{user?.full_name}</p>
        <p>{user?.role}</p>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-paper">
      <div className="fixed inset-y-0 left-0 hidden w-72 lg:block">{sidebar}</div>
      {open ? (
        <div className="fixed inset-0 z-40 bg-ink/20 lg:hidden">
          <div className="h-full w-72">{sidebar}</div>
        </div>
      ) : null}
      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-line bg-paper/90 px-4 backdrop-blur md:px-8">
          <button className="focus-ring rounded-md p-2 lg:hidden" onClick={() => setOpen((value) => !value)}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="hidden text-sm text-muted lg:block">Premium academic productivity for assessment workflows</div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right text-sm md:block">
              <p className="font-medium text-ink">{user?.full_name}</p>
              <p className="text-xs text-muted">{user?.email}</p>
            </div>
            <Button
              variant="secondary"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-8 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
