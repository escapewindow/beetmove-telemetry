"""
Module containing util functions to serve pushing telemetry artifacts under
maven.mozilla.org
"""
import json
import mimetypes
import sys
import asyncio
import aiohttp
import boto3

from constants import MIME_MAP, CACHE_CONTROL_MAXAGE


def setup_mimetypes():
    mimetypes.init()
    # in py3 we must exhaust the map so that add_type is actually invoked
    list(map(
        lambda ext_mimetype: mimetypes.add_type(ext_mimetype[1], ext_mimetype[0]), MIME_MAP.items()
    ))


def load_json_or_yaml(string, is_path=False, file_type='json',
                      message="Failed to load %(file_type)s: %(exc)s"):
    _load_fh = json.load
    _load_str = json.loads

    if is_path:
        with open(string, 'r') as fh:
            contents = _load_fh(fh)
    else:
        contents = _load_str(string)
    return contents


async def _handle_asyncio_loop(async_main, context):
    async with aiohttp.ClientSession() as session:
        context.session = session
        await async_main(context)


async def _process_future_exceptions(tasks, raise_at_first_error):
    succeeded_results = []
    error_results = []

    if tasks:
        await asyncio.wait(tasks)
        for task in tasks:
            exc = task.exception()
            if exc:
                if raise_at_first_error:
                    raise exc
                else:
                    error_results.append(exc)
            else:
                succeeded_results.append(task.result())

    return succeeded_results, error_results


async def raise_future_exceptions(tasks):
    succeeded_results, _ = await _process_future_exceptions(tasks, raise_at_first_error=True)
    return succeeded_results


async def put(context, url, headers, abs_filename, session=None):
    session = session or context.session
    with open(abs_filename, "rb") as fh:
        async with session.put(url, data=fh, headers=headers, compress=False) as resp:
            print(f"put {abs_filename}: {resp.status}")
            response_text = await resp.text()
            if response_text:
                print(response_text)
            if resp.status not in (200, 204):
                raise Exception(f"Bad status {resp.status}")
    return resp


def guess_mime_type(path):
    suffixes = {
        ".module": "text/plain",
        ".sha256": "text/plain",
        ".sha512": "text/plain",
    }
    mime_type = mimetypes.guess_type(path)[0]
    if not mime_type:
        for suffix, mime in suffixes.items():
            if path.endswith(suffix):
                mime_type = mime
                break
    if not mime_type:
        raise Exception(f"Unable to discover valid mime-type for path ({path}), "
                        f"mimetypes.guess_type() returned {mime_type}")
    return mime_type


async def upload_to_s3(context, s3_key, path):
    mime_type = guess_mime_type(path)
    api_kwargs = {
        'Bucket': context.config['bucket_config'][context.bucket]['buckets']['telemetry'],
        'Key': s3_key,
        'ContentType': mime_type,
    }
    headers = {
        'Content-Type': mime_type,
        'Cache-Control': 'public, max-age=%d' % CACHE_CONTROL_MAXAGE,
    }
    creds = context.config['bucket_config'][context.bucket]['credentials']
    s3 = boto3.client('s3', aws_access_key_id=creds['id'], aws_secret_access_key=creds['key'],)
    url = s3.generate_presigned_url('put_object', api_kwargs, ExpiresIn=1800, HttpMethod='PUT')

    # FIXME: add proper logging
    print(f"upload_to_s3: {path} -> s3://{context.bucket}/{s3_key}")
    if not context.dry_run:
        await put(context, url, headers, path, session=context.session)
