
I1=$1
I2=$2

export LC_COLLATE=C
find "$I1" -type f -printf "%P\n" | sed -e 's#\.[^\.]*$##' | sort >/tmp/f1.txt
find "$I1" -type l -printf "%P\n" | sed -e 's#\.[^\.]*$##' | sort >/tmp/l1.txt

find "$I2" -type f -printf "%P\n" | sed -e 's#\.[^\.]*$##' | sort >/tmp/f2.txt
find "$I2" -type l -printf "%P\n" | sed -e 's#\.[^\.]*$##' | sort >/tmp/l2.txt

diff /tmp/f1.txt /tmp/f2.txt
#diff /tmp/l1.txt /tmp/l2.txt
