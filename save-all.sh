#!/bin/sh

rm -rf png-exports
mkdir png-exports
for i in 3d/*/*.obj; do
	./obj-view.py $i --res 2048 --rot 90 --save "png-exports/$(basename $i .obj).png"
done
