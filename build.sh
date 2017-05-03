#!/bin/bash
cp -R lib/python2.7/site-packages/* ./build
cp lambda_function.py ./build
cd build
zip -r ../generate_directory_indexes.zip ./*
aws lambda update-function-code --function generate_directory_indexes --zip-file fileb://../generate_directory_indexes.zip --publish
