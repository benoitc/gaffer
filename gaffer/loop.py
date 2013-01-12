
import multiprocessing
import pyuv

def patch_loop(loop):
    if hasattr(loop, "queue_work") or not loop:
        # we only patch the loop for 0.8
        return loop

    tloop = pyuv.ThreadPool(loop)
    tloop.set_parallel_threads(multiprocessing.cpu_count())

    loop._tloop = tloop
    loop.queue_work = loop._tloop.queue_work
    return loop


def get_loop(default=False):
    if default:
        loop = pyuv.Loop.default_loop()
    else:
        loop = pyuv.Loop()
    return patch_loop(loop)
