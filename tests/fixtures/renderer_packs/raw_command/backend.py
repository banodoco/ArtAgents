#!/usr/bin/env python3
"""Raw v1 command backend for the ``raw_command`` fixture pack (T2.2).

Implements the frozen render-backend-v1 wire protocol WITHOUT importing the
Astrid SDK and WITHOUT ffmpeg:

    python3 backend.py render|support --request <abs.json> --result <abs.json>

* ``support`` writes a SupportReport-shaped result.
* ``render``  writes a deterministic ~2 second MP4 containing a solid-color
  H.264 (baseline) video track and a silent 16-bit PCM (``sowt``) audio
  track, then writes a RenderResult-shaped result whose sha256 is the real
  digest of the produced file.

The script is pure stdlib (argparse, hashlib, json, struct). It never writes
Astrid ledger files (no ``run.json``): the only files it creates are the
authoritative ``--result`` JSON and the generated video under the request's
workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

BACKEND_ID = "raw_command.renderer"
BACKEND_VERSION = "1.0.0"

# Deterministic media constants.  The container timing (time_base 1/12288,
# 512 ticks per frame at 24fps) matches the committed request fixture.
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
AUDIO_CODEC = "sowt"
AUDIO_CHANNEL_LAYOUT = "stereo"

_MB_COLS = WIDTH // 16          # 120
_MB_ROWS = (HEIGHT + 15) // 16  # 68  -> 1088 coded lines, 8 cropped
_MB_COUNT = _MB_COLS * _MB_ROWS  # 8160

_MATRIX = struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)

_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


# ---------------------------------------------------------------------------
# Bit-level H.264 (baseline, all-IDR) construction
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
    _ue(w, 1)               # frame_crop_bottom_offset (1088 -> 1080)
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
    whole frame decodes to a deterministic solid color.  Six bits per MB:
    mb_type ue(3) == "00100" (I_16x16 with Intra16x16PredMode 2 = DC) plus
    intra_chroma_pred_mode ue(0) == "1" (chroma DC).
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


def _mvhd(duration: int) -> bytes:
    payload = (
        struct.pack(">IIII", 0, 0, 12288, duration)  # timescale = 12288
        + struct.pack(">I", 0x00010000)              # rate 1.0
        + struct.pack(">H", 0x0100)                  # volume 1.0
        + struct.pack(">H", 0)
        + struct.pack(">II", 0, 0)
        + _matrix()
        + b"\x00" * 24
        + struct.pack(">I", 3)                       # next_track_ID
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
        + b"RawCommand\x00" + b"\x00" * 21  # compressorname (32 bytes)
        + struct.pack(">Hh", 24, -1)       # depth 24, pre_defined -1
    )
    return _box(b"avc1", visual + _box(b"avcC", avcc))


def _sowt_entry() -> bytes:
    wave = _box(
        b"wave",
        _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
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
    audio_bytes: bytes,
    audio_samples: int,
    audio_chunk_offset: int,
) -> bytes:
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

    stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
    stts_a = _fullbox(
        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
    )
    stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
    stsz_a = _fullbox(
        b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
    )
    stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))

    video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
    audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
    return video_stbl, audio_stbl


def _build_mp4(frames: int) -> bytes:
    """Return a deterministic MP4: `frames` H.264 IDR frames + PCM silence."""
    video_chunk = bytearray()
    video_sizes: list[int] = []
    for frame_index in range(frames):
        nal = _idr_slice_nal(frame_index)
        sample = struct.pack(">I", len(nal)) + nal
        video_chunk += sample
        video_sizes.append(len(sample))
    video_chunk = bytes(video_chunk)

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
        audio_samples=audio_samples,
        audio_chunk_offset=audio_chunk_offset,
    )

    vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
    smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
    dinf = _dinf()

    minf_v = _box(b"minf", vmhd + dinf + video_stbl)
    mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
    trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)

    minf_a = _box(b"minf", smhd + dinf + audio_stbl)
    mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, audio_samples) + _hdlr(b"soun", b"SoundHandler") + minf_a)
    trak_a = _box(b"trak", _tkhd(2, audio_samples, 0x0100, 0, 0) + mdia_a)

    moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME) + trak_v + trak_a)
    mdat = _box(b"mdat", video_chunk + audio_bytes)
    return ftyp + mdat + moov


# ---------------------------------------------------------------------------
# Protocol verbs
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
    _write_json(
        result_path,
        {
            "schema_version": 1,
            "kind": kind,
            "backend": BACKEND_ID,
            "message": message,
            "recovery_command": None,
            "details": details,
        },
    )


def _validate_request(request: dict) -> None:
    if request.get("schema_version") != 1:
        raise ValueError(
            f"unsupported request schema_version {request.get('schema_version')!r}; expected 1"
        )
    output_name = request.get("output_name")
    if not isinstance(output_name, str) or output_name in (".", ".."):
        raise ValueError("output_name must be a non-empty portable basename")
    if not _OUTPUT_NAME_RE.fullmatch(output_name):
        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
    window = request.get("window")
    if window is not None and not isinstance(window, dict):
        raise ValueError("window must be an object or null")
    if isinstance(window, dict):
        end = window.get("end_frame")
        start = window.get("start_frame", 0)
        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
            raise ValueError("window must satisfy 0 <= start_frame < end_frame")


def _support(result_path: Path) -> int:
    _write_json(
        result_path,
        {
            "schema_version": 1,
            "supported": True,
            "reasons": [],
            "features": {"media": True, "audio_mode": "rendered"},
            "alternatives": [],
            "backend": BACKEND_ID,
            "backend_version": BACKEND_VERSION,
        },
    )
    return 0


def _render(request: dict, result_path: Path, request_path: Path) -> int:
    try:
        _validate_request(request)
        window = request.get("window")
        profile = request.get("profile") or {}
        if isinstance(window, dict):
            start = int(window.get("start_frame", 0))
            end = int(window["end_frame"])
        else:
            start, end = 0, 48
        frames = end - start
        if frames <= 0:
            raise ValueError("window must span at least one frame")

        output_name = request["output_name"]
        # The invocation workspace is the directory holding the request file;
        # keep every generated artifact contained there.
        workspace = request_path.resolve().parent
        out_dir = workspace / "outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        video_rel = f"outputs/{output_name}"
        video_path = out_dir / output_name

        media = _build_mp4(frames)
        video_path.write_bytes(media)

        probed_profile = {
            "width": WIDTH,
            "height": HEIGHT,
            "fps_rational": list(FPS_RATIONAL),
            "time_base": list(TIME_BASE),
            "container": CONTAINER,
            "video_codec": VIDEO_CODEC,
            "video_profile": None,
            "video_level": None,
            "pixel_format": PIXEL_FORMAT,
            "audio_codec": AUDIO_CODEC,
            "audio_sample_rate": AUDIO_SAMPLE_RATE,
            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
            "duration_tolerance": int(profile.get("duration_tolerance", 1)),
        }
        result = {
            "schema_version": 1,
            "video": {
                "path": video_rel,
                "profile": probed_profile,
                "sha256": hashlib.sha256(media).hexdigest(),
                "duration_frames": frames,
                "audio": "rendered",
                "attachments": {},
            },
            "backend_fragments": {
                BACKEND_ID: {
                    "renderer": "raw_command",
                    "media": "generated",
                    "audio_mode": "rendered",
                    "deterministic": True,
                }
            },
            "audio_ownership": "rendered",
            "normalization": [],
            "logs": [],
            "metadata": {},
        }
        _write_json(result_path, result)
        return 0
    except ValueError as exc:
        _write_error(result_path, "protocol", str(exc), {"error_type": "ValueError"})
        return 0
    except Exception as exc:  # pragma: no cover - unexpected failure path
        _write_error(
            result_path,
            "internal",
            f"raw_command renderer failed: {exc}",
            {"error_type": type(exc).__name__},
        )
        return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="backend.py",
        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
    )
    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
    parser.add_argument("--request", required=True, help="absolute path to request JSON")
    parser.add_argument("--result", required=True, help="absolute path to result JSON")
    args = parser.parse_args(argv)

    request_path = Path(args.request)
    result_path = Path(args.result)
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _write_error(
            result_path,
            "protocol",
            f"cannot read request JSON from {request_path}: {exc}",
            {"error_type": type(exc).__name__},
        )
        return 0

    if args.verb == "support":
        return _support(result_path)
    if args.verb in ("plan", "finalize"):
        _write_error(
            result_path,
            "unsupported",
            f"{BACKEND_ID} only implements render and support",
            {"verb": args.verb},
        )
        return 0
    return _render(request, result_path, request_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
