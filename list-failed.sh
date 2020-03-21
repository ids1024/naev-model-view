rm -rf png-exports
mkdir png-exports
for i in 3d/*/*.obj; do
	if ! ./obj-view.py $i --exit > /dev/null  2> /dev/null; then
		echo $i
	fi
done
