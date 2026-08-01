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
 * Order matters: aurora at -z-20, growth at -z-10, content above both.
 */
export function LandingBackdrop() {
  return (
    <>
      <AuroraField />
      <GrowthScene />
    </>
  );
}
