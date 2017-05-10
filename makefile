.PHONY: clean build

build:
	python setup.py bdist_wheel

clean:
	rm -f MANIFEST
	rm -rf build dist
