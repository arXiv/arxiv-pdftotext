
arxiv-pdftotext. As a webservice, containerized! The image is based on Alpine.

Forked and extended from https://github.com/sdenel/pdftotext-docker-rest

## Usage

Run the service:

```bash
docker run -d -p8888:8888 arxiv-pdftotext:latest
```

Two modes are supported:
- pdftotext: uses the poppler utilities tool `pdftotext`
- pdf2txt: uses the pdfminer.six tool `pdf2txt.py`

Example of usage:

Default mode is `pdftotext`
```bash
wget http://www.xmlpdf.com/manualfiles/hello-world.pdf
curl -F "file=@hello-world.pdf;" http://localhost:8888/
```

Passing a different mode:
```bash
curl -F "file=@hello-world.pdf;" -F "mode=pdf2txt;" http://localhost:8888/
```

