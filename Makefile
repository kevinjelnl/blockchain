dev:
	gunicorn --reload --workers=1 -b 127.0.0.1:8080 blockchain:app 8080

nodemanager:
	gunicorn --reload --workers=1 -b 127.0.0.1:9001 nodemanager:app 

node1:
	gunicorn --reload --workers=1 -b 127.0.0.1:8081 blockchain:app 8081
node2:
	gunicorn --reload --workers=1 -b 127.0.0.1:8082 blockchain:app 8082
node3:
	gunicorn --reload --workers=1 -b 127.0.0.1:8083 blockchain:app 8083
node4:
	gunicorn --reload --workers=1 -b 127.0.0.1:8084 blockchain:app 8084
node5:
	gunicorn --reload --workers=1 -b 127.0.0.1:8084 blockchain:app 8085
