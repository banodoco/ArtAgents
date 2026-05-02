# Task: Banodoco Resources — Media Showcase & Navigation

**Goal:** Build out the `banodoco.ai/resources` page (branch: `pr-5-art-resources` in `banodoco-website/`) into a polished, visually rich media showcase. All competition art, assets, and creator profiles should be beautifully displayed and fully interconnected — a user should be able to flow naturally between art pieces, assets, and creator profiles.

**Reference site:** The Arca Gidan competition site (`arca-gidan/`) already has a polished video viewer and asset display — reuse its patterns and ideally share the same video player component.

---

## What We're Building

### 1. Homepage (`/resources`)
A visually striking landing page that showcases the best content across three categories:

- **Art / Media** — Featured AI-generated videos and images from competitions and community submissions
- **Assets** — LoRAs, workflows, tools, and other downloadable resources  
- **Creators** — Profiles of community members who submitted work

Each section should be browsable from the homepage (hero/featured items) with a clear CTA to "see all" that takes you into the full filtered view for that category.

### 2. Art Detail Page (`/art/:slug` or `/:username/art/:slug`)
Individual page for each media piece. Should feel like a dedicated showcase:

- **Video player** — Use the `CinematicVideoPlayer` from `arca-gidan/src/components/CinematicVideoPlayer.tsx` or a shared version of it. Supports HLS (Cloudflare Stream), direct MP4 fallback, YouTube embeds, subtitles, and fullscreen
- **Metadata** — Title, description, tools used, date, competition (if applicable)
- **Creator card** — Links to their profile
- **Related assets** — If assets are linked to this media (via `asset_media` junction), show them with download links
- **Related art** — More work from the same creator, or from the same competition

### 3. Asset Detail Page (`/resources/:slug` or `/:username/resources/:slug`)
Individual page for each asset (LoRA, workflow, etc.):

- **Asset info** — Name, description, type, base model, download link
- **Preview media** — Gallery of media items linked via `asset_media` junction table, played with the shared video player
- **Creator card** — Links to their profile
- **Related assets** — Other assets from the same creator or using the same base model

### 4. Creator Profile (`/:username`)
Profile page with tabs for Art and Resources:

- **Profile header** — Avatar, display name, bio, social links (website, Instagram, Twitter)
- **Art tab** — Grid of their media pieces, each clickable to art detail
- **Resources tab** — Grid of their assets, each clickable to asset detail

### 5. Navigation Between Entities
Everything should be interconnected:
- Art detail → click creator → profile page → click another art piece → art detail
- Art detail → click linked asset → asset detail → click other media using that asset → art detail
- Homepage section → full listing → individual detail → back to listing
- Competition filter → see all entries from a specific competition

---

## Database Schema Reference

All data lives in a shared Supabase database.

**Supabase credentials:**
```
VITE_SUPABASE_URL=https://ujlwuvkrxlvoswwkerdf.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx
```

Here are the key tables and how to query them:

### Tables

**`media`** — Art pieces (videos, images)
- Key fields: `id`, `member_id`, `url`, `type`, `title`, `description`, `tools_used` (text[]), `competition_id`
- Video fields: `cloudflare_stream_id`, `cloudflare_playback_hls_url`, `cloudflare_thumbnail_url`, `backup_thumbnail_url`, `web_friendly_serving`, `subtitle_url`
- Storage: `storage_provider` ('cloudflare', 's3', 'external')

**`assets`** — Downloadable resources (LoRAs, workflows, tools)
- Key fields: `id`, `member_id`, `type`, `name`, `description`, `download_link`, `lora_link`, `lora_base_model`, `competition_id`
- Has `primary_media_id` for a hero/preview media item

**`asset_media`** — Junction table linking assets ↔ media (many-to-many)
- Fields: `asset_id`, `media_id`
- Use this to show "assets used in this art" and "art made with this asset"

**`members`** — Creator profiles
- Key fields: `member_id`, `username`, `global_name`, `avatar_url`, `stored_avatar_url`, `bio`, `real_name`, `website_url`, `instagram_url`, `twitter_url`, `banodoco_owner`
- Linked to `auth.users` via `auth_user_id`

**`competitions`** — Competition records
- Key fields: `id`, `type` ('prize'|'community'), `name`, `slug`, `status`, `theme`, `themes`
- Filter by `type = 'prize'` for Arca Gidan

**`competition_entries`** — Links members → media → competitions
- Key fields: `id`, `competition_id`, `member_id`, `media_id`, `status`, `vote_count`, `winner`, `admin_hidden`
- Use to find all media for a given competition

**`models`** / **`media_models`** / **`asset_models`** — AI model catalog and relations
- Links media and assets to the AI models they use (Flux, SDXL, etc.)

### Key Views

**`submission_details`** — Rich denormalized view of prize competition entries
- Includes: entry data, media URLs (with HLS), creator profile (as JSONB), linked assets (as JSONB array), vote counts
- Pre-filtered: only `type = 'prize'`, excludes rejected/admin-hidden entries
- **This is the easiest way to get competition entries with all related data in one query**

### Common Query Patterns

```sql
-- Get featured/curated art pieces
SELECT * FROM media 
WHERE admin_status IN ('Featured', 'Curated', 'Listed')
ORDER BY created_at DESC;

-- Get assets with their preview media
SELECT a.*, m.cloudflare_thumbnail_url, m.cloudflare_playback_hls_url 
FROM assets a
LEFT JOIN media m ON m.id = a.primary_media_id
WHERE a.admin_status IN ('Featured', 'Curated', 'Listed');

-- Get all media linked to an asset
SELECT m.* FROM media m
JOIN asset_media am ON am.media_id = m.id
WHERE am.asset_id = '<asset-uuid>';

-- Get all assets linked to a media piece
SELECT a.* FROM assets a
JOIN asset_media am ON am.asset_id = a.id
WHERE am.media_id = '<media-uuid>';

-- Get competition entries with full details
SELECT * FROM submission_details
WHERE competition_id = '<comp-uuid>';

-- Get creator profile with counts
SELECT m.*, 
  (SELECT COUNT(*) FROM media WHERE member_id = m.member_id) as art_count,
  (SELECT COUNT(*) FROM assets WHERE member_id = m.member_id) as resource_count
FROM members m WHERE m.username = '<username>';
```

---

## Existing Code to Build On

### Current Resources page structure (`banodoco-website/src/`)
```
pages/
  Resources/
    index.tsx              — Main page with hero, filters, grid
    FilterBar.tsx          — Filter controls (type, status, base model)
    ResourceGrid.tsx       — Responsive grid layout
    ResourceCard.tsx       — Individual card component
    ArtGallery/            — Art gallery section
    ArtShowcase/           — Featured art showcase
    CommunityNews/         — News feed section
    CommunityResourcesFeed/ — Community resources
  ArtDetail/index.tsx      — Single art piece page (has HlsPlayer, related art sidebar)
  ResourceDetail/index.tsx — Single resource detail page
  UserProfile/index.tsx    — Profile page with Art/Resources tabs
  SubmitArt/               — Art upload flow
  SubmitResource/          — Resource upload flow

hooks/
  useArtPieces.ts          — Paginated art query (12/page)
  useArtPiece.ts           — Single art piece by slug
  useCommunityResources.ts — Paginated resources query
  useCommunityResource.ts  — Single resource with gallery media
  useUserProfile.ts        — Profile by username with counts

lib/
  routing.ts               — Slug generation (buildArtPath, buildResourcePath, profilePath)
  supabase.ts              — Supabase client setup
```

### Routes (from `App.tsx`)
```
/resources                    → Resources page
/resources/:slug              → Resource detail
/:username/resources/:slug    → Resource detail (user-scoped)
/art/:slug                    → Art detail
/:username/art/:slug          → Art detail (user-scoped)
/:username/art                → User profile (art tab)
/:username/resources          → User profile (resources tab)
/:username                    → User profile (default: art tab)
```

### Video Player to Reuse
**`arca-gidan/src/components/CinematicVideoPlayer.tsx`**
- HLS playback via `hls.js` with MP4 fallback
- YouTube embed support
- Fullscreen, subtitles, volume control, progress bar
- Theater mode, auto-hide controls
- Buffering states with spinner + timeout
- End screen with replay/next
- Variants: `carousel`, `entry`, `list`

**Goal:** Extract this into a shared component or copy it into `banodoco-website/` so both sites use the same player.

---

## The Core Design Challenge

The technical pieces mostly exist already — the real task is making the whole thing feel like **one coherent, polished product** rather than a collection of separate pages bolted together.

Right now we have: community art, downloadable assets/resources, media from competitions, and creator profiles. These are all separate things, but a visitor landing on `/resources` should feel like they've arrived at a **substantial, curated platform** — not a patchwork of features. The experience should feel like walking into a gallery, not browsing a file manager.

### What "coherent" means here:

- **Unified visual language.** Art cards, asset cards, and profile cards should clearly belong to the same family. Shared typography, spacing rhythm, card treatments, hover states. When you click from an art piece into the creator's profile into one of their assets, it should feel like moving through rooms in the same building — not jumping between different websites.

- **Clear information hierarchy.** A first-time visitor should immediately understand: "This is a place with art, tools/assets, and the people who make them." The homepage layout needs to communicate the scope and richness of what's here without overwhelming. Featured/curated content up front, with obvious paths to go deeper.

- **Natural navigation flow.** The connections between entities (art ↔ assets ↔ creators ↔ competitions) should feel effortless. Breadcrumbs, contextual "back" links, creator attribution on every piece, asset tags on art that used them. You should never feel lost or wonder "how do I get back to where I was?"

- **The art is the hero.** Every layout decision should serve the visual content. Large thumbnails, generous whitespace, minimal UI chrome. The interface should recede and let the art speak. Think editorial/magazine, not dashboard/admin.

- **It should feel big.** Even if there are only a handful of items at first, the design should communicate that this is an established, living platform. Thoughtful empty states, consistent density, a layout that scales gracefully from 10 items to 1000. When someone lands here, the reaction should be "oh wow, there's a whole thing here" — not "oh, this looks half-finished."

### Design reference points:
- **Arca Gidan site** (`arca-gidan/`) — Already has the right visual tone for showcasing video art. Match this quality.
- **The existing magazine-style hero** on the resources page uses a scroll-driven animation. Lean into this editorial aesthetic throughout.
- **Dark theme** — Both sites use dark backgrounds which works well for showcasing visual art.
- **Responsive** — Must work beautifully on desktop and mobile. Video player must handle touch interactions.

### Specific design questions to answer:
1. How do art cards and asset cards differ visually while still feeling related? (Art is visual-first; assets are more informational with preview media)
2. What's the homepage layout? How do the sections flow? Is it a single scroll, or tabbed, or something else?
3. How does competition content integrate? Is "Arca Gidan" a filter/collection within the art section, or its own distinct area?
4. What does the transition feel like when clicking from a grid into a detail page? (Full page navigation? Expanding card? Modal?)
5. How prominent are creator profiles? Do they show up in the homepage, or only when you click through from a piece?

---

## Acceptance Criteria

### Design coherence (the main thing)
- [ ] Landing on `/resources` immediately communicates "this is a substantial, curated platform"
- [ ] Art, assets, and profiles feel like parts of one product — shared visual language, not separate features
- [ ] Navigation between entities feels natural — you never feel lost or wonder how to get back
- [ ] The art/media is always the hero — UI chrome recedes, content speaks
- [ ] The whole thing scales gracefully — looks good with 10 items or 1000

### Functional requirements
- [ ] Homepage shows featured art, assets, and creators in visually distinct but related sections
- [ ] Each section has a "see all" that goes to a filtered/paginated listing
- [ ] Art detail pages use the CinematicVideoPlayer (or equivalent) for video content
- [ ] Art detail shows linked assets (if any) with download links
- [ ] Asset detail pages show preview media gallery using the shared video player
- [ ] Creator profiles show all their art and assets in tabs
- [ ] All entities link to each other (art → creator, art → assets, asset → art, etc.)
- [ ] Competition entries can be browsed as a collection
- [ ] Mobile responsive
