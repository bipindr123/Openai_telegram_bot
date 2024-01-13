#!/bin/bash

# Config
IMAGE_NAME="tgbotim"
CONTAINER_NAME="tgbot"

# Build image
docker rm -f $CONTAINER_NAME
docker rmi $(docker images -q $IMAGE_NAME)
docker build --build-arg LIB_DIR=/usr/lib -t $IMAGE_NAME . 

# Start container
docker run --net=host --name $CONTAINER_NAME -d $IMAGE_NAME
