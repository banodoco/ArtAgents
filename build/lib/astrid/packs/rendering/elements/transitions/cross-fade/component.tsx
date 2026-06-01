import type {TransitionResult} from '../../_shared/contracts';

// Builtin null-pair: themes override this with real transition presentation/timing.
export default function CrossFade(): TransitionResult {
  return {presentation: null, timing: null};
}
