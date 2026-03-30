.PHONY: up stop clean build logs lint type test

up: stop clean build run
	
run:
	docker run -it --rm --privileged --cgroupns host -p 8080:8080 arxiv-pdftotext:latest

build:
	docker buildx build -t arxiv-pdftotext:latest --load .

stop:
	docker stop arxiv-pdftotext || true

clean:
	docker rmi arxiv-pdftotext || true

logs:
	docker logs -f arxiv-pdftotext

lint:
	uv run ruff check

type:
	uv run ty check

test:
	uv run pytest tests
	