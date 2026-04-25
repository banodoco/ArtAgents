-- MP2 approval request / pending intro bridge regression checks.
-- Run with psql after applying:
--   20260425090000_link_approval_requests_to_pending_intros.sql
--   20260425090001_approval_request_intro_glue.sql

\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS dblink;

-- Idempotent fixture cleanup.
DELETE FROM public.intro_votes
WHERE intro_id IN (
  SELECT id
  FROM public.pending_intros
  WHERE approval_request_id IN (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    '44444444-4444-4444-8444-444444444444',
    '55555555-5555-4555-8555-555555555555'
  )
  OR member_id IN (990000000001, 990000000002, 990000000003, 990000000004, 990000000005)
);

DELETE FROM public.pending_intros
WHERE approval_request_id IN (
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
  '55555555-5555-4555-8555-555555555555'
)
OR member_id IN (990000000001, 990000000002, 990000000003, 990000000004, 990000000005);

DELETE FROM public.approval_requests
WHERE id IN (
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
  '55555555-5555-4555-8555-555555555555'
)
OR member_id IN ('990000000001', '990000000002', '990000000003', '990000000004', '990000000005');

DELETE FROM public.assets
WHERE id IN ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1');

DELETE FROM public.media
WHERE id IN (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2'
);

DELETE FROM public.members
WHERE member_id IN (990000000001, 990000000002, 990000000003, 990000000004, 990000000005);

INSERT INTO public.members (member_id, username)
VALUES
  (990000000001, 'mp2-media-user'),
  (990000000002, 'mp2-asset-user'),
  (990000000003, 'mp2-claim-user'),
  (990000000004, 'mp2-organic-user'),
  (990000000005, 'mp2-unique-user')
ON CONFLICT (member_id) DO UPDATE
SET username = EXCLUDED.username;

INSERT INTO public.media (
  id,
  member_id,
  url,
  type,
  admin_status,
  self_attributed
)
VALUES
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0',
    990000000001,
    'https://example.com/mp2-media.webp',
    'image',
    'Hidden',
    true
  ),
  (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2',
    990000000004,
    'https://example.com/mp2-organic.webp',
    'image',
    'Hidden',
    true
  );

INSERT INTO public.assets (
  id,
  member_id,
  name,
  type,
  status,
  admin_status,
  self_attributed
)
VALUES (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
  990000000002,
  'MP2 Draft Resource',
  'workflow',
  'draft',
  NULL,
  true
);

INSERT INTO public.approval_requests (
  id,
  member_id,
  bio_snapshot,
  attached_media_id,
  attached_resource_id,
  status,
  posted_message_id,
  created_at
)
VALUES
  (
    '11111111-1111-4111-8111-111111111111',
    '990000000001',
    'Media path fixture',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0',
    NULL,
    'pending',
    NULL,
    now() - interval '4 hours'
  ),
  (
    '22222222-2222-4222-8222-222222222222',
    '990000000002',
    'Asset path fixture',
    NULL,
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
    'pending',
    NULL,
    now() - interval '3 hours'
  ),
  (
    '33333333-3333-4333-8333-333333333333',
    '990000000003',
    'Skip locked fixture',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0',
    NULL,
    'pending',
    NULL,
    timestamp with time zone '2000-01-01 00:00:00+00'
  ),
  (
    '44444444-4444-4444-8444-444444444444',
    '990000000004',
    'Organic guard fixture',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2',
    NULL,
    'pending',
    NULL,
    now() - interval '2 hours'
  ),
  (
    '55555555-5555-4555-8555-555555555555',
    '990000000005',
    'Unique constraint fixture',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0',
    NULL,
    'pending',
    NULL,
    now() - interval '1 hour'
  );

-- 1. Concurrent SKIP LOCKED claim: one open transaction locks the fixture row;
-- a second session must skip it, and it becomes reclaimable after rollback.
DO $$
DECLARE
  v_seen_first boolean;
  v_seen_second boolean;
  v_seen_after_rollback boolean;
BEGIN
  PERFORM dblink_disconnect('mp2_claim_a');
EXCEPTION
  WHEN OTHERS THEN
    NULL;
END;
$$;

SELECT dblink_connect('mp2_claim_a', 'dbname=' || current_database());
SELECT dblink_exec('mp2_claim_a', 'BEGIN');

CREATE TEMP TABLE mp2_first_claim (id uuid) ON COMMIT DROP;
INSERT INTO mp2_first_claim (id)
SELECT id
FROM dblink(
  'mp2_claim_a',
  'SELECT id FROM public.claim_pending_approval_requests(10000)'
) AS claimed(id uuid);

DO $$
DECLARE
  v_seen_first boolean;
  v_seen_second boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM mp2_first_claim WHERE id = '33333333-3333-4333-8333-333333333333'
  )
  INTO v_seen_first;

  SELECT EXISTS (
    SELECT 1
    FROM public.claim_pending_approval_requests(10000)
    WHERE id = '33333333-3333-4333-8333-333333333333'
  )
  INTO v_seen_second;

  IF NOT v_seen_first THEN
    RAISE EXCEPTION 'SKIP LOCKED setup failed: first transaction did not claim AR-C';
  END IF;

  IF v_seen_second THEN
    RAISE EXCEPTION 'SKIP LOCKED failed: second transaction saw locked AR-C';
  END IF;
END;
$$;

SELECT dblink_exec('mp2_claim_a', 'ROLLBACK');
SELECT dblink_disconnect('mp2_claim_a');

DO $$
DECLARE
  v_seen_after_rollback boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM public.claim_pending_approval_requests(10000)
    WHERE id = '33333333-3333-4333-8333-333333333333'
  )
  INTO v_seen_after_rollback;

  IF NOT v_seen_after_rollback THEN
    RAISE EXCEPTION 'SKIP LOCKED failed: AR-C was not reclaimable after rollback';
  END IF;
END;
$$;

-- 2. Trigger media path: approval flips AR-M and lists only the attached media.
INSERT INTO public.pending_intros (
  member_id,
  message_id,
  channel_id,
  guild_id,
  status,
  approval_request_id
)
VALUES (
  990000000001,
  990000000101,
  990000000201,
  990000000301,
  'pending',
  '11111111-1111-4111-8111-111111111111'
);

UPDATE public.pending_intros
SET status = 'approved'
WHERE approval_request_id = '11111111-1111-4111-8111-111111111111';

DO $$
DECLARE
  v_ar public.approval_requests%ROWTYPE;
  v_media_status text;
  v_asset_status text;
BEGIN
  SELECT * INTO v_ar
  FROM public.approval_requests
  WHERE id = '11111111-1111-4111-8111-111111111111';

  SELECT admin_status INTO v_media_status
  FROM public.media
  WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0';

  SELECT status INTO v_asset_status
  FROM public.assets
  WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1';

  IF v_ar.status <> 'approved' OR v_ar.decided_at IS NULL OR v_ar.decided_at < now() - interval '1 minute' THEN
    RAISE EXCEPTION 'media path trigger failed: approval request not approved with recent decided_at';
  END IF;

  IF v_media_status <> 'Listed' THEN
    RAISE EXCEPTION 'media path trigger failed: media admin_status is %, expected Listed', v_media_status;
  END IF;

  IF v_asset_status <> 'draft' THEN
    RAISE EXCEPTION 'media path trigger touched asset status unexpectedly: %', v_asset_status;
  END IF;
END;
$$;

-- 3. Trigger asset path: approval flips AR-A and publishes only the attached asset.
INSERT INTO public.pending_intros (
  member_id,
  message_id,
  channel_id,
  guild_id,
  status,
  approval_request_id
)
VALUES (
  990000000002,
  990000000102,
  990000000202,
  990000000302,
  'pending',
  '22222222-2222-4222-8222-222222222222'
);

UPDATE public.pending_intros
SET status = 'approved'
WHERE approval_request_id = '22222222-2222-4222-8222-222222222222';

DO $$
DECLARE
  v_ar public.approval_requests%ROWTYPE;
  v_media_status text;
  v_asset_status text;
BEGIN
  SELECT * INTO v_ar
  FROM public.approval_requests
  WHERE id = '22222222-2222-4222-8222-222222222222';

  SELECT admin_status INTO v_media_status
  FROM public.media
  WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2';

  SELECT status INTO v_asset_status
  FROM public.assets
  WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1';

  IF v_ar.status <> 'approved' OR v_ar.decided_at IS NULL OR v_ar.decided_at < now() - interval '1 minute' THEN
    RAISE EXCEPTION 'asset path trigger failed: approval request not approved with recent decided_at';
  END IF;

  IF v_asset_status <> 'published' THEN
    RAISE EXCEPTION 'asset path trigger failed: asset status is %, expected published', v_asset_status;
  END IF;

  IF v_media_status <> 'Hidden' THEN
    RAISE EXCEPTION 'asset path trigger touched unrelated media unexpectedly: %', v_media_status;
  END IF;
END;
$$;

-- 4. Organic intro regression: NULL approval_request_id must skip the trigger.
INSERT INTO public.pending_intros (
  member_id,
  message_id,
  channel_id,
  guild_id,
  status,
  approval_request_id
)
VALUES (
  990000000004,
  990000000104,
  990000000204,
  990000000304,
  'pending',
  NULL
);

UPDATE public.pending_intros
SET status = 'approved'
WHERE member_id = 990000000004
  AND message_id = 990000000104;

DO $$
DECLARE
  v_ar_status text;
  v_media_status text;
BEGIN
  SELECT status INTO v_ar_status
  FROM public.approval_requests
  WHERE id = '44444444-4444-4444-8444-444444444444';

  SELECT admin_status INTO v_media_status
  FROM public.media
  WHERE id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2';

  IF v_ar_status <> 'pending' THEN
    RAISE EXCEPTION 'organic intro guard failed: approval request status changed to %', v_ar_status;
  END IF;

  IF v_media_status <> 'Hidden' THEN
    RAISE EXCEPTION 'organic intro guard failed: media status changed to %', v_media_status;
  END IF;
END;
$$;

-- 5. Unique partial index: duplicate non-null approval_request_id must fail with 23505.
INSERT INTO public.pending_intros (
  member_id,
  message_id,
  channel_id,
  guild_id,
  status,
  approval_request_id
)
VALUES (
  990000000005,
  990000000105,
  990000000205,
  990000000305,
  'pending',
  '55555555-5555-4555-8555-555555555555'
);

DO $$
BEGIN
  INSERT INTO public.pending_intros (
    member_id,
    message_id,
    channel_id,
    guild_id,
    status,
    approval_request_id
  )
  VALUES (
    990000000005,
    990000000106,
    990000000206,
    990000000306,
    'pending',
    '55555555-5555-4555-8555-555555555555'
  );

  RAISE EXCEPTION 'unique partial index failed: duplicate approval_request_id insert succeeded';
EXCEPTION
  WHEN unique_violation THEN
    IF SQLSTATE <> '23505' THEN
      RAISE EXCEPTION 'expected SQLSTATE 23505, got %', SQLSTATE;
    END IF;
END;
$$;

-- Cleanup.
DELETE FROM public.intro_votes
WHERE intro_id IN (
  SELECT id
  FROM public.pending_intros
  WHERE approval_request_id IN (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    '44444444-4444-4444-8444-444444444444',
    '55555555-5555-4555-8555-555555555555'
  )
  OR member_id IN (990000000001, 990000000002, 990000000003, 990000000004, 990000000005)
);

DELETE FROM public.pending_intros
WHERE approval_request_id IN (
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
  '55555555-5555-4555-8555-555555555555'
)
OR member_id IN (990000000001, 990000000002, 990000000003, 990000000004, 990000000005);

DELETE FROM public.approval_requests
WHERE id IN (
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  '33333333-3333-4333-8333-333333333333',
  '44444444-4444-4444-8444-444444444444',
  '55555555-5555-4555-8555-555555555555'
)
OR member_id IN ('990000000001', '990000000002', '990000000003', '990000000004', '990000000005');

DELETE FROM public.assets
WHERE id IN ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1');

DELETE FROM public.media
WHERE id IN (
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa0',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2'
);

DELETE FROM public.members
WHERE member_id IN (990000000001, 990000000002, 990000000003, 990000000004, 990000000005);
