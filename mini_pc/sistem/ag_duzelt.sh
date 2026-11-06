#!/bin/sh
# Çift DHCP'yi kaldır: dhcpcd kapanır, connman "caner" ağında sabit 192.168.1.117 kullanır.
# 90 sn içinde modeme ulaşılamazsa her şeyi eski hâline döndürür.
[ "$(id -u)" = 0 ] || { echo "sudo ile çalıştır"; exit 1; }
if [ "$1" != "arka" ]; then
  setsid nohup sh "$0" arka > /var/log/ag_duzelt.log 2>&1 < /dev/null &
  echo "Başladı. Bağlantı birkaç saniye kopabilir, bu normal. Pencereyi kapatabilirsin."
  exit 0
fi
S=wifi_dc85dedf3797_63616e6572_managed_psk
echo "$(date) başladı"
cp /etc/resolv.conf /etc/resolv.conf.dhcpcd-yedek
sv down dhcpcd; rm -f /etc/service/dhcpcd
sleep 2
connmanctl config $S --ipv4 manual 192.168.1.117 255.255.255.0 192.168.1.1
connmanctl config $S --nameservers 192.168.1.1
sleep 10
grep -q '^nameserver' /etc/resolv.conf || echo 'nameserver 192.168.1.1' > /etc/resolv.conf
ok=0
for i in $(seq 1 16); do
  if ping -c 1 -W 3 192.168.1.1 >/dev/null 2>&1 && ip -4 addr show wlan0 | grep -q '192.168.1.117/'; then ok=1; break; fi
  sleep 5
done
if [ $ok = 1 ]; then
  echo "$(date) TAMAM"; ip -4 addr show wlan0 | grep inet
else
  echo "$(date) OLMADI, geri alınıyor"
  connmanctl config $S --ipv4 dhcp
  ln -s /etc/sv/dhcpcd /etc/service/dhcpcd
  cp /etc/resolv.conf.dhcpcd-yedek /etc/resolv.conf
fi
