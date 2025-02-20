import logging
import math
from typing import List
import av
import cv2
import numpy as np
import httpx  # Use httpx instead of requests for async
from streamlit_server_state import server_state, server_state_lock
from streamlit_webrtc import WebRtcMode, create_mix_track, webrtc_streamer
from streamlit_webrtc.component import WebRtcStreamerContext
from io import BytesIO
from PIL import Image
import asyncio

logger = logging.getLogger(__name__)

FASTAPI_URL = "http://localhost:8000/predict"  # FastAPI endpoint for predictions


async def send_to_fastapi(frame: np.ndarray) -> str:
    """
    Send a video frame to the FastAPI backend for emotion prediction.
    """
    # Convert frame to RGB and PIL image
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)

    # Send the image to FastAPI for prediction asynchronously using httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                FASTAPI_URL, files={"file": ("frame.jpg", buffer, "image/jpeg")}
            )
        if response.status_code == 200:
            return response.json().get("prediction", "Unknown")  # Get prediction
        else:
            return "Error"
    except Exception as e:
        logger.error(f"Error sending frame to FastAPI: {e}")
        return "Error"


def mixer_callback(frames: List[av.VideoFrame]) -> av.VideoFrame:
    """
    Combine multiple video frames into a grid and overlay emotion predictions.
    """
    buf_w = 640  # Width of output buffer
    buf_h = 480  # Height of output buffer
    buffer = np.zeros((buf_h, buf_w, 3), dtype=np.uint8)

    n_inputs = len(frames)
    if n_inputs == 0:
        return None  # Return None if there are no frames

    n_cols = math.ceil(math.sqrt(n_inputs))
    n_rows = math.ceil(n_inputs / n_cols)
    grid_w = buf_w // n_cols
    grid_h = buf_h // n_rows

    for i in range(n_inputs):
        frame = frames[i]
        if frame is None:
            continue

        grid_x = (i % n_cols) * grid_w
        grid_y = (i // n_cols) * grid_h

        img = frame.to_ndarray(format="bgr24")
        src_h, src_w = img.shape[0:2]

        aspect_ratio = src_w / src_h

        window_w = min(grid_w, int(grid_h * aspect_ratio))
        window_h = min(grid_h, int(window_w / aspect_ratio))

        window_offset_x = (grid_w - window_w) // 2
        window_offset_y = (grid_h - window_h) // 2

        window_x0 = grid_x + window_offset_x
        window_y0 = grid_y + window_offset_y
        window_x1 = window_x0 + window_w
        window_y1 = window_y0 + window_h

        buffer[window_y0:window_y1, window_x0:window_x1, :] = cv2.resize(
            img, (window_w, window_h)
        )

        # Use asyncio.create_task() to schedule the async function without blocking the loop
        asyncio.create_task(overlay_emotion_label(buffer, img, window_x0, window_y0))

    new_frame = av.VideoFrame.from_ndarray(buffer, format="bgr24")

    return new_frame


async def overlay_emotion_label(buffer: np.ndarray, img: np.ndarray, window_x0: int, window_y0: int):
    """Handle the emotion label overlay asynchronously."""
    emotion_label = await send_to_fastapi(img)
    cv2.putText(
        buffer,
        emotion_label,
        (window_x0 + 10, window_y0 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2,
    )


def main():
    """
    Main Streamlit RTC app entry point.
    """
    with server_state_lock["webrtc_contexts"]:
        if "webrtc_contexts" not in server_state:
            server_state["webrtc_contexts"] = []

    with server_state_lock["mix_track"]:
        if "mix_track" not in server_state:
            server_state["mix_track"] = create_mix_track(
                kind="video", mixer_callback=mixer_callback, key="mix"
            )

    mix_track = server_state["mix_track"]

    self_ctx = webrtc_streamer(
        key="self",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        media_stream_constraints={"video": True, "audio": True},
        source_video_track=mix_track,
        sendback_audio=False,
    )

    if self_ctx.input_video_track:
        mix_track.add_input_track(self_ctx.input_video_track)

    with server_state_lock["webrtc_contexts"]:
        webrtc_contexts: List[WebRtcStreamerContext] = server_state["webrtc_contexts"]
        self_is_playing = self_ctx.state.playing
        if self_is_playing and self_ctx not in webrtc_contexts:
            webrtc_contexts.append(self_ctx)
            server_state["webrtc_contexts"] = webrtc_contexts
        elif not self_is_playing and self_ctx in webrtc_contexts:
            webrtc_contexts.remove(self_ctx)
            server_state["webrtc_contexts"] = webrtc_contexts

    # Audio streams are transferred in SFU manner
    for ctx in webrtc_contexts:
        if ctx == self_ctx or not ctx.state.playing:
            continue
        webrtc_streamer(
            key=f"sound-{id(ctx)}",
            mode=WebRtcMode.RECVONLY,
            rtc_configuration={ 
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={"video": False, "audio": True},
            source_audio_track=ctx.input_audio_track,
            desired_playing_state=ctx.state.playing,
        )


if __name__ == "__main__":
    import os

    DEBUG = os.environ.get("DEBUG", "false").lower() not in ["false", "no", "0"]

    logging.basicConfig(
        format="[%(asctime)s] %(levelname)7s from %(name)s in %(pathname)s:%(lineno)d: "
        "%(message)s",
        force=True,
    )

    logger.setLevel(level=logging.DEBUG if DEBUG else logging.INFO)

    st_webrtc_logger = logging.getLogger("streamlit_webrtc")
    st_webrtc_logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    aioice_logger = logging.getLogger("aioice")
    aioice_logger.setLevel(logging.WARNING)

    fsevents_logger = logging.getLogger("fsevents")
    fsevents_logger.setLevel(logging.WARNING)

    main()
