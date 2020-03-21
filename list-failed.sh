rm -rf png-exports
mkdir png-exports
for i in 3d/*/*.obj; do
	if echo $i | grep -q 'viper.*.obj'; then
		continue
	fi
	if ! ./obj-view.py $i --exit > /dev/null  2> /dev/null; then
		echo $i
	fi
done
