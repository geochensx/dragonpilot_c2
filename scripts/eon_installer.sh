#!/usr/bin/bash
rm -fr /data/openpilot ;
cd /data/ &&

git clone https://github.com/geochensx/dragonpilot_c2 -b main-c2-master --single-branch --depth=1 openpilot &&

touch /data/data/com.termux/files/continue.sh &&
echo "#!/usr/bin/bash" >> /data/data/com.termux/files/continue.sh &&
echo "cd /data/openpilot" >> /data/data/com.termux/files/continue.sh &&
echo "exec ./launch_openpilot.sh" >> /data/data/com.termux/files/continue.sh &&

chmod u+x /data/data/com.termux/files/continue.sh &&
reboot
