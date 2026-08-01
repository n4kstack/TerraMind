import { Sprout, Activity, ScanLine, Network, type LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  /** Shown in the mobile tab bar, where horizontal space is tight. */
  shortLabel: string;
  icon: LucideIcon;
  description: string;
}

/**
 * The four modules that have a working backend. Single source of truth for the
 * desktop nav, the mobile tab bar, and the landing page module grid, so they
 * can never drift out of sync.
 *
 * Deliberately excludes Weather, Farm Analytics and Authentication: those have
 * no endpoints, and shipping navigation to a dead end is worse than omitting it.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    to: '/advisor',
    label: 'Advisor',
    shortLabel: 'Advisor',
    icon: Sprout,
    description: 'Pre-sowing crop and yield recommendations from soil, climate and district history.',
  },
  {
    to: '/monitor',
    label: 'Monitor',
    shortLabel: 'Monitor',
    icon: Activity,
    description: 'In-season fertiliser dosage and pest-pressure guidance for the current growth stage.',
  },
  {
    to: '/diagnosis',
    label: 'Diagnosis',
    shortLabel: 'Diagnose',
    icon: ScanLine,
    description: 'Identify crop disease from a leaf photograph, with ranked alternatives.',
  },
  {
    to: '/augnosis',
    label: 'AugNosis',
    shortLabel: 'Ask AI',
    icon: Network,
    description: 'Ask farming questions and get answers grounded in a knowledge graph, with sources.',
  },
];
