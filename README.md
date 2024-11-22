arxiv-pdftotext
===============

Convert PDFs to text as webservice.

Forked and extended from https://github.com/sdenel/pdftotext-docker-rest
with the following changes:

- provide multiple modes to convert
- allow reading PDF from GCS bucket
- run conversion under cgroup with memory limit


## Usage

This repository uses [`uv`](https://docs.astral.sh/uv/). In the following
we assume that `uv` is installed.

### Setup the Python environment

Run
```
uv sync
```
to install dependencies (including development dependencies) into a new
virtualenv in `.venv`.

### Start service locally

Run
```
uv run hypercorn --bind 0.0.0.0:8888 webserver:app
```

### Docker

#### Build docker image

Run
```
docker build -t arxiv-pdftotext:latest .
```

#### Run docker service:

Start the docker service with
```bash
docker run --privileged --cgroupns=host -d -p8888:8888 arxiv-pdftotext:latest
```

### Sending files for conversion

Three modes are supported:
- pdftotext: uses the poppler utilities tool `pdftotext`
- pdf2txt: uses the pdfminer.six tool `pdf2txt.py`
- auto: first tries pdftotext and if that fails pdf2txt

Default mode is `auto`

```bash
curl -F "file=@tests/hello-world.pdf;" http://localhost:8888/
```

Passing a different mode:
```bash
curl -F "file=@tests/hello-world.pdf;" http://localhost:8888/?mode=pdf2txt
```

Note that files not ending in `.pdf` will be rejected.

### Converting PDFs located in GCS buckets

It is possible to convert PDF files in GCS buckets via the endpoint
`/from_bucket`. By default, all buckets are accepted.
If the program is started with the environment variable `ACCEPTED_BUCKETS`
begin set to a comma-separated list of acceptable buckets,
only `gs://` URIs with one of these buckets will be accepted.

Note that one can set `ACCEPTED_BUCKETS` also via `.env` files.

Example conversion:

```bash
curl -X POST 'http://localhost:8888/from_bucket?uri=gs://some-bucket/some-file.pdf'
```

## Development

We provide a pre-commit configuration file. We strongly recommend activating
the pre-commit hook by e.g. running
```
uv tool install pre-commit --with pre-commit-uv --force-reinstall
pre-commit install --install-hooks
```

