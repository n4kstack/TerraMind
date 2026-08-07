import { useEffect, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { Leaf } from 'lucide-react';
import { Navbar } from './Navbar';
import { MobileTabBar } from './MobileTabBar';
import { pageVariants } from '@/lib/motion';
import { cn } from '@/lib/utils';

/**
 * `bare` swaps the rule and flat tint for a gradient that fades out upward. On
 * the landing page both drew a hard horizontal edge across the growth scene;
 * elsewhere they are the only thing separating the footer from the page.
 *
 * The gradient is not decoration. Removing the flat tint dropped the disclaimer
 * to 4.36:1 in light mode against a leaf behind it, and a flat replacement would
 * just redraw the edge we are removing. Fading to transparent leaves no seam and
 * measures 5.0:1 where the text actually sits.
 */
function Footer({ bare }: { bare?: boolean }) {
  return (
    <footer
      className={cn(
        bare
          ? 'bg-gradient-to-t from-background via-background/75 to-transparent'
          : 'border-t border-border bg-card/50',
      )}
    >
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:px-6 lg:px-8">
        <p className="flex items-center gap-2">
          <Leaf className="size-4 text-primary" aria-hidden="true" />
          <span>
            <span className="font-semibold text-foreground">TerraMind</span> — Smarter farming, every
            stage
          </span>
        </p>
        <p className="text-center sm:text-right">
          Model outputs are advisory. Verify against local agronomic guidance before acting.
        </p>
      </div>
    </footer>
  );
}

/** Route changes must reset scroll; SPAs otherwise keep the previous offset. */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  }, [pathname]);
  return null;
}

export function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const isLanding = pathname === '/';
  const reduced = useReducedMotion();

  // Under reduced motion the page renders as a plain <main>: a route
  // transition that fades from opacity 0 would leave the entire page blank if
  // the animation never completed.
  const transitionProps = reduced
    ? {}
    : { variants: pageVariants, initial: 'initial' as const, animate: 'animate' as const };

  return (
    <div className="flex min-h-dvh flex-col">
      {/* Decorative, fixed, pointer-events-none — never intercepts input.
          Skipped on the landing page, whose hero owns the full viewport and
          paints footage over every pixel this would occupy. */}
      {!isLanding && <div className="biophilic-field" aria-hidden="true" />}

      <ScrollToTop />
      <Navbar />

      <motion.main
        id="main"
        // Keying on pathname makes React remount per route so the enter
        // animation actually replays on navigation.
        key={pathname}
        {...transitionProps}
        className={
          isLanding
            ? 'flex-1'
            : // pb-24 on mobile clears the fixed bottom tab bar; without it the
              // last element of every page sits underneath it.
              'mx-auto w-full max-w-7xl flex-1 px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pb-16'
        }
      >
        {children}
      </motion.main>

      <Footer bare={isLanding} />
      {!isLanding && <MobileTabBar />}
    </div>
  );
}
