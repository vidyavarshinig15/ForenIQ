export type NavigationTab =
  | 'dashboard'
  | 'cases'
  | 'evidence'
  | 'investigations'
  | 'search'
  | 'timeline'
  | 'graph'
  | 'anomalies'
  | 'reports'
  | 'audit'
  | 'settings';

export interface NavigationItem {
  id: NavigationTab;
  label: string;
  category: 'Core' | 'Forensic Analysis' | 'Governance';
  description: string;
  plannedPhase: string;
}
