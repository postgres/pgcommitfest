format:
	ruff format
	npx @biomejs/biome format --write
	djhtml pgcommitfest/*/templates/*.html pgcommitfest/*/templates/*.inc --tabwidth=1

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
