.PHONY: clean build

build:
	python setup.py bdist_wheel

clean:
	rm -f MANIFEST
	rm -rf build dist

# this is specific to the puppetlabs "plops" internal pypi repo
release:
	python setup.py sdist upload -r plops
