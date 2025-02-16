format:
	ruff format
	npx @biomejs/biome format --write

lint:
	ruff check
	npx @biomejs/biome check

lint-fix:
	ruff check --fix
	npx @biomejs/biome check --fix

lint-fix-unsafe:
	ruff check --fix --unsafe-fixes
	npx @biomejs/biome check --fix --unsafe

fix: format lint-fix-unsafe
