import { Layers, MapPin, Sparkles } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { NAV_ITEMS } from '@/components/layout/navigation';
import stateDistrictMapping from '@/data/state_district_mapping.json';

/**
 * Figures the hero quotes, derived rather than written down.
 *
 * Every number here is counted at build time from something real in this
 * repository — the bundled district map, the module list. Nothing is invented.
 * Fabricated social proof ("trusted by 10,000 farmers") would be both dishonest
 * and, for an advisory tool that influences what a smallholder spends on seed
 * and fertiliser, actively harmful to trust.
 *
 * Shared between the scrubbed hero and its reduced-motion still so the two can
 * never drift apart.
 */

const districtMap = stateDistrictMapping as Record<string, string[]>;

export const STATE_COUNT = Object.keys(districtMap).length;
export const DISTRICT_COUNT = Object.values(districtMap).reduce(
  (sum, list) => sum + list.length,
  0,
);

export interface HeroStat {
  value: string;
  label: string;
  icon: LucideIcon;
}

export const HERO_STATS: readonly HeroStat[] = [
  { value: `${STATE_COUNT}`, label: 'States & UTs covered', icon: MapPin },
  { value: `${DISTRICT_COUNT}`, label: 'Districts with local priors', icon: Layers },
  { value: `${NAV_ITEMS.length}`, label: 'Intelligence modules', icon: Sparkles },
];
