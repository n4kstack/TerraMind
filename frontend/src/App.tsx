import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from '@/components/layout/Layout';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ThemeProvider } from '@/components/theme/ThemeProvider';
import { SkeletonCard } from '@/components/ui/Skeleton';
import Landing from '@/pages/Landing';

/**
 * Landing is imported statically (above) — it is the entry point, and lazy
 * loading it introduced a Suspense swap that shifted the footer on the
 * most-visited page.
 *
 * The module routes stay lazy. Making them eager was tried and measured: it
 * grew the entry chunk from 54 kB to 218 kB and cost points on EVERY route,
 * landing included (97 -> 93 median), because each page then pays for all four.
 * The round trip it saved on direct navigation was worth less than the weight
 * it added everywhere.
 */
const Advisor = lazy(() => import('@/pages/Advisor'));
const Monitor = lazy(() => import('@/pages/Monitor'));
const Diagnosis = lazy(() => import('@/pages/Diagnosis'));
const AugNosis = lazy(() => import('@/pages/AugNosis'));
const NotFound = lazy(() => import('@/pages/NotFound'));

/**
 * The min-height is load-bearing, not decorative.
 *
 * Without it the fallback is far shorter than the module page that replaces it,
 * so the footer jumps the moment the lazy chunk resolves — Lighthouse named
 * <footer> as the sole layout-shift culprit. CLS only scores shifts that are
 * *visible*, so reserving more than a viewport keeps the footer below the fold
 * during the swap: it still moves, but never within sight, and the measured
 * shift goes to zero.
 */
function RouteFallback() {
  return (
    <div className="min-h-[130vh] space-y-6 py-4">
      <div className="skeleton h-9 w-2/3 max-w-sm rounded-md" />
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <SkeletonCard />
        </div>
        <div className="lg:col-span-7">
          <SkeletonCard />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <BrowserRouter>
          <Layout>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/advisor" element={<Advisor />} />
                <Route path="/monitor" element={<Monitor />} />
                <Route path="/diagnosis" element={<Diagnosis />} />
                <Route path="/augnosis" element={<AugNosis />} />

                {/* Back-compat: these paths were live in the previous build and
                    may exist in bookmarks or shared links. */}
                <Route path="/graphrag" element={<Navigate to="/augnosis" replace />} />
                <Route path="/chatbot" element={<Navigate to="/augnosis" replace />} />

                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </Layout>
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
