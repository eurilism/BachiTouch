import asyncio
import json
import argparse
import os
import queue
import sys
import threading
from aiohttp import web, WSMsgType


def get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(*relative_parts: str) -> str:
    return os.path.join(get_base_dir(), *relative_parts)
from pynput.keyboard import Controller, Key

keyboard = Controller()

DEFAULT_MAPPINGS = {
    "left_rim": "d",
    "left_face": "f",
    "right_face": "j",
    "right_rim": "k",
}


class KeyPressWorker(threading.Thread):
    def __init__(self, max_queue_size=200):
        super().__init__(daemon=True)
        self.queue = queue.Queue(max_queue_size)
        self.running = True

    def run(self):
        while self.running:
            try:
                key, shift = self.queue.get(timeout=0.01)
            except queue.Empty:
                continue
            try:
                if shift:
                    press_shift_key(key)
                else:
                    press_key(key)
            except Exception:
                pass
            finally:
                self.queue.task_done()

    def stop(self):
        self.running = False


key_worker = KeyPressWorker()
key_worker.start()


def enqueue_key(key, shift=False):
    try:
        key_worker.queue.put_nowait((key, shift))
    except queue.Full:
        pass

async def index(request):
    index_path = get_resource_path('static', 'index.html')
    return web.FileResponse(index_path)

async def bg_image(request):
    image_path = get_resource_path('bg.jpg')
    return web.FileResponse(image_path)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    mappings = DEFAULT_MAPPINGS.copy()

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except Exception:
                continue

            typ = data.get('type')
            if typ == 'mapping':
                newmap = data.get('mappings', {})
                for k, v in newmap.items():
                    if k in mappings and isinstance(v, str) and v:
                        mappings[k] = v
                await ws.send_json({'type': 'mappings_ack', 'mappings': mappings})
            elif typ == 'tap':
                control = data.get('control')
                if control == 'pause':
                    custom_key = mappings.get('custom', 'escape')
                    if isinstance(custom_key, str):
                        custom_key_lower = custom_key.lower()
                        if custom_key_lower in ('escape', 'esc'):
                            enqueue_key(Key.esc)
                        else:
                            enqueue_key(custom_key_lower)
                elif control in ('left_rim_shift', 'right_rim_shift'):
                    mapping_key = mappings.get('left_rim' if control == 'left_rim_shift' else 'right_rim')
                    if mapping_key:
                        enqueue_key(mapping_key, shift=True)
                else:
                    key = mappings.get(control)
                    if key:
                        enqueue_key(key)
            elif typ == 'ping':
                await ws.send_json({'type': 'pong'})
        elif msg.type == WSMsgType.ERROR:
            print('ws connection closed with exception %s' % ws.exception())

    return ws

def press_key(key):
    try:
        keyboard.press(key)
        keyboard.release(key)
    except Exception:
        # fallback: try pressing first character
        if isinstance(key, str) and key:
            keyboard.press(key[0])
            keyboard.release(key[0])

def press_shift_key(key):
    try:
        keyboard.press(Key.shift)
        keyboard.press(key)
        keyboard.release(key)
        keyboard.release(Key.shift)
    except Exception:
        if isinstance(key, str) and key:
            keyboard.press(Key.shift)
            keyboard.press(key[0])
            keyboard.release(key[0])
            keyboard.release(Key.shift)


def shutdown_key_worker():
    key_worker.stop()
    key_worker.join(timeout=1)


@web.middleware
async def no_cache_static_middleware(request, handler):
    response = await handler(request)
    if request.path.startswith('/static/') and isinstance(response, web.StreamResponse):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


def make_app():
    static_path = get_resource_path('static')
    app = web.Application(middlewares=[no_cache_static_middleware])
    app.router.add_get('/', index)
    app.router.add_get('/bg.jpg', bg_image)
    app.router.add_get('/ws', websocket_handler)
    app.router.add_static('/static/', path=static_path, name='static')
    return app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()

    app = make_app()
    web.run_app(app, host=args.host, port=args.port)

if __name__ == '__main__':
    main()
