#python3 run.py
pybabel compile -d finalfrsproject/translations
gunicorn -w ${GUNICORN_WORKERS:-3} --preload -b 0.0.0.0:4001 --keyfile=key-new.pem --certfile=cert.pem run:app
#uwsgi --http 0.0.0.0:4000 --gevent 1000 --http-websockets --master --wsgi-file run.py --callable app
