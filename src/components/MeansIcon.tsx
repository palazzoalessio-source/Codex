import {
  Mail,
  Database,
  Phone,
  Users,
  Globe,
  FileText,
  Cloud,
  Truck,
  Folder,
  Settings,
  MonitorCog,
} from "lucide-react";
export const meansIcons = [
  ["Mail", "Mail"],
  ["ERP", "ERP"],
  ["Database", "Database"],
  ["Phone", "Telefono"],
  ["Teams", "Teams"],
  ["Web Portal", "Portale"],
  ["letter", "Lettera"],
  ["cloud", "Cloud"],
  ["courier", "Corriere"],
  ["folder", "Cartella"],
  ["Generic", "Altro"],
] as const;
const icons = {
  Mail,
  ERP: MonitorCog,
  Database,
  Phone,
  Teams: Users,
  "Web Portal": Globe,
  letter: FileText,
  cloud: Cloud,
  courier: Truck,
  folder: Folder,
  Generic: Settings,
};
export function MeansIcon({
  kind,
  size = 24,
}: {
  kind: unknown;
  size?: number;
}) {
  const Icon = icons[String(kind) as keyof typeof icons] ?? Settings;
  return <Icon size={size} aria-hidden="true" />;
}
