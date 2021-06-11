import signal
import threading
import time

import redis
import rq
from botfunctions import check_submissions

UPDATE_TIMEOUT = 30

sub_thread = None


class SubmitterThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.stop_thread = False
        self.queue = rq.Queue(name="acbot", connection=redis.Redis())

        for job in self.queue.job_ids:
            self.queue.remove(job)

    def stop(self):
        self.stop_thread = True

    def run(self):
        while not self.stop_thread:
            job = self.queue.enqueue(check_submissions, job_id="praw", result_ttl=UPDATE_TIMEOUT+60)
            time.sleep(UPDATE_TIMEOUT)


def sigterm_handler(_signo, _stack_frame):
    print("Shuting down")
    sub_thread.stop()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)

    sub_thread = SubmitterThread()
    sub_thread.start()

    worker = rq.Worker(queues=["acbot"], connection=redis.Redis())
    worker.work(with_scheduler=True)

    sub_thread.join()
