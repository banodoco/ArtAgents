-- Flag curated assets from Arca Gidan Ed 2 for The Forge section on /2RP.
--
-- Source: public.competition_entries for competition_id
--   '8c1bcdf1-c8ef-4c7e-83c1-091b68e9ca4c' (Arca Gidan Ed 2),
-- excluding status='draft' and admin_hidden=true.
--
-- Ranking signal: public.public_vote_counts.avg_score (DESC), tie-broken
-- by score_count (DESC) then prize_tier (apex > crest > ridge > null).
-- Floor applied: score_count >= 20 (all 95 eligible entries satisfy this;
-- the smallest score_count in Ed 2 was 35, so the floor only exists to
-- guard against fluke single-voter entries on future re-runs).
--
-- Selection: walk eligible entries top-to-bottom, pull each entry's
-- submission_details.assets JSONB array, resolve each asset.id against
-- public.assets, drop rows with empty/null name or missing from assets,
-- de-duplicate (first occurrence wins), stop at 25 unique asset IDs.
--
-- Depends on: 20260419120000_add_featured_in_forge_flag.sql (adds the
-- featured_in_forge column).
--
-- Intentionally does NOT touch admin_status. The Forge hook should
-- rely on featured_in_forge alone for this curated subset.

UPDATE public.assets
SET featured_in_forge = TRUE
WHERE id IN (
    'eb495d16-adf6-489b-83fb-46df05aa9602',  -- rank 1: Wan first frame last frame (avg_score=7.51, score_count=128, prize_tier=apex)
    '7aba126c-d4a4-4eb0-8d1d-38f9ca478ef4',  -- rank 2: Qwen Image edit (avg_score=7.51, score_count=128, prize_tier=apex)
    '4fc8571a-224a-4143-9081-c07fa747858a',  -- rank 3: Image to Video - LTX 2.3 (avg_score=7.51, score_count=128, prize_tier=apex)
    'c7fd8e3d-82f6-4017-aae1-c3a0220da11b',  -- rank 4: WanAnimate - Input Video + Random Image (avg_score=7.47, score_count=162, prize_tier=apex)
    '62646884-fe02-44f6-a24b-76c2ff96ecb1',  -- rank 5: BiRefNet_AutoMask (avg_score=7.47, score_count=162, prize_tier=apex)
    '0d55592c-7ad8-44db-ab49-cfddf40c6102',  -- rank 6: Z-Image Turbo + LTX-2.3 I2V+A + Auto Music Sequencer (avg_score=7.47, score_count=162, prize_tier=apex)
    '5db49ad1-783c-4efd-970c-f3963acbf567',  -- rank 7: ZIT + LTX I2V+A + Music Sequencer_BASIC (avg_score=7.47, score_count=162, prize_tier=apex)
    'd2b2d584-79c9-4e12-8876-533e9e140d54',  -- rank 8: First frame,Middle Frame,Last Frame LTX2.3 by RuneXX (avg_score=7.37, score_count=189, prize_tier=ridge)
    '103d9211-8fbc-4d46-adae-5ca35b38a385',  -- rank 9: first/last frame ltx (avg_score=7.35, score_count=106, prize_tier=none)
    'acfe7381-c3aa-4623-b326-07fbade93f36',  -- rank 10: Z-image Turbo flow (avg_score=7.35, score_count=106, prize_tier=none)
    'be9c92af-87d3-4133-a148-a55c3f8cf5d1',  -- rank 11: Z-image Turbo Comfy workflow (avg_score=7.35, score_count=106, prize_tier=none)
    '7433a455-dc09-4456-a51c-214a6d1c7fcd',  -- rank 12: image to video wan (avg_score=7.35, score_count=106, prize_tier=none)
    '57fb9413-9dd6-4614-b7ba-f58ed1cb81af',  -- rank 13: first/last frame ltx (avg_score=7.35, score_count=106, prize_tier=none)
    '615b7bc6-ec84-4449-9b36-13a73f2d9ebc',  -- rank 14: Wan image to video workflow (avg_score=7.35, score_count=106, prize_tier=none)
    '0827bf5c-0f66-4481-92c6-63c947485c9c',  -- rank 15: image to video ltx (avg_score=7.35, score_count=106, prize_tier=none)
    'f162cce9-135c-48b0-b50d-7e8fae28543a',  -- rank 16: LTX 2.3 image to video workflow (avg_score=7.35, score_count=106, prize_tier=none)
    'f0c33232-2ce2-4cb9-b929-7b92e92d5347',  -- rank 17: image to video wan (avg_score=7.35, score_count=106, prize_tier=none)
    'aec84405-1eb5-4af9-b5b2-ae35aa2cb3a7',  -- rank 18: LTX 2,3 First/Last frame workflow (avg_score=7.35, score_count=106, prize_tier=none)
    '8b259e80-2b09-47ea-886a-0d1740c1f24a',  -- rank 19: Tutorial for general Music Video from me on reddit. (avg_score=7.08, score_count=111, prize_tier=crest)
    'f218b8fb-50c4-4d4b-852f-72c2bc99ee03',  -- rank 20: LTX 2.3 Img2Video + Lipsync (avg_score=7.08, score_count=111, prize_tier=crest)
    'd253867e-12a0-4616-884f-55947132d621',  -- rank 21: LTX 2.3 Img2Video from  Benji’s AI (avg_score=7.08, score_count=111, prize_tier=crest)
    'e1871894-4ab5-4eca-b995-ff22edbe086a',  -- rank 22: Anima Workflow (avg_score=7.08, score_count=111, prize_tier=crest)
    '8e27db40-de01-4f62-ae19-8c6671195445',  -- rank 23: How I did it. (avg_score=7.08, score_count=111, prize_tier=crest)
    'dbd8a763-31d5-4df2-b0f3-91edb19a3583',  -- rank 24: WAN2.2-I2I_Workflow_Herbst (avg_score=7.06, score_count=144, prize_tier=apex)
    '6012c743-c423-4707-864b-b549c6adf792'  -- rank 25: Flux_Klein-9b_base_I2I_Calvin_Herbst (avg_score=7.06, score_count=144, prize_tier=apex)
);
