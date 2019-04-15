# okralact

> A repository for online OCRD training infrastructure.

## Installation

Running `okralact` requires

* Python 3
* `redis` as the job queue/database

In Ubuntu:

```sh
sudo apt-get install redis
pip install -r requirements.txt
```

## Running

### Start redis

```
make start-server
```

### Start evaluation worker

```
make start-worker-eval
```

### Start training worker

```
make start-worker-train
```
