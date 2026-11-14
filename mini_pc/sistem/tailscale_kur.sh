#!/bin/sh
# Tailscale kurulumu (antiX 32-bit, runit). Kullanım: sudo sh ~/tailscale_kur.sh
# Uzaktan erişim: operatör CGNAT veriyor (10.x), port yönlendirme yok → Tailscale dışarıya kendisi bağlanır.
set -e
D=/home/karavan/tailscale_1.104.7_386
install -m755 $D/tailscaled /usr/local/sbin/tailscaled
install -m755 $D/tailscale /usr/local/bin/tailscale
mkdir -p /var/lib/tailscale /etc/sv/tailscaled
cat > /etc/sv/tailscaled/run <<'E'
#!/bin/sh
exec 2>&1
mkdir -p /run/tailscale
exec /usr/local/sbin/tailscaled --state=/var/lib/tailscale/tailscaled.state --socket=/run/tailscale/tailscaled.sock --port=41641
E
chmod 755 /etc/sv/tailscaled/run
ln -sf /etc/sv/tailscaled /etc/service/
echo "tailscaled başlatılıyor..."; sleep 6
echo; echo ">>> Aşağıda çıkan https://login.tailscale.com/... adresine tıkla, Google hesabınla giriş yap <<<"; echo
/usr/local/bin/tailscale up --hostname=karavan --operator=karavan
echo; echo "TAMAM. Tailscale adresi:"; /usr/local/bin/tailscale ip -4
