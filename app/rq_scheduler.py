from redis import Redis
from rq import Queue, Retry
from rq.repeat import Repeat
from datetime import datetime, timedelta

queue = Queue(connection=Redis())

def say_hello():
    print("Hello")

# # Schedule job to run at 9:15, October 10th
# job = queue.enqueue_at(datetime(2019, 10, 8, 9, 15), say_hello)

# # Schedule job to be run in 10 seconds
# job = queue.enqueue_in(timedelta(seconds=10), say_hello)

# # Repeat job 3 times after successful completion, with 60 second intervals
# job = queue.enqueue(say_hello, repeat=Repeat(times=3, interval=60))

# # Use different intervals between repetitions
# job = queue.enqueue(say_hello, repeat=Repeat(times=3, interval=[10, 30, 60]))

# # Retry up to 3 times, failed job will be requeued immediately
# queue.enqueue(say_hello, retry=Retry(max=3))

# # Retry up to 3 times, with configurable intervals between retries
# queue.enqueue(say_hello, retry=Retry(max=3, interval=[10, 30, 60]))
