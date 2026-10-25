format:
	ruff format
	npx @biomejs/biome@2.6.3 format --write
	djhtml pgcommitfest/*/templates/*.html pgcommitfest/*/templates/*.inc --tabwidth=1

lint:
	ruff check
	npx @biomejs/biome@2.6.3 check

lint-fix:
	ruff check --fix
	npx @biomejs/biome@2.6.3 check --fix

lint-fix-unsafe:
	ruff check --fix --unsafe-fixes
	npx @biomejs/biome@2.6.3 check --fix --unsafe

fix: format lint-fix-unsafe
