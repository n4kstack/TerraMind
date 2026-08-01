import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Leaf, Menu, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { NAV_ITEMS } from './navigation';
import { ThemeToggle } from '@/components/theme/ThemeToggle';
import { Button } from '@/components/ui/Button';

function Wordmark() {
  return (
    <Link
      to="/"
      className="group flex items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      aria-label="TerraMind home"
    >
      <span className="grid size-9 place-items-center rounded-md bg-primary text-primary-foreground shadow-sm transition-transform duration-200 ease-organic group-hover:scale-105">
        <Leaf className="size-5" aria-hidden="true" />
      </span>
      <span className="text-lg font-extrabold tracking-tight text-foreground">
        Terra<span className="text-primary">Mind</span>
      </span>
    </Link>
  );
}

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    // passive: this listener never calls preventDefault, and marking it so
    // keeps scrolling off the main thread's critical path.
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Close the mobile sheet on navigation, otherwise it covers the new page.
  useEffect(() => setMobileOpen(false), [location.pathname]);

  // Lock body scroll while the sheet is open.
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  return (
    <>
      {/* Skip link: the first tab stop for keyboard users. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2.5 focus:text-sm focus:font-semibold focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <header
        className={cn(
          'sticky top-0 z-50 w-full transition-[background-color,border-color,box-shadow] duration-300',
          scrolled
            ? 'border-b border-border bg-background/85 shadow-sm backdrop-blur-xl'
            : 'border-b border-transparent bg-background/60 backdrop-blur-sm',
        )}
      >
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Wordmark />

          <div className="hidden items-center gap-1 lg:flex">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'relative flex h-11 items-center gap-2 rounded-md px-4 text-sm font-semibold',
                    'cursor-pointer transition-colors duration-150',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                    isActive ? 'text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {/* layoutId gives the indicator a shared-element slide
                        between tabs instead of a hard cut. */}
                    {isActive && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-0 -z-10 rounded-md bg-primary/10"
                        transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                      />
                    )}
                    <Icon className="size-4" aria-hidden="true" />
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </div>

          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileOpen}
              aria-controls="mobile-menu"
              onClick={() => setMobileOpen((v) => !v)}
            >
              {mobileOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
            </Button>
          </div>
        </nav>
      </header>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            id="mobile-menu"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 top-16 z-40 bg-background/95 backdrop-blur-xl lg:hidden"
          >
            <ul className="space-y-1 p-4">
              {NAV_ITEMS.map(({ to, label, icon: Icon, description }, i) => (
                <motion.li
                  key={to}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05, duration: 0.25 }}
                >
                  <NavLink
                    to={to}
                    className={({ isActive }) =>
                      cn(
                        'flex items-start gap-3 rounded-lg border p-4 transition-colors duration-150',
                        isActive
                          ? 'border-primary/30 bg-primary/10'
                          : 'border-border bg-card hover:bg-muted',
                      )
                    }
                  >
                    <span className="grid size-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block font-semibold text-foreground">{label}</span>
                      <span className="mt-0.5 block text-sm leading-snug text-muted-foreground">
                        {description}
                      </span>
                    </span>
                  </NavLink>
                </motion.li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
