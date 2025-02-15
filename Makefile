format:
	ruff format
	npx @biomejs/biome format --write

lint:
	ruff check
	npx @biomejs/biome check

lint-fix:
	ruff check --fix
	npx @biomejs/biome check --fix
