import logging
from redis import Redis
from rq import Queue, Worker
from rq.serializers import JSONSerializer
from . import config


def main():
    logging.basicConfig(level=logging.INFO)
    config.initialize_storage()
    redis = Redis.from_url(config.REDIS_URL)
    queue = Queue(config.QUEUE, connection=redis, serializer=JSONSerializer)
    Worker([queue], connection=redis, serializer=JSONSerializer, worker_ttl=60).work()


if __name__ == '__main__':
    main()
