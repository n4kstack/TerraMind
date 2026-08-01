import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { NAV_ITEMS } from './navigation';

/**
 * Bottom tab bar for phones.
 *
 * Chosen over a hamburger-only pattern because this audience works one-handed
 * on a phone, often outdoors: bottom-of-screen targets are reachable with a
 * thumb, top-of-screen ones are not. Four items sits inside the five-item
 * ceiling for bottom navigation.
 *
 * `pb-[env(safe-area-inset-bottom)]` keeps the targets clear of the iOS home
 * indicator; without it the last few pixels of each tab are unhittable.
 */
export function MobileTabBar() {
  return (
    <nav
      aria-label="Modules"
      className={cn(
        'fixed inset-x-0 bottom-0 z-40 lg:hidden',
        'border-t border-border bg-background/90 backdrop-blur-xl',
        'pb-[env(safe-area-inset-bottom)]',
      )}
    >
      <ul className="mx-auto flex max-w-md items-stretch justify-around">
        {NAV_ITEMS.map(({ to, shortLabel, icon: Icon }) => (
          <li key={to} className="flex-1">
            <NavLink
              to={to}
              className={({ isActive }) =>
                cn(
                  // min-h-14 keeps every tab above the 44px touch-target floor.
                  'relative flex min-h-14 flex-col items-center justify-center gap-1 px-1 py-2',
                  'text-[11px] font-semibold transition-colors duration-150',
                  isActive ? 'text-primary' : 'text-muted-foreground',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="tab-active"
                      className="absolute inset-x-3 top-0 h-0.5 rounded-full bg-primary"
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                    />
                  )}
                  <Icon className="size-5" aria-hidden="true" />
                  <span>{shortLabel}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
