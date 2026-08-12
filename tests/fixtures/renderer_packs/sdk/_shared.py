#!/usr/bin/env python3
"""Shared canonical logic for the ``sdk`` conformance pack (T6.4).

This module is the SAME logic behind both thin wrappers in this pack:

* ``render.py`` — raw-command backend: parses argv, delegates the verb here,
  and writes the authoritative ``--result`` JSON. Pure stdlib: it never
  imports the Astrid SDK and never touches the Astrid ledger.
* ``sdk_render.py`` — SDK backend: delegates the whole protocol to
  ``astrid.sdk.rendering.renderer_main`` (T6.2 shared contract), which
  implements the identical wire behavior through the public SDK/core DTOs.

The conformance harness
(``tests/core/rendering/test_conformance.py``) drives both backends through
:class:`CommandTransport` and asserts the emitted result/support JSON is
semantically identical: same keys, same normalized values, matching hashes and
profile values.

Wire contract implemented here (frozen render-backend-v1):

* ``support`` writes a ``SupportReport``-shaped result. The decision is
  request-sensitive: supported only for the specific combination
  ``window == [0, 48) @ 24fps`` with ``audio`` in {rendered, passthrough,
  none} and a profile that matches the fixed output when supplied.
* ``render`` writes a deterministic MP4 (H.264 baseline video + PCM audio for
  ``rendered``; visual-only for ``passthrough``/``none``) plus a
  ``RenderResult``-shaped result whose sha256 is the real digest of the file.
  A request for an invalid output name produces a structured
  ``RendererError`` (kind ``protocol``).
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

BACKEND_ID = "sdk.renderer"
BACKEND_VERSION = "1.0.0"

# Deterministic media constants. The container timing (time_base 1/12288,
# 512 ticks per frame at 24fps) matches the committed request fixtures and
# the raw_command fixture pack so both fixtures stay cross-comparable.
WIDTH = 1920
HEIGHT = 1080
FPS_RATIONAL = [24, 1]
TIME_BASE = [1, 12288]
SAMPLES_PER_FRAME = 512
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_BITS = 16
CONTAINER = "mp4"
VIDEO_CODEC = "h264"
PIXEL_FORMAT = "yuv420p"
AUDIO_CODEC = "pcm_s16le"
AUDIO_CHANNEL_LAYOUT = "stereo"

# Request-sensitive support contract: the backend commits only to this
# window/audio combination in its support report.
SUPPORTED_WINDOW_FRAMES = 48
SUPPORTED_AUDIO_MODES = ("rendered", "passthrough", "none")

_MB_COLS = WIDTH // 16          # 120
_MB_ROWS = (HEIGHT + 15) // 16  # 68  -> 1088 coded lines, 8 cropped
_MB_COUNT = _MB_COLS * _MB_ROWS  # 8160

_MATRIX = struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)

_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Attachment emitted for the named-byte-payload conformance case.
ATTACHMENT_NAME = "sdk_manifest.json"
ATTACHMENT_KIND = "json"
ATTACHMENT_CONTENT = (
    json.dumps(
        {
            "fixture": "sdk",
            "attachment": "manifest",
            "generator": BACKEND_ID,
            "bytes": 32,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
).encode("utf-8")


# ---------------------------------------------------------------------------
# Bit-level H.264 (baseline, all-IDR) construction (same encoder as the
# raw_command fixture so both fixtures produce cross-comparable media)
# ---------------------------------------------------------------------------


class _BitWriter:
    """Tiny MSB-first bit writer over a bytearray."""

    __slots__ = ("data", "acc", "nbits")

    def __init__(self) -> None:
        self.data = bytearray()
        self.acc = 0
        self.nbits = 0

    def put(self, value: int, count: int) -> None:
        for shift in range(count - 1, -1, -1):
            self.acc = (self.acc << 1) | ((value >> shift) & 1)
            self.nbits += 1
            if self.nbits == 8:
                self.data.append(self.acc)
                self.acc = 0
                self.nbits = 0

    def finish(self) -> None:
        """Append rbsp_trailing_bits: a single 1 bit plus zero padding."""
        if self.nbits:
            self.data.append((self.acc << (8 - self.nbits)) | (1 << (7 - self.nbits)))
        else:
            self.data.append(0x80)
        self.acc = 0
        self.nbits = 0


def _ue(writer: _BitWriter, value: int) -> None:
    """Exp-Golomb unsigned code."""
    code_num = value + 1
    n = code_num.bit_length()
    writer.put(0, n - 1)
    writer.put(code_num, n)


def _se(writer: _BitWriter, value: int) -> None:
    """Exp-Golomb signed code."""
    _ue(writer, -2 * value if value <= 0 else 2 * value - 1)


def _escape_rbsp(data: bytes) -> bytes:
    """Insert emulation-prevention 0x03 bytes after 00 00 [<=03]."""
    out = bytearray()
    zeros = 0
    for byte in data:
        if zeros >= 2 and byte <= 3:
            out.append(3)
            zeros = 0
        out.append(byte)
        zeros = zeros + 1 if byte == 0 else 0
    return bytes(out)


def _sps_nal() -> bytes:
    """Sequence parameter set for baseline 1920x1080 @ level 4.0."""
    w = _BitWriter()
    w.put(66, 8)            # profile_idc = baseline
    w.put(0xC0, 8)          # constraint_set0|set1
    w.put(40, 8)            # level_idc = 4.0
    _ue(w, 0)               # seq_parameter_set_id
    _ue(w, 0)               # log2_max_frame_num_minus4 -> 4-bit frame_num
    _ue(w, 0)               # pic_order_cnt_type = 0
    _ue(w, 4)               # log2_max_pic_order_cnt_lsb_minus4 -> 8-bit POC lsb
    _ue(w, 1)               # max_num_ref_frames
    w.put(0, 1)             # gaps_in_frame_num_value_allowed_flag
    _ue(w, _MB_COLS - 1)    # pic_width_in_mbs_minus1
    _ue(w, _MB_ROWS - 1)    # pic_height_in_map_units_minus1
    w.put(1, 1)             # frame_mbs_only_flag
    w.put(1, 1)             # direct_8x8_inference_flag
    w.put(1, 1)             # frame_cropping_flag
    _ue(w, 0)               # frame_crop_left_offset
    _ue(w, 0)               # frame_crop_right_offset
    _ue(w, 0)               # frame_crop_top_offset
    _ue(w, 4)               # frame_crop_bottom_offset (1088 - 8 = 1080)
    w.put(0, 1)             # vui_parameters_present_flag
    w.finish()
    return bytes([0x67]) + _escape_rbsp(bytes(w.data))


def _pps_nal() -> bytes:
    """Picture parameter set (CAVLC, single slice group)."""
    w = _BitWriter()
    _ue(w, 0)               # pic_parameter_set_id
    _ue(w, 0)               # seq_parameter_set_id
    w.put(0, 1)             # entropy_coding_mode_flag (CAVLC)
    w.put(0, 1)             # bottom_field_pic_order_in_frame_present_flag
    _ue(w, 0)               # num_slice_groups_minus1
    _ue(w, 0)               # num_ref_idx_l0_default_active_minus1
    _ue(w, 0)               # num_ref_idx_l1_default_active_minus1
    w.put(0, 1)             # weighted_pred_flag
    w.put(0, 2)             # weighted_bipred_idc
    _se(w, 0)               # pic_init_qp_minus26
    _se(w, 0)               # pic_init_qs_minus26
    _se(w, 0)               # chroma_qp_index_offset
    w.put(0, 1)             # deblocking_filter_control_present_flag
    w.put(0, 1)             # constrained_intra_pred_flag
    w.put(0, 1)             # redundant_pic_cnt_present_flag
    w.finish()
    return bytes([0x68]) + _escape_rbsp(bytes(w.data))


def _idr_slice_nal(frame_index: int) -> bytes:
    """One IDR I-frame: every macroblock is I_16x16_2_0_0 with no residual.

    With CodedBlockPatternLuma/Chroma = 0 the decoder reconstructs each 16x16
    block from DC prediction (unavailable neighbours default to 128), so the
    whole frame decodes to a deterministic solid color.
    """
    w = _BitWriter()
    _ue(w, 0)               # first_mb_in_slice
    _ue(w, 2)               # slice_type = I (2)
    _ue(w, 0)               # pic_parameter_set_id
    w.put(0, 4)             # frame_num (IDR pictures use 0)
    _ue(w, 0)               # idr_pic_id
    w.put((2 * frame_index) & 0xFF, 8)  # pic_order_cnt_lsb (POC grows by 2/frame)
    w.put(0, 1)             # no_output_of_prior_pics_flag
    w.put(0, 1)             # long_term_reference_flag
    _se(w, 0)               # slice_qp_delta
    for _ in range(_MB_COUNT):
        w.put(0b001001, 6)  # mb_type=3 (I_16x16_2_0_0) + intra_chroma_pred_mode=0
    w.finish()
    return bytes([0x65]) + _escape_rbsp(bytes(w.data))


# ---------------------------------------------------------------------------
# Minimal ISO BMFF (MP4) muxer
# ---------------------------------------------------------------------------


def _box(box_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), box_type) + payload


def _fullbox(box_type: bytes, version_flags: int, payload: bytes) -> bytes:
    return struct.pack(">I4sI", 12 + len(payload), box_type, version_flags) + payload


def _matrix() -> bytes:
    return _MATRIX


def _ftyp() -> bytes:
    return (
        struct.pack(">I4sII", 32, b"ftyp", 0x69736F6D, 0x00000200)
        + b"isomiso2avc1mp41"
    )


def _mvhd(duration: int, next_track_id: int) -> bytes:
    payload = (
        struct.pack(">IIII", 0, 0, 12288, duration)  # timescale = 12288
        + struct.pack(">I", 0x00010000)              # rate 1.0
        + struct.pack(">H", 0x0100)                  # volume 1.0
        + struct.pack(">H", 0)
        + struct.pack(">II", 0, 0)
        + _matrix()
        + b"\x00" * 24
        + struct.pack(">I", next_track_id)
    )
    return _fullbox(b"mvhd", 0, payload)


def _tkhd(track_id: int, duration: int, volume: int, width: int, height: int) -> bytes:
    payload = (
        struct.pack(">II", 0, 0)
        + struct.pack(">I", track_id)
        + struct.pack(">I", 0)
        + struct.pack(">I", duration)
        + struct.pack(">II", 0, 0)
        + struct.pack(">Hh", 0, 0)
        + struct.pack(">H", volume)
        + struct.pack(">H", 0)
        + _matrix()
        + struct.pack(">II", width << 16, height << 16)
    )
    return _fullbox(b"tkhd", 0x00000007, payload)


def _mdhd(timescale: int, duration: int) -> bytes:
    payload = (
        struct.pack(">IIII", 0, 0, timescale, duration)
        + struct.pack(">HH", 0x55C4, 0)  # language "und"
    )
    return _fullbox(b"mdhd", 0, payload)


def _hdlr(handler: bytes, name: bytes) -> bytes:
    payload = struct.pack(">I", 0) + handler + b"\x00" * 12 + name + b"\x00"
    return _fullbox(b"hdlr", 0, payload)


def _dinf() -> bytes:
    dref = _fullbox(b"dref", 0, struct.pack(">I", 1) + _fullbox(b"url ", 1, b""))
    return _box(b"dinf", dref)


def _avc1_entry(sps: bytes, pps: bytes) -> bytes:
    avcc = (
        bytes([1, 66, 0xC0, 40, 0xFF, 0xE1])
        + struct.pack(">H", len(sps))
        + sps
        + bytes([1])
        + struct.pack(">H", len(pps))
        + pps
    )
    visual = (
        b"\x00" * 6
        + struct.pack(">H", 1)             # data_reference_index
        + struct.pack(">HH", 0, 0)
        + b"\x00" * 12
        + struct.pack(">HH", WIDTH, HEIGHT)
        + struct.pack(">II", 0x00480000, 0x00480000)  # 72 dpi
        + struct.pack(">I", 0)
        + struct.pack(">H", 1)             # frame_count
        + b"SDKFixture\x00" + b"\x00" * 21  # compressorname (32 bytes)
        + struct.pack(">Hh", 24, -1)       # depth 24, pre_defined -1
    )
    return _box(b"avc1", visual + _box(b"avcC", avcc))


def _sowt_entry() -> bytes:
    # Canonical QuickTime channel layout atom (FFmpeg movenc format):
    # version(2) + revision(2) + layout_tag(4) + bitmap(4) +
    # num_descriptions(4). Stereo layout tag = 0x00650002.
    chan = _box(
        b"chan",
        struct.pack(">H", 0)   # version
        + struct.pack(">H", 0)  # revision
        + struct.pack(">I", 0x00650002 if AUDIO_CHANNELS == 2 else 0x00650000)
        + struct.pack(">I", 0)  # bitmap (kAudioChannelBit_None)
        + struct.pack(">I", 0),  # num channel descriptions
    )
    wave = _box(
        b"wave",
        _box(b"frma", b"sowt")
        + _box(b"enda", struct.pack(">H", 1))
        + chan,
    )
    audio = (
        b"\x00" * 6
        + struct.pack(">H", 1)             # data_reference_index
        + struct.pack(">HH", 0, 0)
        + struct.pack(">I", 0)             # vendor
        + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
        + struct.pack(">HH", 0, 0)         # compressionid, packetsize
        + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
    )
    return _box(b"sowt", audio + wave)


def _sample_tables(
    *,
    video_frames: int,
    video_sizes: list[int],
    video_chunk_offset: int,
    audio_bytes: bytes | None,
    audio_samples: int,
    audio_chunk_offset: int,
) -> tuple[bytes, bytes | None]:
    stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
    stts_v = _fullbox(
        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", video_frames, SAMPLES_PER_FRAME)
    )
    stsc_v = _fullbox(
        b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, video_frames, 1)
    )
    stsz_v = _fullbox(
        b"stsz", 0, struct.pack(">II", 0, video_frames)
        + b"".join(struct.pack(">I", size) for size in video_sizes)
    )
    stco_v = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", video_chunk_offset))

    video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
    if audio_bytes is None:
        return video_stbl, None

    stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
    stts_a = _fullbox(
        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
    )
    stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
    stsz_a = _fullbox(
        b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
    )
    stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))

    audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
    return video_stbl, audio_stbl


def build_mp4(frames: int, *, with_audio: bool) -> bytes:
    """Return a deterministic MP4: `frames` H.264 IDR frames (+ PCM silence)."""
    video_chunk = bytearray()
    video_sizes: list[int] = []
    for frame_index in range(frames):
        nal = _idr_slice_nal(frame_index)
        sample = struct.pack(">I", len(nal)) + nal
        video_chunk += sample
        video_sizes.append(len(sample))
    video_chunk = bytes(video_chunk)

    audio_bytes: bytes | None = None
    if with_audio:
        audio_samples = frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])
        audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))

    ftyp = _ftyp()
    video_chunk_offset = len(ftyp) + 8
    audio_chunk_offset = video_chunk_offset + len(video_chunk)

    video_stbl, audio_stbl = _sample_tables(
        video_frames=frames,
        video_sizes=video_sizes,
        video_chunk_offset=video_chunk_offset,
        audio_bytes=audio_bytes,
        audio_samples=frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0]),
        audio_chunk_offset=audio_chunk_offset,
    )

    vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
    dinf = _dinf()

    minf_v = _box(b"minf", vmhd + dinf + video_stbl)
    mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
    trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)

    traks = trak_v
    mdat_payload = video_chunk
    if audio_bytes is not None:
        smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
        minf_a = _box(b"minf", smhd + dinf + audio_stbl)
        mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])) + _hdlr(b"soun", b"SoundHandler") + minf_a)
        trak_a = _box(b"trak", _tkhd(2, frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0]), 0x0100, 0, 0) + mdia_a)
        traks = trak_v + trak_a
        mdat_payload = video_chunk + audio_bytes

    moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME, 3 if with_audio else 2) + traks)
    mdat = _box(b"mdat", mdat_payload)
    return ftyp + mdat + moov


# ---------------------------------------------------------------------------
# Canonical wire logic
# ---------------------------------------------------------------------------


def fixed_profile(audio_mode: str) -> dict:
    """The exact profile the renderer emits for one audio mode."""
    profile = {
        "width": WIDTH,
        "height": HEIGHT,
        "fps_rational": list(FPS_RATIONAL),
        "time_base": list(TIME_BASE),
        "container": CONTAINER,
        "video_codec": VIDEO_CODEC,
        "video_profile": None,
        "video_level": None,
        "pixel_format": PIXEL_FORMAT,
        "audio_codec": None,
        "audio_sample_rate": None,
        "audio_channel_layout": None,
        "duration_tolerance": 1,
    }
    if audio_mode == "rendered":
        profile.update(
            audio_codec=AUDIO_CODEC,
            audio_sample_rate=AUDIO_SAMPLE_RATE,
            audio_channel_layout=AUDIO_CHANNEL_LAYOUT,
        )
    return profile


def error_payload(kind: str, message: str, details: dict) -> dict:
    """A language-neutral structured renderer failure (RendererError shape)."""
    return {
        "schema_version": 1,
        "kind": kind,
        "backend": BACKEND_ID,
        "message": message,
        "recovery_command": None,
        "details": details,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _requested_audio(request: dict) -> str:
    return request.get("audio") or "rendered"


def validate_request(request: dict) -> None:
    """Renderer-level request validation (mirrors the raw_command fixture)."""
    version = request.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        raise ValueError(
            f"unsupported request schema_version {version!r}; expected 1"
        )
    output_name = request.get("output_name")
    if not isinstance(output_name, str) or output_name in (".", ".."):
        raise ValueError("output_name must be a non-empty portable basename")
    if not _OUTPUT_NAME_RE.fullmatch(output_name):
        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
    if ".." in output_name or output_name.startswith("."):
        raise ValueError(
            f"invalid output name {output_name!r}: must not contain '..' or start with '.'"
        )
    window = request.get("window")
    if window is not None and not isinstance(window, dict):
        raise ValueError("window must be an object or null")
    if isinstance(window, dict):
        end = window.get("end_frame")
        start = window.get("start_frame", 0)
        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
    audio = request.get("audio")
    if audio not in (None, "rendered", "passthrough", "none"):
        raise ValueError(f"audio={audio!r} is not one of rendered/passthrough/none")


def support_report(request: dict) -> dict:
    """Request-sensitive support: only the [0, 48) @ 24fps + supported-audio
    combination is supported; every deviation is named in a single reason."""
    mismatches: list[str] = []
    window = request.get("window")
    if not isinstance(window, dict):
        mismatches.append(f"window={window!r} (required [0, {SUPPORTED_WINDOW_FRAMES}) @ 24fps)")
    else:
        start = window.get("start_frame", 0)
        end = window.get("end_frame")
        fps = window.get("fps_rational")
        if start != 0 or end != SUPPORTED_WINDOW_FRAMES or fps != list(FPS_RATIONAL):
            mismatches.append(
                f"window=[{start}, {end})@{fps} (fixed [0, {SUPPORTED_WINDOW_FRAMES}) @ 24fps)"
            )
    audio = request.get("audio")
    if audio not in SUPPORTED_AUDIO_MODES:
        modes = ", ".join(SUPPORTED_AUDIO_MODES)
        mismatches.append(f"audio={audio!r} (supported: {modes})")
    profile = request.get("profile")
    if isinstance(profile, dict):
        expected = fixed_profile(audio if audio in SUPPORTED_AUDIO_MODES else "rendered")
        for field, fixed in expected.items():
            requested = profile.get(field)
            if requested is not None and requested != fixed:
                mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
    if mismatches:
        return {
            "schema_version": 1,
            "supported": False,
            "reasons": [
                "profile not produced by " + BACKEND_ID + ": " + "; ".join(mismatches)
            ],
            "features": {"media": False, "audio_mode": "none"},
            "alternatives": [],
            "backend": BACKEND_ID,
            "backend_version": BACKEND_VERSION,
        }
    return {
        "schema_version": 1,
        "supported": True,
        "reasons": [],
        "features": {"media": True, "audio_mode": audio or "rendered"},
        "alternatives": [],
        "backend": BACKEND_ID,
        "backend_version": BACKEND_VERSION,
    }


def render_result(request: dict, request_path: Path) -> dict:
    """Render the deterministic media and return the RenderResult-shaped dict.

    The invocation workspace is the directory holding the request file; every
    generated artifact stays contained there.
    """
    validate_request(request)
    window = request.get("window")
    if isinstance(window, dict):
        start = int(window.get("start_frame", 0))
        end = int(window["end_frame"])
    else:
        start, end = 0, SUPPORTED_WINDOW_FRAMES
    frames = end - start
    if frames <= 0:
        raise ValueError("window must span at least one frame")

    audio_mode = _requested_audio(request)
    output_name = request["output_name"]
    workspace = request_path.resolve().parent
    out_dir = workspace / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    video_rel = f"outputs/{output_name}"
    video_path = out_dir / output_name

    media = build_mp4(frames, with_audio=audio_mode == "rendered")
    video_path.write_bytes(media)

    attachments: dict = {}
    backend_config = request.get("backend_config") or {}
    config = backend_config.get(BACKEND_ID) or {}
    if config.get("attachment") == "manifest":
        attachment_path = out_dir / ATTACHMENT_NAME
        attachment_path.write_bytes(ATTACHMENT_CONTENT)
        attachments[ATTACHMENT_NAME] = {
            "name": ATTACHMENT_NAME,
            "path": f"outputs/{ATTACHMENT_NAME}",
            "kind": ATTACHMENT_KIND,
            "sha256": hashlib.sha256(ATTACHMENT_CONTENT).hexdigest(),
        }

    probed_profile = fixed_profile(audio_mode)
    probed_profile["duration_tolerance"] = int(
        (request.get("profile") or {}).get("duration_tolerance", 1)
    )
    return {
        "schema_version": 1,
        "video": {
            "path": video_rel,
            "profile": probed_profile,
            "sha256": hashlib.sha256(media).hexdigest(),
            "duration_frames": frames,
            "audio": audio_mode,
            "attachments": attachments,
        },
        "backend_fragments": {
            BACKEND_ID: {
                "renderer": "sdk",
                "media": "generated",
                "audio_mode": audio_mode,
                "deterministic": True,
            }
        },
        "audio_ownership": audio_mode,
        "normalization": [],
        "logs": [],
        "metadata": {},
    }


def write_render_result(request: dict, request_path: Path, result_path: Path) -> int:
    """Canonical render dispatch shared by the raw wrapper and any inline SDK
    runner: validates, renders, and writes the authoritative result JSON."""
    try:
        result = render_result(request, request_path)
        _write_json(result_path, result)
    except ValueError as exc:
        _write_json(
            result_path,
            error_payload("protocol", str(exc), {"error_type": "ValueError"}),
        )
    except Exception as exc:  # pragma: no cover - unexpected failure path
        _write_json(
            result_path,
            error_payload(
                "internal",
                f"{BACKEND_ID} renderer failed: {exc}",
                {"error_type": type(exc).__name__},
            ),
        )
    return 0


def write_support_result(request: dict, result_path: Path) -> int:
    """Canonical support dispatch shared by the raw wrapper and any inline SDK
    runner: decides and writes the authoritative SupportReport JSON."""
    try:
        validate_request(request)
        report = support_report(request)
        _write_json(result_path, report)
    except ValueError as exc:
        _write_json(
            result_path,
            error_payload(
                "protocol",
                f"invalid support request: {exc}",
                {"error_type": type(exc).__name__},
            ),
        )
    return 0
