import {
  BarChart3,
  Briefcase,
  FileText,
  KanbanSquare,
  LayoutDashboard,
  Mail,
  PenLine,
  Settings,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/resume", label: "Resume", icon: FileText },
  { href: "/preferences", label: "Preferences", icon: SlidersHorizontal },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/applications", label: "Applications", icon: KanbanSquare },
  { href: "/tailoring", label: "Tailoring", icon: PenLine },
  { href: "/cover-letters", label: "Cover letters", icon: Mail },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];
