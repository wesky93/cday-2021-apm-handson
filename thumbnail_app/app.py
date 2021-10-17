import logging
import os
import tempfile
from io import BytesIO
from uuid import uuid4

import redis
import requests
import smartcrop
from PIL import Image
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.responses import StreamingResponse

from trace_helper import trace_function

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', 6379)
REDIS_DB = os.environ.get('REDIS_DB', 0)

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'awskrug-cday')

cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, )


def make_key() -> str:
    return uuid4().hex[:8]


app = FastAPI()
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

exporter = JaegerExporter()
span_processor = BatchSpanProcessor(exporter)
trace.get_tracer_provider().add_span_processor(span_processor)


# 아키텍쳐 https://drive.google.com/file/d/1u2ApjhQQj5ojDUPH0x2w79SAM3BuFVV_/view?usp=sharing

@app.get('/crop')
def crop(url: str, width: int, height: int):
    with tracer.start_as_current_span('crop') as span:
        span.set_attributes(dict(
            url=url,
            width=width,
            height=height
        ))
        temp_file = make_key()
        with tempfile.TemporaryDirectory() as temp_dir:
            download_file = os.path.join(temp_dir, temp_file)
            file_download(url, download_file)

            # 이미지 변환
            with Image.open(download_file) as image:
                # 이미지 변환
                img = crop_handler(image, width, height)

                # 포맷 변환
                raw_img = save_to_jpeg(img)
        return StreamingResponse(BytesIO(raw_img), media_type="image/jpeg")


@app.get('/resize')
@trace_function(tracer)
def resize(url: str, width: int, height: int):
    temp_file = make_key()
    with tempfile.TemporaryDirectory() as temp_dir:
        download_file = os.path.join(temp_dir, temp_file)
        file_download(url, download_file)

        # 이미지 변환
        with Image.open(download_file) as image:
            # 이미지 변환
            img = crop_handler(image, width, height)

            # 포맷 변환
            raw_img = save_to_jpeg(img)
    return StreamingResponse(BytesIO(raw_img), media_type="image/jpeg")



@app.get('/smartcrop')
@trace_function(tracer)
def smart_crop(url: str, width: int, height: int):
    temp_file = make_key()

    with tempfile.TemporaryDirectory() as temp_dir:
        download_file = os.path.join(temp_dir, temp_file)
        file_download(url, download_file)

        # 이미지 변환
        with Image.open(download_file) as image:
            # 이미지 변환
            img = smart_crop_handler(image, width, height)

            # 포맷 변환
            raw_img = save_to_jpeg(img)
    return StreamingResponse(BytesIO(raw_img), media_type="image/jpeg")


@trace_function(tracer)
def file_download(url: str, target_path: str):
    logging.info(f"start download {url=} to {target_path=}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(target_path, 'wb') as f:
        for block in r.iter_content(1024):
            if not block:
                break
            f.write(block)
    logging.info(f"finished download")

@trace_function(tracer)
def resize_handler(image: Image, width: int, height: int):
    with tracer.start_as_current_span('resize_handler') as span:
        span.set_attributes(dict(
            width=width,
            height=height
        ))
        image.thumbnail((width, height), Image.ANTIALIAS)
        return image


@trace_function(tracer)
def crop_handler(image: Image, width: int, height: int, **kwargs):
    origin_width = image.size[0]
    origin_height = image.size[1]

    origin_aspect = origin_width / float(origin_height)

    target_aspect = width / float(height)

    if origin_aspect > target_aspect:
        # crop the left and right edges:
        new_width = int(target_aspect * origin_height)
        offset = (origin_width - new_width) / 2
        resize = (offset, 0, origin_width - offset, origin_height)
    else:
        # crop the top and bottom:
        new_height = int(origin_width / target_aspect)
        offset = (origin_height - new_height) / 2
        resize = (0, offset, origin_width, origin_height - offset)

    img = image.crop(resize)
    img.thumbnail((width, height), Image.ANTIALIAS)
    return img


@trace_function(tracer)
def smart_crop_handler(image: Image, width: int, height: int, **kwargs):
    sc = smartcrop.SmartCrop()
    origin_width = image.size[0]
    origin_height = image.size[1]

    origin_aspect = origin_width / float(origin_height)

    target_aspect = width / float(height)

    if origin_aspect > target_aspect:
        new_width = int(target_aspect * origin_height)
        crop_size = (new_width, origin_height)
    else:
        new_height = int(origin_width / target_aspect)
        crop_size = (origin_width, new_height)

    if image.mode != 'RGB':
        image = image.convert('RGB')

    with tracer.start_as_current_span('smart_croping') as span:
        result = sc.crop(image, *crop_size)['top_crop']
    resize = (
        result['x'],
        result['y'],
        result['width'] + result['x'],
        result['height'] + result['y']
    )
    img = image.crop(resize)
    img.thumbnail((width, height), Image.ANTIALIAS)
    return img


@trace_function(tracer)
def save_to_jpeg(image):
    if image.mode != 'RGB':
        image = image.convert('RGB')
    with BytesIO() as f:
        image.save(f, format='JPEG')
        return f.getvalue()
