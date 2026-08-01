import { AuroraField } from './AuroraField';
import { CanopyBorder } from './CanopyBorder';
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
 * Order matters: aurora at -z-20, growth and canopy at -z-10, content above
 * both. The canopy is painted after the growth scene so it hangs in front of
 * the tree's crown rather than behind it.
 */
export function LandingBackdrop() {
  return (
    <>
      <AuroraField />
      <GrowthScene />
      <CanopyBorder />
    </>
  );
}
