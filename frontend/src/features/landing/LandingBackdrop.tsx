import { AuroraField } from './AuroraField';
import { GrowthScene } from './GrowthScene';

/**
 * The landing page's two decorative layers, composed.
 *
 * Rendered from <Layout> as a sibling of <main> rather than from inside the
 * page. Both layers are `position: fixed`, and <main> carries a transform
 * during the route-enter animation — a transformed ancestor makes `fixed`
 * resolve against that ancestor instead of the viewport, which would stretch
 * the scene over the full document height for the length of the transition.
 *
 * Order matters: aurora at -z-20, growth at -z-10, content above both. The leaf
 * canopy is NOT here — it belongs to the hero and is mounted from Landing, so
 * it scrolls away with the section it decorates instead of sitting over every
 * block of copy on the page.
 */
export function LandingBackdrop() {
  return (
    <>
      <AuroraField />
      <GrowthScene />
    </>
  );
}
