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

Two modes are supported:
- pdftotext: uses the poppler utilities tool `pdftotext`
- pdf2txt: uses the pdfminer.six tool `pdf2txt.py`

Default mode is `pdftotext`

```bash
wget http://www.xmlpdf.com/manualfiles/hello-world.pdf
curl -F "file=@hello-world.pdf;" http://localhost:8888/
```

Passing a different mode:
```bash
curl -F "file=@hello-world.pdf;" -F "mode=pdf2txt;" http://localhost:8888/
```


## Todo

- auto-fallback: if mode=auto, first try pdftotext, if that fails/runs out of
  memory, try pdfminer/pdf2text.py


## Development

We provide a pre-commit configuration file. We strongly recommend activating
the pre-commit hook by e.g. running
```
uv tool install pre-commit --with pre-commit-uv --force-reinstall
pre-commit install --install-hooks
```

