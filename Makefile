
SOURCE_GLOB=$(wildcard bot_maker/*.py bot_maker/**/*.py tests/**/*.py examples/*.py)

IGNORE_PEP=E203,E221,E241,E272,E501,F811

# help scripts to find the right place of bot_maker module
export PYTHONPATH=./

.PHONY: all
all : clean lint

.PHONY: clean
clean:
	rm -fr dist/* .pytype ./src/bot_maker/**/*.pyi ./src/bot_maker/*.pyi

.PHONY: lint
lint: pylint pycodestyle flake8 mypy


# disable: TODO list temporay
.PHONY: pylint
pylint:
	pylint \
		--load-plugins pylint_quotes \
		--disable=W0511,R0801,cyclic-import,C4001 \
		$(SOURCE_GLOB)

.PHONY: pycodestyle
pycodestyle:
	pycodestyle \
		--statistics \
		--count \
		--ignore="${IGNORE_PEP}" \
		$(SOURCE_GLOB)

.PHONY: flake8
flake8:
	flake8 \
		--ignore="${IGNORE_PEP}" \
		$(SOURCE_GLOB)

.PHONY: mypy
mypy:
	MYPYPATH=stubs/ mypy \
		$(SOURCE_GLOB)

.PHONY: pytype
pytype:
	pytype \
		-V 3.8 \
		--disable=import-error,pyi-error \
		src/
	pytype \
		-V 3.8 \
		--disable=import-error \
		examples/

.PHONY: uninstall-git-hook
uninstall-git-hook:
	pre-commit clean
	pre-commit gc
	pre-commit uninstall
	pre-commit uninstall --hook-type pre-push

.PHONY: install-git-hook
install-git-hook:
	# cleanup existing pre-commit configuration (if any)
	pre-commit clean
	pre-commit gc
	# setup pre-commit
	# Ensures pre-commit hooks point to latest versions
	pre-commit autoupdate
	pre-commit install
	pre-commit install --hook-type pre-push

.PHONY: install
install:
	pip3 install -r requirements.txt
	pip3 install -r requirements-dev.txt
	$(MAKE) install-git-hook

.PHONY: pytest
pytest:
	pytest tests/

.PHONY: test-unit
test-unit: pytest

.PHONY: test
test: pytest

.PHONY: check-python-version
check-python-version:
	./scripts/check_python_version.py

code:
	code .

.PHONY: run
run:
	python3 bin/run.py

.PHONY: dist
dist:
	python3 setup.py sdist bdist_wheel

.PHONY: publish
publish:
	PATH=~/.local/bin:${PATH} twine upload dist/*

.PHONY: bot
bot:
	python3 examples/ding-dong-bot.py

.PHONY: version
version:
	@newVersion=$$(awk -F. '{print $$1"."$$2"."$$3+1}' < VERSION) \
		&& echo $${newVersion} > VERSION \
		&& git add VERSION \
		&& git commit -m "🔥 update version to $${newVersion}" > /dev/null \
		&& git tag "v$${newVersion}" \
		&& echo "Bumped version to $${newVersion}"

.PHONY: deploy-version
deploy-version:
	echo "VERSION = '$$(cat VERSION)'" > src/bot_maker/version.py

.PHONY: doc
doc:
	mkdocs serve
