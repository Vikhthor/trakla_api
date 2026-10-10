from redis import Redis
from rq import Queue

q = Queue(connection=Redis())

# from my_module import count_words_at_url
# result = q.enqueue(count_words_at_url, 'https://python-rq.org')

# To start executing enqueued function calls in the background, start a worker from your project’s directory:
# $ rq worker --with-scheduler
# *** Listening for work on default
# Got count_words_at_url('http://nvie.com') from default
# Job result = 818
# *** Listening for work on default

# Queue: contains a list of Job instances to be executed in a FIFO manner.
# Job: contains the function to be executed by the worker.
# Worker: responsible for getting Job instances from a Queue and executing them.
# Execution: contains runtime data of a Job, created by a Worker when it executes a Job.
# Result: stores the outcome of an Execution, whether it succeeded or failed.
