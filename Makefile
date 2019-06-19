# Makefile for the python package.
#

PACKAGE_NAME != sed -n "s/\s*name='\(.*\)'.*/\1/p" ./setup.py
WORKON_HOME ?= $(HOME)/.virtualenvs
VIRTUAL_ENV ?= $(WORKON_HOME)/$(PACKAGE_NAME)
PYTHON=${VIRTUAL_ENV}/bin/python3
MAKE := $(MAKE) --no-print-directory

default:
	@echo "Makefile for $(PACKAGE_NAME)"
	@echo
	@echo 'Usage:'
	@echo
	@echo '    make install    install the package in a virtual environment'
	@echo '    make reset      recreate the virtual environment'
	@echo '    make remove     remove the virtual environment'
	@echo '    make clean      cleanup all temporary files'
	@echo


venv: $(VIRTUAL_ENV)/bin/activate
$(VIRTUAL_ENV)/bin/activate: setup.py
	test -d $(VIRTUAL_ENV) || virtualenv -p python3 $(VIRTUAL_ENV)
	${PYTHON} -m pip install -U pip
	${PYTHON} -m pip uninstall --yes $(PACKAGE_NAME) &>/dev/null || true
	find . -name "setup.py" -exec sh -c '${PYTHON} -m pip install -e `dirname {}`' \;
	touch $(VIRTUAL_ENV)/bin/activate
	@echo '#'
	@echo '#  use "source ${VIRTUAL_ENV}/bin/activate" to activate virtual environment'

install: venv

reset:
	$(MAKE) clean
	rm -Rf "$(VIRTUAL_ENV)"
	$(MAKE) install

remove:
	$(MAKE) clean
	rm -Rf "$(VIRTUAL_ENV)"
	@echo '#'
	@echo '#  use "deactivate" to exit virtual environment'

clean:
	@rm -Rf *.egg .cache .coverage .tox build dist docs/build htmlcov
	@find -depth -type d -name __pycache__ -exec rm -Rf {} \;
	@find -type f -name '*.pyc' -delete

.PHONY: default install reset clean test
